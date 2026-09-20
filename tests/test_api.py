#!/usr/bin/env python3
"""Bo test cho may chu LibreTranslate local.

Chi dung thu vien chuan -> chay duoc tren Python 3.14 cua may, khong can pip install.

    python3 -m unittest discover -s tests -v          # tat ca
    python3 tests/test_api.py                         # tat ca + tom tat
    python3 -m unittest tests.test_api.TestWebUI -v   # rieng Web UI
"""
from __future__ import annotations

import json
import re
import sys
import time
import unittest
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from tests.support import API, WEB, env, multipart, request

BASE = API
EXPECTED_LANGS = {"en", "vi", "zh-Hans", "ja", "ko"}
TIMEOUT = 120


def http(path, data=None, method=None, headers=None, raw=None, timeout=TIMEOUT):
    """Duong dan tuong doi duoc ghep voi BASE; duong dan tuyet doi giu nguyen."""
    url = path if path.startswith("http") else BASE + path
    r = request(url, data=data, method=method, headers=headers, raw=raw, timeout=timeout)
    return r.status, r.headers, r.body


def jpost(path, data, timeout=TIMEOUT):
    status, _, body = http(path, data, timeout=timeout)
    return status, json.loads(body or b"{}")


def translate(q, target, source="auto", fmt="text", **extra):
    status, data = jpost("/translate",
                         {"q": q, "source": source, "target": target, "format": fmt, **extra})
    if status != 200:
        raise AssertionError(f"/translate tra HTTP {status}: {data}")
    return data["translatedText"]


class ServerUp(unittest.TestCase):
    """Chay truoc moi thu: neu may chu chet thi bao ro thay vi 40 test do."""

    def test_00_server_reachable(self):
        try:
            status, _, _ = http("/languages", timeout=10)
        except Exception as exc:  # noqa: BLE001
            self.fail(f"Khong ket noi duoc {BASE} — may chu dang chay chua?\n"
                      f"  ./scripts/ltctl status\n  {exc}")
        self.assertEqual(status, 200, "/languages phai tra 200")


class TestLanguages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, body = http("/languages")
        cls.langs = json.loads(body)
        cls.codes = {l["code"] for l in cls.langs}

    def test_expected_languages_loaded(self):
        missing = EXPECTED_LANGS - self.codes
        self.assertFalse(missing, f"thieu ngon ngu: {missing} (co: {sorted(self.codes)})")

    def test_every_language_has_targets(self):
        for l in self.langs:
            with self.subTest(lang=l["code"]):
                self.assertTrue(l["targets"], f"{l['code']} khong dich duoc sang dau")

    def test_vietnamese_reaches_every_other_language(self):
        vi = next(l for l in self.langs if l["code"] == "vi")
        self.assertGreaterEqual(
            set(vi["targets"]), EXPECTED_LANGS,
            "vi phai dich duoc sang moi ngon ngu da nap (ke ca bac cau qua en)")


