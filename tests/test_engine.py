"""Test engine thu hai (EnViT5 qua CTranslate2) va cach UI chon engine.

Tu bo qua neu engine chua duoc bat.

    python3 -m unittest tests.test_engine -v
"""
from __future__ import annotations

import json
import unittest

from tests.support import EXTENSION as EXT, ROOT, WEB, env, reachable, request

#: Engine chi lo ra qua nginx, khong mo cong rieng.
ENG = WEB + "/api2"


def http(url, data=None, timeout=120):
    r = request(url, data=data, timeout=timeout)
    return r.status, r.headers, r.body


needs_engine = unittest.skipUnless(
    reachable(ENG + "/health"), f"engine EnViT5 chua bat tai {ENG}")


@needs_engine
class TestEngineBasics(unittest.TestCase):
    def test_health(self):
        status, _, body = http(ENG + "/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")

    def test_info_reports_model_and_license(self):
        _, _, body = http(ENG + "/info")
        info = json.loads(body)
        self.assertIn("envit5", info["model"].lower())
        self.assertEqual(info["engine"], "ctranslate2")
        self.assertEqual(info["quantization"], "int8")
        self.assertEqual(info["license"], "openrail")

    def test_languages_only_en_vi(self):
        _, _, body = http(ENG + "/languages")
        self.assertEqual({l["code"] for l in json.loads(body)}, {"en", "vi"})


@needs_engine
class TestEngineTranslate(unittest.TestCase):
    def tr(self, q, source="auto", target="vi", **extra):
        status, _, body = http(ENG + "/translate",
                               {"q": q, "source": source, "target": target,
                                "format": "text", **extra})
        return status, json.loads(body)

    def test_en_to_vi(self):
        status, data = self.tr("Good morning, how are you today?", "en", "vi")
        self.assertEqual(status, 200, data)
        self.assertTrue(data["translatedText"].strip())

    def test_vi_to_en(self):
        status, data = self.tr("Hôm nay trời rất đẹp.", "vi", "en")
        self.assertEqual(status, 200, data)
        self.assertRegex(data["translatedText"].lower(), r"today|beautiful|weather|nice")

    def test_language_prefix_is_stripped(self):
        """EnViT5 tra ve 'vi: ...' / 'en: ...' — tien to do KHONG duoc lot ra API."""
        _, data = self.tr("The cat sits on the mat.", "en", "vi")
        self.assertFalse(data["translatedText"].lower().startswith(("vi:", "en:")),
                         f"tien to chua bi cat: {data['translatedText']!r}")

    def test_auto_detect_vietnamese(self):
        _, data = self.tr("Tôi đang học lập trình.", "auto", "en")
        self.assertEqual(data["detectedLanguage"]["language"], "vi")
        self.assertTrue(data["translatedText"].strip())

    def test_auto_detect_english(self):
        _, data = self.tr("I am learning to program.", "auto", "vi")
        self.assertEqual(data["detectedLanguage"]["language"], "en")

    def test_batch_keeps_length_and_order(self):
        items = ["Save", "Cancel", "Delete account", "Settings"]
        status, data = self.tr(items, "en", "vi")
        self.assertEqual(status, 200, data)
        out = data["translatedText"]
        self.assertIsInstance(out, list)
        self.assertEqual(len(out), len(items))
        self.assertTrue(all(s.strip() for s in out))

    def test_reports_timing(self):
        _, data = self.tr("A short sentence.", "en", "vi")
        self.assertIsInstance(data["ms"], int)


