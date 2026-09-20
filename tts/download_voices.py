"""Tai giong Piper tu Hugging Face — chi chay o TANG BUILD cua Docker.

Moi giong la hai tep canh nhau: <ten>.onnx (model) va <ten>.onnx.json (cau hinh:
ma ngon ngu, tan so lay mau, so giong noi). Ca hai deu bat buoc — thieu tep json
thi Piper khong biet doc bang thu tieng gi.

Bien TTS_VOICES liet ke duong dan trong repo, cach nhau bang khoang trang, KHONG
kem duoi tep. Vi du:
    vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = os.environ.get("TTS_VOICE_REPO", "rhasspy/piper-voices")
BASE = f"https://huggingface.co/{REPO}/resolve/main"
OUT = Path(os.environ.get("VOICE_DIR", "/voices"))
SPEC = os.environ.get("TTS_VOICES", "").split()

# Mot giong 'medium' nang ~63 MB. Tep nho hon nhieu gan nhu chac chan la trang
# loi HTML hoac con tro LFS chu khong phai model — bat o day con hon de container
# khoi dong roi chet voi mot loi onnxruntime kho hieu.
MIN_MODEL_BYTES = 1_000_000


def fetch(url: str, dest: Path) -> int:
    try:
        with urllib.request.urlopen(url, timeout=600) as r, dest.open("wb") as f:
            n = 0
            while chunk := r.read(1 << 20):
                f.write(chunk)
                n += len(chunk)
            return n
    except urllib.error.HTTPError as exc:
        sys.exit(f"LOI: {url} -> HTTP {exc.code}. Kiem tra lai duong dan giong.")
    except urllib.error.URLError as exc:
        sys.exit(f"LOI: khong tai duoc {url} ({exc.reason}). Tang build can mang.")


def main() -> None:
    if not SPEC:
        sys.exit("LOI: TTS_VOICES rong — khong co giong nao de tai.")
    OUT.mkdir(parents=True, exist_ok=True)

    for path in SPEC:
        name = path.rsplit("/", 1)[-1]
        model, cfg = OUT / f"{name}.onnx", OUT / f"{name}.onnx.json"

        size = fetch(f"{BASE}/{path}.onnx", model)
        if size < MIN_MODEL_BYTES:
            sys.exit(f"LOI: {name}.onnx chi co {size} byte — khong phai model that.")
        fetch(f"{BASE}/{path}.onnx.json", cfg)

        try:
            meta = json.loads(cfg.read_text())
        except json.JSONDecodeError:
            sys.exit(f"LOI: {name}.onnx.json khong phai JSON hop le.")
        lang = (meta.get("language") or {}).get("code", "?")
        print(f"  {name}  {size/1e6:.1f} MB  [{lang}]", flush=True)

    print(f"Da tai {len(SPEC)} giong vao {OUT}", flush=True)


if __name__ == "__main__":
    main()