class TestTranslate(unittest.TestCase):
    def test_en_to_vi(self):
        out = translate("Good morning, how are you today?", "vi", "en")
        self.assertTrue(out.strip())
        self.assertNotEqual(out.strip().lower(), "good morning, how are you today?",
                            "ket qua y het dau vao -> khong dich duoc")

    def test_vi_to_en(self):
        out = translate("Hôm nay trời rất đẹp và tôi muốn đi dạo.", "en", "vi")
        self.assertRegex(out.lower(), r"today|beautiful|weather|walk")

    def test_all_pairs_produce_output(self):
        """Moi cap trong 5 ngon ngu phai ra ket qua, ke ca cap phai bac cau."""
        sample = {"en": "The weather is nice today.",
                  "vi": "Thời tiết hôm nay rất đẹp.",
                  "ja": "今日はいい天気です。",
                  "ko": "오늘 날씨가 좋습니다.",
                  "zh-Hans": "今天天气很好。"}
        for src in sample:
            for tgt in EXPECTED_LANGS:
                if src == tgt:
                    continue
                with self.subTest(pair=f"{src}->{tgt}"):
                    out = translate(sample[src], tgt, src)
                    self.assertTrue(out.strip(), f"{src}->{tgt} tra ve rong")

    def test_zh_alias_accepted(self):
        """Gui 'zh' phai duoc chap nhan du /languages bao 'zh-Hans'."""
        self.assertTrue(translate("Local translation server.", "zh", "en").strip())

    def test_batch(self):
        items = ["Save", "Cancel", "Settings", "Delete", "Retry"]
        out = translate(items, "vi", "en")
        self.assertIsInstance(out, list)
        self.assertEqual(len(out), len(items))
        self.assertTrue(all(s.strip() for s in out))

    def test_batch_preserves_order(self):
        out = translate(["one", "two", "three"], "vi", "en")
        self.assertEqual(len(out), 3)
        self.assertNotEqual(out[0], out[1])

    def test_batch_larger_than_64(self):
        """LT_BATCH_LIMIT=-1 -> mang dai khong bi tu choi."""
        items = [f"item number {i}" for i in range(80)]
        out = translate(items, "vi", "en")
        self.assertEqual(len(out), 80)

    def test_auto_detect_source(self):
        self.assertTrue(translate("Xin chào thế giới", "en", "auto").strip())

    def test_html_format_keeps_tags(self):
        out = translate("<p>Hello <b>world</b></p>", "vi", "en", fmt="html")
        self.assertIn("<b>", out)
        self.assertIn("<p>", out)

    def test_alternatives(self):
        status, data = jpost("/translate", {
            "q": "hello", "source": "en", "target": "vi",
            "format": "text", "alternatives": 3})
        self.assertEqual(status, 200)
        self.assertIn("alternatives", data)
        self.assertIsInstance(data["alternatives"], list)

    def test_long_text(self):
        para = ("Machine translation running entirely on local hardware keeps "
                "documents private. ") * 15
        out = translate(para, "vi", "en")
        self.assertGreater(len(out), len(para) // 4)

    def test_unicode_roundtrip(self):
        out = translate("Tiếng Việt có dấu: ăn, ớt, ừ, ỹ", "en", "vi")
        self.assertTrue(out.strip())


class TestDetect(unittest.TestCase):
    def test_detect_vietnamese(self):
        status, data = jpost("/detect", {"q": "Đây là một câu tiếng Việt hoàn chỉnh."})
        self.assertEqual(status, 200)
        self.assertEqual(data[0]["language"], "vi")

    def test_detect_returns_confidence(self):
        _, data = jpost("/detect", {"q": "This is a complete English sentence."})
        self.assertIn("confidence", data[0])


class TestErrors(unittest.TestCase):
    def test_invalid_target_rejected(self):
        status, data = jpost("/translate",
                             {"q": "hello", "source": "en", "target": "xx", "format": "text"})
        self.assertGreaterEqual(status, 400, f"ma ngon ngu sai phai bi tu choi, nhan {status}")
        self.assertIn("error", data)

    def test_missing_q_rejected(self):
        status, _ = jpost("/translate", {"source": "en", "target": "vi", "format": "text"})
        self.assertGreaterEqual(status, 400)

    def test_empty_string_does_not_crash(self):
        status, _ = jpost("/translate",
                          {"q": "", "source": "en", "target": "vi", "format": "text"})
        self.assertLess(status, 500, "chuoi rong khong duoc lam may chu loi 500")


class TestNoWildcardCors(unittest.TestCase):
    """May chu chay tren loopback ma mo CORS cho moi origin thi BAT KY trang web
    nao nguoi dung ghe cung goi duoc no tu trinh duyet cua ho. Khong client nao
    cua du an can CORS: UI web cung origin, extension goi tu service worker."""

    def test_no_cors_on_get(self):
        _, headers, _ = http("/languages")
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))

    def test_no_cors_on_post(self):
        _, headers, _ = http("/translate",
                             {"q": "hi", "source": "en", "target": "vi", "format": "text"})
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))

    def test_cross_origin_preflight_is_not_blessed(self):
        _, headers, _ = http(
            "/translate", method="OPTIONS",
            headers={"Origin": "https://ke-tan-cong.example",
                     "Access-Control-Request-Method": "POST"})
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))

    def test_same_origin_still_works(self):
        """Bo CORS khong duoc lam hong UI cua chinh minh (cung origin)."""
        status, _, body = http("/translate",
                               {"q": "Good morning", "source": "en", "target": "vi",
                                "format": "text"}, headers={"Origin": WEB})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["translatedText"].strip())


