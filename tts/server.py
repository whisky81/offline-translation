"""May doc offline dung Piper (mang neural VITS chay bang onnxruntime).

Vi sao phai co may chu nay, thay vi speechSynthesis cua trinh duyet:
Chrome/Brave tren Linux khong kem giong nao — no di muon speech-dispatcher cua
he thong. Tren may khong cai, getVoices() tra ve mang rong va nut "Doc" bam se
im lang. Tong hop o phia may chu roi tra ve WAV thi o dau cung nghe duoc.

Giong duoc nuong san vao image luc build (xem download_voices.py) nen luc chay
khong dong toi mang. Ngon ngu cua tung giong doc tu tep .onnx.json di kem, nen
them mot giong moi chi la them hai tep — khong phai sua ma nguon.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import threading
import time
import wave
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from piper import PiperVoice, SynthesisConfig

VOICE_DIR = Path(os.environ.get("VOICE_DIR", "/voices"))
PORT = int(os.environ.get("PORT", "8100"))
MAX_CHARS = int(os.environ.get("TTS_MAX_CHARS", "2000"))
CACHE_BYTES = int(os.environ.get("TTS_CACHE_MB", "64")) * 1024 * 1024
SPEED_MIN, SPEED_MAX = 0.5, 2.0

# Doc chi can van ban. Cac ky tu dieu khien C0/C1 (tru tab/xuong dong) khong
# phat ra am nao, chi lam ban log va lam roi bo tach cau cua Piper.
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
# Phai co it nhat mot chu cai hoac chu so thi moi co gi de doc. Chuoi toan dau
# cham hoac emoji se khien Piper sinh ra 0 mau -> tep WAV rong, nguoi dung bam
# nut ma khong nghe thay gi va khong hieu tai sao.
_SPEAKABLE = re.compile(r"[^\W_]", re.UNICODE)


class BadRequest(ValueError):
    """Loi do dau vao, tra ve 400 kem thong bao doc duoc."""


# --------------------------------------------------------------------------
# Kho giong
# --------------------------------------------------------------------------
class VoiceStore:
    """Tim, nap va giu cac giong Piper co trong VOICE_DIR.

    Nap lan dau khi co request (lazy): mot giong medium chiem ~90 MB RAM khi
    da tao phien onnxruntime, nen nuong san 5 giong ma nap het luc khoi dong
    la tra gia cho nhung giong khong ai dung.
    """

    def __init__(self, folder: Path):
        self.folder = folder
        self._loaded: dict[str, PiperVoice] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()
        self.catalog = self._scan()

    def _scan(self) -> dict[str, dict]:
        found: dict[str, dict] = {}
        for model in sorted(self.folder.glob("*.onnx")):
            cfg = model.with_suffix(".onnx.json")
            if not cfg.exists():
                print(f"Bo qua {model.name}: thieu {cfg.name}", flush=True)
                continue
            try:
                meta = json.loads(cfg.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                print(f"Bo qua {model.name}: {cfg.name} hong ({exc})", flush=True)
                continue
            code = (meta.get("language") or {}).get("code", "")
            found[model.stem] = {
                "id": model.stem,
                "path": model,
                # 'vi_VN' -> 'vi'. Client noi 'vi', khong noi 'vi_VN'.
                "lang": code.split("_")[0].lower(),
                "locale": code,
                "quality": (meta.get("audio") or {}).get("quality")
                           or meta.get("quality") or "?",
                "sample_rate": (meta.get("audio") or {}).get("sample_rate", 22050),
                "speakers": meta.get("num_speakers", 1),
            }
        return found

    @property
    def languages(self) -> list[str]:
        return sorted({v["lang"] for v in self.catalog.values() if v["lang"]})

    def resolve(self, lang: str | None, voice: str | None) -> dict:
        """Chon giong theo id cu the, hoac theo ngon ngu."""
        if voice:
            got = self.catalog.get(voice)
            if not got:
                raise BadRequest(f"khong co giong '{voice}'. Co: "
                                 f"{', '.join(sorted(self.catalog)) or 'khong co giong nao'}")
            return got
        want = (lang or "").split("-")[0].lower()
        if not want:
            raise BadRequest("thieu 'lang' hoac 'voice'")
        for v in self.catalog.values():
            if v["lang"] == want:
                return v
        raise BadRequest(f"chua nuong giong cho '{want}'. Co: "
                         f"{', '.join(self.languages) or 'khong co'}")

    def load(self, spec: dict) -> tuple[PiperVoice, threading.Lock]:
        vid = spec["id"]
        with self._guard:
            lock = self._locks.setdefault(vid, threading.Lock())
        if vid not in self._loaded:
            # Khoa theo tung giong: hai request cung luc cho cung mot giong
            # se khong nap model hai lan.
            with lock:
                if vid not in self._loaded:
                    t0 = time.perf_counter()
                    self._loaded[vid] = PiperVoice.load(str(spec["path"]))
                    print(f"Nap giong {vid} trong {time.perf_counter()-t0:.1f}s", flush=True)
        return self._loaded[vid], lock

    @property
    def loaded_ids(self) -> list[str]:
        return sorted(self._loaded)


# --------------------------------------------------------------------------
# Bo nho dem
# --------------------------------------------------------------------------
class WavCache:
    """LRU gioi han theo SO BYTE, khong theo so muc.

    Dem theo so muc la sai o day: mot cau ngan va mot doan 2000 ky tu chenh
    nhau vai chuc lan ve kich thuoc, nen 'toi da 64 muc' khong noi duoc gi ve
    luong RAM that su chiem.
    """

    def __init__(self, budget: int):
        self.budget = budget
        self._items: OrderedDict[str, bytes] = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    def get(self, key: str) -> bytes | None:
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key: str, blob: bytes) -> None:
        if len(blob) > self.budget:
            return                      # mot muc khong duoc nuot ca ngan sach
        with self._lock:
            if key in self._items:
                self._bytes -= len(self._items.pop(key))
            self._items[key] = blob
            self._bytes += len(blob)
            while self._bytes > self.budget:
                self._bytes -= len(self._items.popitem(last=False)[1])

    def stats(self) -> dict:
        with self._lock:
            return {"items": len(self._items), "bytes": self._bytes,
                    "budget": self.budget}


# --------------------------------------------------------------------------
# Tong hop
# --------------------------------------------------------------------------
def clean(text: str) -> str:
    return _CTRL.sub(" ", text).strip()


def synth(spec: dict, text: str, speed: float) -> bytes:
    voice, lock = store.load(spec)
    buf = io.BytesIO()
    # length_scale la do DAI cua am, nghich dao cua toc do: 2.0 = cham gap doi.
    cfg = SynthesisConfig(length_scale=1.0 / speed)
    with lock:
        with wave.open(buf, "wb") as wav:
            voice.synthesize_wav(text, wav, syn_config=cfg)
    return buf.getvalue()


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):      # journald da ghi du
        pass

    def _headers(self, code: int, ctype: str, length: int, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        # KHONG dat Access-Control-Allow-Origin — cung ly do nhu engine: may chu
        # nay chi tiep can qua nginx o :5001/api3, va UI web cung origin.
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, str(v))
        self.end_headers()

    def _json(self, code: int, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self._headers(code, "application/json; charset=utf-8", len(body))
        if self.command != "HEAD":
            self.wfile.write(body)

    def _wav(self, blob: bytes, extra: dict):
        self._headers(200, "audio/wav", len(blob), extra)
        self.wfile.write(blob)

    def do_OPTIONS(self):
        self._json(204, {})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            # 'ok' ngay ca khi chua nap giong nao: nap la lazy, va healthcheck
            # khong nen ep nap ~90 MB model chi de tra loi.
            self._json(200, {"status": "ok" if store.catalog else "no-voices",
                             "voices": len(store.catalog),
                             "languages": store.languages,
                             "loaded": store.loaded_ids})
        elif path == "/voices":
            self._json(200, [{k: v for k, v in s.items() if k != "path"}
                             for s in store.catalog.values()])
        elif path == "/info":
            self._json(200, {"engine": "piper", "runtime": "onnxruntime",
                             "max_chars": MAX_CHARS,
                             "speed_range": [SPEED_MIN, SPEED_MAX],
                             "cache": cache.stats(),
                             "license": "GPL-3.0-or-later (piper), MIT (giong noi)"})
        else:
            self._json(404, {"error": "khong co endpoint nay"})

    def do_POST(self):
        try:
            self._do_post()
        except BadRequest as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:                            # noqa: BLE001
            # Khong de mot loi lap trinh giet handler giua chung: client se
            # thay 502 tu nginx thay vi mot thong bao co nghia.
            try:
                self._json(500, {"error": f"loi noi bo: {exc}"})
            except Exception:                               # noqa: BLE001
                pass

    def _do_post(self):
        if self.path.split("?")[0] != "/speak":
            self._json(404, {"error": "khong co endpoint nay"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            raise BadRequest("than request khong phai JSON hop le")
        if not isinstance(req, dict):
            raise BadRequest("than request phai la mot doi tuong JSON")

        q = req.get("q")
        # Chi nhan chuoi. So hay mang se lam cac buoc sau nem loi kieu kho hieu
        # — tu choi ngay o day de thong bao con noi duoc dieu gi co ich.
        if not isinstance(q, str):
            raise BadRequest("'q' phai la chuoi")
        text = clean(q)
        if not text:
            raise BadRequest("thieu tham so 'q'")
        if not _SPEAKABLE.search(text):
            raise BadRequest("khong co chu nao de doc")

        truncated = len(text) > MAX_CHARS
        if truncated:
            text = text[:MAX_CHARS]

        speed = req.get("speed", 1.0)
        if not isinstance(speed, (int, float)) or isinstance(speed, bool):
            raise BadRequest("'speed' phai la so")
        speed = max(SPEED_MIN, min(SPEED_MAX, float(speed)))

        spec = store.resolve(req.get("lang"), req.get("voice"))

        key = hashlib.sha256(
            f"{spec['id']}|{speed:.3f}|{text}".encode()).hexdigest()
        blob = cache.get(key)
        cached = blob is not None

        t0 = time.perf_counter()
        if blob is None:
            blob = synth(spec, text, speed)
            cache.put(key, blob)
        ms = round((time.perf_counter() - t0) * 1000)

        # Piper co the tra ve WAV chi co phan header khi van ban khong phat am
        # duoc (vd mot chuoi ky tu la). Phat tep do la im lang — bao loi ro hon.
        with wave.open(io.BytesIO(blob)) as w:
            frames = w.getnframes()
            seconds = frames / (w.getframerate() or 1)
        if frames == 0:
            raise BadRequest("khong doc duoc doan nay — thu bo bot ky tu dac biet")

        self._wav(blob, {
            "X-Voice": spec["id"],
            "X-Lang": spec["lang"],
            "X-Ms": ms,
            "X-Cached": int(cached),
            "X-Truncated": int(truncated),
            "X-Chars": len(text),
            "X-Seconds": f"{seconds:.2f}",
        })


store = VoiceStore(VOICE_DIR)
cache = WavCache(CACHE_BYTES)

if __name__ == "__main__":
    if not store.catalog:
        print(f"CANH BAO: khong thay giong nao trong {VOICE_DIR}", flush=True)
    else:
        print(f"Co {len(store.catalog)} giong: "
              f"{', '.join(store.catalog)} (ngon ngu: {', '.join(store.languages)})",
              flush=True)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    print(f"Lang nghe tren :{PORT}", flush=True)
    srv.serve_forever()
