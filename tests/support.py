"""Tien ich dung chung cho bo test.

Truoc day moi tep test tu viet lai `_env`, `http`, va phan dung multipart —
nam ban sao hoi khac nhau, sua mot cho quen bon cho. Gop vao day de co mot
nguon su that duy nhat.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parent.parent
EXTENSION = ROOT / "extension"


def env(name: str, default: str = "") -> str:
    """Doc mot bien tu .env cua du an (khong dung thu vien ngoai)."""
    envfile = ROOT / ".env"
    if not envfile.is_file():
        return default
    for line in envfile.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == name:
            return value.strip()
    return default


def _host() -> str:
    """Stack chi mo tren loopback — dia chi duoc ghi cung trong compose."""
    return "127.0.0.1"


#: nginx la CUA DUY NHAT cong bo ra host, chi tren loopback.
WEB = f"http://{_host()}:{env('WEB_PORT', '5001')}"
#: LibreTranslate — khong con cong rieng, chi tiep can qua proxy.
API = f"{WEB}/api"
#: EnViT5 — cung vay.
ENGINE = f"{WEB}/api2"
#: May doc Piper — cung vay.
TTS = f"{WEB}/api3"


class Response(NamedTuple):
    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self) -> Any:
        return json.loads(self.body or b"null")


def request(url: str, *, data: Any = None, method: str | None = None,
            headers: dict[str, str] | None = None, raw: bytes | None = None,
            timeout: float = 60) -> Response:
    """Goi HTTP va LUON tra ve Response, ke ca khi ma loi >= 400.

    Test can kiem tra ca truong hop bi tu choi, nen loi HTTP la du lieu chu
    khong phai ngoai le."""
    body = raw
    hdrs = dict(headers or {})
    if data is not None:
        body = json.dumps(data).encode()
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(
        url, data=body, headers=hdrs,
        method=method or ("POST" if body is not None else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Response(r.status, dict(r.headers), r.read())
    except urllib.error.HTTPError as e:
        # HTTPError giu mot file handle; khong dong se sinh ResourceWarning.
        with e:
            return Response(e.code, dict(e.headers), e.read())


def reachable(url: str, timeout: float = 5) -> bool:
    try:
        return request(url, timeout=timeout).status < 500
    except OSError:
        return False


def multipart(fields: dict[str, str],
              file: tuple[str, str, bytes] | None = None) -> tuple[bytes, str]:
    """Dung than multipart/form-data. Tra ve (body, content_type).

    `file` la (ten_truong, ten_tep, noi_dung)."""
    boundary = "----dich" + uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        for k, v in fields.items()
    ]
    if file:
        name, filename, content = file
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
            + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def content_script_source() -> str:
    """Gop ma cua content script. No duoc chia thanh nhieu tep nap theo thu tu,
    nen test ve noi dung nen nhin tat ca nhu mot."""
    parts = sorted((EXTENSION / "content").glob("*.js"))
    return "\n".join(f.read_text() for f in parts)


def extension_sources() -> dict[str, str]:
    """Moi tep .js cua extension (ke ca trong content/), khong gom vendor."""
    out = {p.name: p.read_text() for p in EXTENSION.glob("*.js")}
    out.update({f"content/{p.name}": p.read_text()
                for p in (EXTENSION / "content").glob("*.js")})
    return out


def translate(base: str, q: Any, target: str, source: str = "auto",
              fmt: str = "text", **extra: Any) -> Response:
    """Goi /translate cua mot engine. `base` da gom ca tien to (/api hay /api2)."""
    return request(f"{base}/translate",
                   data={"q": q, "source": source, "target": target, "format": fmt, **extra})