class TestStockUiIsOff(unittest.TestCase):
    """UI goc cua LibreTranslate bi tat: ta co UI rieng o :5001, giu no chi la
    them be mat. Cac endpoint API thi van phai song."""

    def test_stock_ui_returns_404(self):
        self.assertEqual(http("/")[0], 404)
        self.assertEqual(http("/js/app.js")[0], 404)

    def test_api_endpoints_survive(self):
        for path in ("/languages", "/frontend/settings", "/spec"):
            with self.subTest(path=path):
                self.assertEqual(http(path)[0], 200)

    def test_swagger_still_reachable(self):
        self.assertEqual(http("/docs/", timeout=20)[0], 200)

    def test_frontend_settings_match_env(self):
        """UI cua ta doc supportedFilesFormat tu day."""
        _, _, body = http("/frontend/settings")
        cfg = json.loads(body)
        self.assertEqual(cfg["charLimit"], int(env("LT_CHAR_LIMIT", "-1")))
        self.assertTrue(cfg["supportedFilesFormat"])

    def test_formdata_payload_still_accepted(self):
        """API nhan ca multipart/form-data, khong chi JSON."""
        body, ctype = multipart({"q": "Good evening", "source": "auto",
                                 "target": "vi", "format": "text"})
        status, _, raw = http("/translate", raw=body, headers={"Content-Type": ctype})
        self.assertEqual(status, 200, raw[:200])
        self.assertTrue(json.loads(raw)["translatedText"].strip())


class TestFileTranslation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, body = http("/frontend/settings")
        cls.formats = json.loads(body)["supportedFilesFormat"]

    def test_txt_is_supported(self):
        self.assertIn(".txt", self.formats)

    def test_office_formats_supported(self):
        for fmt in (".docx", ".pptx", ".odt"):
            with self.subTest(fmt=fmt):
                self.assertIn(fmt, self.formats)

    def test_xlsx_is_not_supported(self):
        """Ghi nhan gioi han da biet — neu ban nay ho tro duoc thi test do va
        ta cap nhat tai lieu."""
        self.assertNotIn(".xlsx", self.formats,
                         "xlsx da duoc ho tro — cap nhat README!")

    def test_txt_upload_roundtrip(self):
        content = b"The document stays on this machine. Nothing is uploaded.\n"
        body, ctype = multipart({"source": "en", "target": "vi"},
                                ("file", "probe.txt", content))
        status, _, raw = http("/translate_file", raw=body,
                              headers={"Content-Type": ctype})
        self.assertEqual(status, 200, raw[:200])
        data = json.loads(raw)

        self.assertIn("translatedFileUrl", data, f"khong co link file dich: {data}")
        status, _, translated = http(data["translatedFileUrl"], timeout=60)
        self.assertEqual(status, 200, "khong tai duoc file da dich")
        self.assertTrue(translated.strip(), "file dich rong")
        self.assertNotEqual(translated.strip(), content.strip(), "file khong he duoc dich")


class TestPerformance(unittest.TestCase):
    def test_short_sentence_latency(self):
        translate("Warm up the worker.", "vi", "en")  # nap model truoc khi do
        t0 = time.perf_counter()
        translate("This is a short latency probe sentence.", "vi", "en")
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"\n      do tre 1 cau: {elapsed:.0f} ms", end="")
        self.assertLess(elapsed, 5000, f"qua cham: {elapsed:.0f} ms")

    def test_parallel_requests(self):
        """Nhieu worker gunicorn phai xu ly song song ma khong loi."""
        n = 8
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=n) as pool:
            results = list(pool.map(
                lambda i: translate(f"Parallel request number {i}.", "vi", "en"), range(n)))
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"\n      {n} request song song: {elapsed:.0f} ms", end="")
        self.assertEqual(len(results), n)
        self.assertTrue(all(r.strip() for r in results), "co request tra ve rong")


if __name__ == "__main__":
    print(f"Muc tieu: {BASE}\n")
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
