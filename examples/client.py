#!/usr/bin/env python3
"""Client cho may chu dich + may doc, bang thu vien chuan - khong can pip install gi.

Chay:  python3 examples/client.py
Dung trong du an:  from client import LibreTranslateClient

Stack chi cong bo MOT cong ra host: nginx tren 127.0.0.1:5001. Tu do:
    /api   -> LibreTranslate (moi cap ngon ngu)
    /api2  -> EnViT5         (chi en<->vi, dich sat hon)
    /api3  -> Piper          (doc thanh tieng, tra ve WAV)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Sequence, overload

WEB_URL = "http://127.0.0.1:5001"
DEFAULT_URL = f"{WEB_URL}/api"     # LibreTranslate qua nginx
TTS_URL = f"{WEB_URL}/api3"        # may doc Piper qua nginx


class LibreTranslateError(RuntimeError):
    pass


class LibreTranslateClient:
    def __init__(self, base_url: str = DEFAULT_URL, api_key: str | None = None,
                 timeout: float = 120.0, tts_url: str = TTS_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.tts_url = tts_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _post(self, path: str, payload: dict) -> dict | list:
        if self.api_key:
            payload = {**payload, "api_key": self.api_key}
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise LibreTranslateError(f"HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise LibreTranslateError(
                f"Khong ket noi duoc {self.base_url} — may chu dang chay chua? ({exc.reason})"
            ) from exc

    def languages(self) -> list[dict]:
        with urllib.request.urlopen(f"{self.base_url}/languages", timeout=self.timeout) as r:
            return json.loads(r.read())

    def detect(self, text: str) -> list[dict]:
        return self._post("/detect", {"q": text})  # type: ignore[return-value]

    @overload
    def translate(self, text: str, target: str = ..., source: str = ...,
                  fmt: str = ...) -> str: ...
    @overload
    def translate(self, text: Sequence[str], target: str = ..., source: str = ...,
                  fmt: str = ...) -> list[str]: ...

    def translate(self, text, target="vi", source="auto", fmt="text"):
        """Dich 1 chuoi -> str, hoac 1 danh sach chuoi -> list[str]."""
        data = self._post("/translate", {
            "q": list(text) if not isinstance(text, str) else text,
            "source": source, "target": target, "format": fmt,
        })
        return data["translatedText"]  # type: ignore[index]

    def voices(self) -> list[dict]:
        """Giong doc dang co. Mang rong hoac loi = may doc chua bat."""
        with urllib.request.urlopen(f"{self.tts_url}/voices", timeout=self.timeout) as r:
            return json.loads(r.read())

    def speak(self, text: str, lang: str = "vi", speed: float = 1.0) -> bytes:
        """Doc `text` thanh tieng, tra ve NOI DUNG TEP WAV (khong phai JSON).

        Van ban dai hon TTS_MAX_CHARS bi cat; goi y: tu cat theo cau o phia
        client roi phat noi tiep — tong hop nhanh hon phat khoang 10 lan nen
        doan sau luon kip, va tieng bat dau sau ~1 giay thay vi ~10 giay.
        """
        req = urllib.request.Request(
            f"{self.tts_url}/speak",
            data=json.dumps({"q": text, "lang": lang, "speed": speed}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise LibreTranslateError(f"HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise LibreTranslateError(
                f"Khong goi duoc may doc {self.tts_url} ({exc.reason})") from exc


if __name__ == "__main__":
    lt = LibreTranslateClient()

    print("Ngon ngu co san:")
    for lang in lt.languages():
        print(f"  {lang['code']:<4} {lang['name']:<12} -> {', '.join(lang['targets'])}")

    print("\nDich 1 cau:")
    print(" ", lt.translate("Everything runs on this machine, nothing leaves it.",
                            target="vi", source="en"))

    print("\nDich hang loat (nhanh hon nhieu so voi goi tung cau):")
    for src, out in zip(
        ["Save", "Cancel", "Settings", "Delete"],
        lt.translate(["Save", "Cancel", "Settings", "Delete"], target="vi", source="en"),
    ):
        print(f"  {src:<10} -> {out}")

    print("\nTu nhan dien ngon ngu:")
    print(" ", lt.detect("안녕하세요 반갑습니다"))
    print(" ", lt.translate("안녕하세요 반갑습니다", target="vi"))

    print("\nDoc thanh tieng (may doc la tuy chon):")
    try:
        for v in lt.voices():
            print(f"  giong {v['id']:<24} [{v['lang']}] {v['quality']}")
        cau = lt.translate("Everything runs on this machine.", target="vi", source="en")
        wav = lt.speak(cau, lang="vi")
        with open("/tmp/lt-client.wav", "wb") as f:
            f.write(wav)
        print(f"  da ghi /tmp/lt-client.wav ({len(wav):,} byte) — nghe: aplay /tmp/lt-client.wav")
    except (LibreTranslateError, OSError) as exc:
        print(f"  (bo qua: {exc})")
