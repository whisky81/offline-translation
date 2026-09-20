"""May chu dich dung EnViT5 (CTranslate2 int8), API tuong thich LibreTranslate.

EnViT5 la model T5 hai chieu EN<->VI: tien to o dau vao la ngon ngu NGUON
("en: ..." -> ra "vi: ..."), va dau ra mang tien to ngon ngu dich phai cat bo.
Vi vay model chi phuc vu dung cap en<->vi; moi cap khac tra loi ro rang.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import ctranslate2
from transformers import AutoTokenizer

MODEL_DIR = os.environ.get("MODEL_DIR", "/model")
PORT = int(os.environ.get("PORT", "8000"))
INTRA = int(os.environ.get("INTRA_THREADS", "4"))
INTER = int(os.environ.get("INTER_THREADS", "1"))
BEAM = int(os.environ.get("BEAM_SIZE", "2"))
MAX_LEN = int(os.environ.get("MAX_DECODING_LENGTH", "512"))
MODEL_ID = os.environ.get("MODEL_ID", "VietAI/envit5-translation")

SUPPORTED = {"en": "English", "vi": "Vietnamese"}
_PREFIX = re.compile(r"^\s*(?:en|vi)\s*:\s*")

print(f"Nap {MODEL_DIR} (intra={INTRA} inter={INTER} beam={BEAM})", flush=True)
_t0 = time.perf_counter()
translator = ctranslate2.Translator(MODEL_DIR, device="cpu", compute_type="int8",
                                    intra_threads=INTRA, inter_threads=INTER)
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
print(f"San sang sau {time.perf_counter()-_t0:.1f}s", flush=True)

# CTranslate2 Translator an toan voi nhieu luong, nhung mot khoa giup do tre
# on dinh tren may 1 nguoi dung va tranh tranh chap CPU giua cac request.
_lock = threading.Lock()

# Tieng Viet co nhung ky tu khong xuat hien trong tieng Anh -> nhan dien du dung
# cho cap en/vi ma khong can them model detect.
_VI_CHARS = re.compile(
    "[ăâđêôơưĂÂĐÊÔƠƯàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩị"
    "òóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]")

# Chu Han / Kana / Hangul. Model nay khong biet cac thu tieng do, va heuristic
# "khong co dau tieng Viet => tieng Anh" se am tham coi chung la tieng Anh roi
# tra ve rac. Thay vi doan, tu choi thang.
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff]")


class UnsupportedText(ValueError):
    pass


def detect(text: str) -> str:
    if _CJK.search(text):
        raise UnsupportedText(
            "van ban co chu Han/Kana/Hangul — EnViT5 chi biet en va vi. "
            "Dung LibreTranslate cho cac thu tieng do.")
    return "vi" if _VI_CHARS.search(text) else "en"


def translate(texts: list[str], source: str) -> list[str]:
    """Dich giu nguyen thu tu va so luong phan tu cua `texts`.

    Phan tu rong duoc tra lai nguyen ven: dua "en: " vao model se sinh ra rac
    (thuong la mot dau hai cham) chu khong phai chuoi rong."""
    todo = [(i, t) for i, t in enumerate(texts) if t.strip()]
    out = list(texts)
    if not todo:
        return out

    batch = [tokenizer.convert_ids_to_tokens(tokenizer.encode(f"{source}: {t}"))
             for _, t in todo]
    with _lock:
        results = translator.translate_batch(
            batch, beam_size=BEAM, max_decoding_length=MAX_LEN,
            max_batch_size=8, replace_unknowns=True)
    for (i, _), r in zip(todo, results):
        ids = tokenizer.convert_tokens_to_ids(r.hypotheses[0])
        text = tokenizer.decode(ids, skip_special_tokens=True)
        out[i] = _PREFIX.sub("", text).strip()   # cat tien to "vi: " / "en: "
    return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):      # bot on, journald da co du thong tin
        pass

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # KHONG dat Access-Control-Allow-Origin. Engine chi tiep can duoc qua
        # nginx o :5001/api2, va UI web cung origin nen khong can CORS. Mo
        # rong cho moi origin se cho bat ky trang web nao dung may chu nay.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            self._send(200, {"status": "ok", "model": MODEL_ID})
        elif path == "/languages":
            self._send(200, [
                {"code": c, "name": n, "targets": [o for o in SUPPORTED if o != c]}
                for c, n in SUPPORTED.items()])
        elif path == "/info":
            self._send(200, {"model": MODEL_ID, "engine": "ctranslate2",
                             "quantization": "int8", "beam_size": BEAM,
                             "intra_threads": INTRA, "pairs": ["en->vi", "vi->en"],
                             "license": "openrail"})
        else:
            self._send(404, {"error": "khong co endpoint nay"})

    def do_POST(self):
        try:
            self._do_post()
        except Exception as exc:                            # noqa: BLE001
            # Khong de mot loi lap trinh lam chet handler: client se thay
            # 502 tu nginx thay vi mot thong bao co nghia.
            try:
                self._send(500, {"error": f"loi noi bo: {exc}"})
            except Exception:                               # noqa: BLE001
                pass

    def _do_post(self):
        if self.path.split("?")[0] != "/translate":
            self._send(404, {"error": "khong co endpoint nay"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"error": "than request khong phai JSON hop le"})
            return

        q = req.get("q")
        # q phai la chuoi hoac mang chuoi. Truoc day mot so (vd 123) lam
        # list(q) nem TypeError, handler chet giua chung, nginx tra 502.
        if isinstance(q, str):
            texts = [q]
        elif isinstance(q, list) and all(isinstance(x, str) for x in q):
            texts = list(q)
        else:
            self._send(400, {"error": "'q' phai la chuoi hoac mang chuoi"})
            return
        if not any(t.strip() for t in texts):
            self._send(400, {"error": "thieu tham so 'q'"})
            return
        if req.get("format") == "html":
            self._send(400, {"error": "EnViT5 khong giu duoc the HTML — "
                                      "dung engine LibreTranslate cho format=html"})
            return

        single = isinstance(q, str)

        source = (req.get("source") or "auto").lower()
        target = (req.get("target") or "vi").lower()
        if target == "zh-hans":
            target = "zh"
        if source == "auto":
            try:
                source = detect(texts[0])
            except UnsupportedText as exc:
                self._send(400, {"error": str(exc)})
                return
        if source not in SUPPORTED or target not in SUPPORTED or source == target:
            self._send(400, {"error": f"EnViT5 chi dich en<->vi, khong ho tro "
                                      f"{source}->{target}"})
            return

        try:
            t0 = time.perf_counter()
            out = translate(texts, source)
            ms = (time.perf_counter() - t0) * 1000
        except Exception as exc:                            # noqa: BLE001
            self._send(500, {"error": f"dich that bai: {exc}"})
            return

        body = {"translatedText": out[0] if single else out,
                "engine": MODEL_ID, "ms": round(ms)}
        if (req.get("source") or "auto").lower() == "auto":
            body["detectedLanguage"] = {"language": source, "confidence": 100}
        self._send(200, body)


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    print(f"Lang nghe tren :{PORT}", flush=True)
    srv.serve_forever()