@needs_engine
class TestEngineLimits(unittest.TestCase):
    """Engine chi lam duoc en<->vi — phai tu choi ro rang, khong tra rac."""

    def test_rejects_unsupported_pair(self):
        status, _, body = http(ENG + "/translate",
                               {"q": "hello", "source": "en", "target": "ja",
                                "format": "text"})
        self.assertEqual(status, 400)
        self.assertIn("en<->vi", json.loads(body)["error"])

    def test_rejects_same_language(self):
        status, _, _ = http(ENG + "/translate",
                            {"q": "hello", "source": "en", "target": "en",
                             "format": "text"})
        self.assertEqual(status, 400)

    def test_rejects_html_format(self):
        status, _, body = http(ENG + "/translate",
                               {"q": "<p>hi</p>", "source": "en", "target": "vi",
                                "format": "html"})
        self.assertEqual(status, 400)
        self.assertIn("HTML", json.loads(body)["error"])

    def test_rejects_missing_q(self):
        status, _, _ = http(ENG + "/translate", {"source": "en", "target": "vi"})
        self.assertEqual(status, 400)

    def test_unknown_endpoint_is_404(self):
        self.assertEqual(http(ENG + "/nope")[0], 404)

    def test_no_wildcard_cors(self):
        """Khong duoc mo cho moi origin: neu mo, bat ky trang web nao nguoi dung
        ghe cung goi duoc may chu dich nay tu trinh duyet cua ho."""
        _, headers, _ = http(ENG + "/languages")
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))


class TestUiEngineSelector(unittest.TestCase):
    """Phan UI — kiem tra tren dia, khong can container chay."""

    @classmethod
    def setUpClass(cls):
        web = ROOT / "web" / "html"
        cls.html = (web / "index.html").read_text()
        cls.js = (web / "js" / "app.js").read_text()
        cls.engines_js = (web / "js" / "engines.js").read_text()

    def test_dropdown_exists_and_is_labelled(self):
        self.assertIn('id="engine"', self.html)
        self.assertIn('for="engine"', self.html)

    def test_both_engines_offered(self):
        self.assertIn('value="lt"', self.html)
        self.assertIn('value="hf"', self.html)

    def test_each_engine_declares_its_own_base(self):
        self.assertIn('base: "/api"', self.engines_js)
        self.assertIn('base: "/api2"', self.engines_js)

    def test_falls_back_when_pair_unsupported(self):
        """Chon EnViT5 roi dich en->ja thi phai tu quay ve LibreTranslate,
        khong duoc de nguoi dung nhan loi 400."""
        self.assertIn("function pickEngine", self.engines_js)
        self.assertIn("function engineHandles", self.engines_js)

    def test_file_translation_always_uses_libretranslate(self):
        self.assertIn("base: ENGINES.lt.base", self.js)

    def test_nginx_proxies_api2(self):
        conf = (ROOT / "web" / "nginx.conf").read_text()
        self.assertIn("location /api2/", conf)
        # Phai qua BIEN + resolver, khong viet cung ten host: nginx phan giai
        # upstream luc nap config, engine chua ton tai la nginx khong khoi dong noi.
        self.assertIn("set                $engine http://engine:8000", conf)
        self.assertIn("proxy_pass         $engine", conf)


class TestEngineBuildDefinition(unittest.TestCase):
    def test_torch_stays_out_of_runtime_image(self):
        """PyTorch chi can de convert. Neu no lot vao tang chay thi image phinh
        them gan 1 GB ma khong dung den."""
        df = (ROOT / "engine" / "Dockerfile").read_text()
        runtime = df[df.rindex("FROM python"):]
        self.assertNotIn("torch", runtime)

    def test_runtime_is_offline(self):
        df = (ROOT / "engine" / "Dockerfile").read_text()
        runtime = df[df.rindex("FROM python"):]
        self.assertIn("HF_HUB_OFFLINE=1", runtime)

    def test_model_id_matchesenv(self):
        self.assertEqual(env("ENGINE_MODEL_ID", ""), "VietAI/envit5-translation")

    def test_thread_budget_shared_with_libretranslate(self):
        import os
        total = (int(env("LT_THREADS", "4")) * int(env("OMP_NUM_THREADS", "4"))
                 + int(env("ENGINE_INTRA_THREADS", "4")))
        self.assertLessEqual(total, 3 * os.cpu_count(),
                             f"tong {total} thread tren {os.cpu_count()} luong CPU")


if __name__ == "__main__":
    unittest.main(verbosity=2)
