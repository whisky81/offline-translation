#!/usr/bin/env python3
"""Client LibreTranslate bang thu vien chuan - khong can pip install gi.

Chay:  python3 examples/client.py
Dung trong du an:  from client import LibreTranslateClient
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Sequence, overload

DEFAULT_URL = "http://127.0.0.1:5000"


class LibreTranslateError(RuntimeError):
    pass


class LibreTranslateClient:
    def __init__(self, base_url: str = DEFAULT_URL, api_key: str | None = None,
                 timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
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
