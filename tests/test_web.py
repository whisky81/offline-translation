"""Test UI tieng Viet rieng (nginx) va lop proxy cung origin.

    python3 -m unittest tests.test_web -v
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
import urllib.parse

from tests.support import API as LT, ROOT, WEB, env, multipart, reachable, request


def http(url, data=None, headers=None, timeout=60):
    r = request(url, data=data, headers=headers, timeout=timeout)
    return r.status, r.headers, r.body


WEB_OK = reachable(WEB + "/")
skip_web = unittest.skipUnless(
    WEB_OK, f"UI rieng khong chay tai {WEB} — ./scripts/ltctl restart")


@skip_web
class TestStaticUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.status, cls.headers, body = http(WEB + "/")
        cls.html = body.decode()

    def test_index_served(self):
        self.assertEqual(self.status, 200)
        self.assertIn("text/html", self.headers.get("Content-Type", ""))

    def test_html_lang_is_vietnamese(self):
        self.assertIn('<html lang="vi">', self.html)

    def test_interface_is_in_vietnamese(self):
        for word in ("Bản dịch", "Văn bản gốc", "Tự nhận diện", "ký tự"):
            with self.subTest(word=word):
                self.assertIn(word, self.html)

    def test_no_external_resources(self):
        """Cong cu offline: khong duoc phu thuoc CDN nao — mat mang van phai chay."""
        ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', self.html)
        self.assertFalse(ext, f"UI tham chieu tai nguyen ngoai: {ext}")

    def test_every_asset_loads(self):
        refs = re.findall(r'(?:src|href)="([^"]+)"', self.html)
        local = [r for r in refs if not r.startswith(("http", "data:", "#", "/docs"))]
        self.assertTrue(local)
        for ref in local:
            with self.subTest(asset=ref):
                status, _, body = http(urllib.parse.urljoin(WEB + "/", ref))
                self.assertEqual(status, 200)
                self.assertTrue(body)

    def test_js_modules_load_and_have_no_cdn(self):
        """UI duoc chia thanh module ES; tat ca phai nam tren may, khong CDN."""
        for name in ("app", "api", "engines", "store"):
            with self.subTest(module=name):
                status, _, body = http(f"{WEB}/js/{name}.js")
                self.assertEqual(status, 200)
                js = body.decode()
                self.assertNotIn("http://cdn", js)
                self.assertNotIn("https://", js.replace("https://www.w3.org", ""))

    def test_inputs_are_labelled(self):
        """Moi select/textarea phai co label — de dung duoc bang trinh doc man hinh."""
        ids = re.findall(r'<(?:select|textarea)[^>]*id="([^"]+)"', self.html)
        labelled = set(re.findall(r'<label[^>]*for="([^"]+)"', self.html))
        missing = [i for i in ids if i not in labelled]
        self.assertFalse(missing, f"khong co <label for=...>: {missing}")

    def test_ui_not_cached(self):
        self.assertIn("no-store", self.headers.get("Cache-Control", ""))


@skip_web
class TestApiProxy(unittest.TestCase):
    """/api/... phai tuong duong goi thang LibreTranslate, nhung cung origin."""

    def test_languages_through_proxy(self):
        status, _, body = http(WEB + "/api/languages")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(json.loads(body)), 5)

    def test_translate_through_proxy(self):
        status, _, body = http(WEB + "/api/translate", {
            "q": "Good morning", "source": "en", "target": "vi", "format": "text"})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["translatedText"].strip())

    def test_detect_through_proxy(self):
        _, _, body = http(WEB + "/api/detect", {"q": "Đây là tiếng Việt."})
        self.assertEqual(json.loads(body)[0]["language"], "vi")

    def test_alternatives_available(self):
        _, _, body = http(WEB + "/api/translate", {
            "q": "hello", "source": "en", "target": "vi",
            "format": "text", "alternatives": 3})
        self.assertIn("alternatives", json.loads(body))

    def test_proxy_is_the_only_way_in(self):
        """LibreTranslate khong con cong rieng tren host."""
        import socket
        with socket.socket() as sk:
            sk.settimeout(2)
            self.assertNotEqual(sk.connect_ex(("127.0.0.1", 5000)), 0,
                                "cong 5000 van mo — LibreTranslate dang lo ra host")

    def test_docs_reachable_through_proxy(self):
        status, _, _ = http(WEB + "/docs/")
        self.assertEqual(status, 200)


@skip_web
class TestFileThroughProxy(unittest.TestCase):
    def test_download_url_points_back_at_the_proxy(self):
        """LibreTranslate dung header Host de dung URL tuyet doi. Neu proxy khong
        giu Host, link tai ve se tro vao cong 5000 va hong khi chi mo UI."""
        content = b"Good morning. Nothing leaves this machine.\n"
        body, ctype = multipart({"source": "en", "target": "vi"},
                                ("file", "probe.txt", content))
        r = request(WEB + "/api/translate_file", raw=body,
                    headers={"Content-Type": ctype}, timeout=120)
        self.assertEqual(r.status, 200, r.text[:200])
        url = r.json()["translatedFileUrl"]

        self.assertIn(env("WEB_PORT", "5001"), url,
                      f"link tai ve khong di qua proxy: {url}")
        status, _, body = http(url)
        self.assertEqual(status, 200)
        self.assertTrue(body.strip())
        self.assertNotEqual(body.strip(), content.strip(), "tep khong he duoc dich")


class TestWebSourceFiles(unittest.TestCase):
    """Kiem tra tren dia — chay duoc ca khi container chua bat."""

    def test_nginx_config_preserves_host_header(self):
        conf = (ROOT / "web" / "nginx.conf").read_text()
        self.assertIn("proxy_set_header   Host $http_host", conf)
        self.assertIn("location /download_file/", conf,
                      "thieu proxy /download_file/ -> tai tep dich se 404")

    def test_compose_mounts_web_read_only(self):
        compose = (ROOT / "docker-compose.yml").read_text()
        self.assertIn("./web/html:/usr/share/nginx/html:ro", compose)
        self.assertIn("./web/nginx.conf:/etc/nginx/conf.d/default.conf:ro", compose)

    def test_web_port_differs_from_api_port(self):
        self.assertNotEqual(env("WEB_PORT", "5001"), env("HOST_PORT", "5000"))

    def test_nginx_listens_on_ipv6_too(self):
        """Trong container /etc/hosts co '::1 localhost'. Neu nginx chi bind IPv4
        thi client nao chon IPv6 truoc (busybox wget) se bi Connection refused."""
        conf = (ROOT / "web" / "nginx.conf").read_text()
        self.assertIn("listen       [::]:80;", conf)

    def test_upstreams_are_resolved_at_request_time(self):
        """nginx phan giai ten upstream mot lan luc nap config. Neu viet thang
        'proxy_pass http://engine:8000' ma container engine chua ton tai thi
        nginx khong khoi dong duoc va mat luon UI. Dung bien + resolver thi
        engine tat chi tra 502."""
        conf = (ROOT / "web" / "nginx.conf").read_text()
        self.assertIn("resolver 127.0.0.11", conf)
        # Bo dong chu thich: chinh phan giai thich co nhac 'proxy_pass http://...'
        code = "\n".join(l for l in conf.splitlines() if not l.lstrip().startswith("#"))
        hardcoded = re.findall(r"proxy_pass\s+(http://[a-z]+:\d+)", code)
        self.assertFalse(hardcoded,
                         f"proxy_pass viet cung ten host: {hardcoded} — "
                         f"dung 'set $var ...' de phan giai theo request")

    def test_healthcheck_does_not_rely_on_name_resolution(self):
        compose = (ROOT / "docker-compose.yml").read_text()
        # Cat tu 'web:' den khoa 'volumes:' o CAP GOC (khong thut dau) — service
        # web cung co khoa 'volumes:' rieng nen phai phan biet bang thut dau.
        block = compose[compose.index("  web:"):]
        block = block[:block.index("\nvolumes:")]
        self.assertNotIn("http://localhost/", block,
                         "healthcheck phai dung 127.0.0.1 — 'localhost' phan giai ca ::1")
        self.assertIn("http://127.0.0.1/", block)


def _dockerenv():
    import os
    env = dict(os.environ)
    env["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    env["DOCKER_CONFIG"] = str(ROOT / "docker-config")
    env.pop("DOCKER_CONTEXT", None)
    return env


def _docker_ok() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "version"], env=_dockerenv(),
                          capture_output=True, timeout=30).returncode == 0


class TestContainerHealth(unittest.TestCase):
    @unittest.skipUnless(_docker_ok(), "shell chua co quyen truy cap Docker Engine")
    def test_both_containers_report_healthy(self):
        for name in ("libretranslate", "lt-web"):
            with self.subTest(container=name):
                r = subprocess.run(
                    ["docker", "inspect", name, "--format", "{{.State.Health.Status}}"],
                    env=_dockerenv(), capture_output=True, text=True, timeout=30)
                if r.returncode != 0:
                    self.skipTest(f"{name} chua chay")
                self.assertEqual(r.stdout.strip(), "healthy",
                                 f"{name} khong healthy — docker inspect {name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ---------------------------------------------------------------------------
# Kiem thu trong trinh duyet that.
#
# Bo test tinh truoc day khong bat duoc mot ngoai le chua bat trong boot():
# ENGINES['auto'] la undefined -> doc .name nem loi -> boot() dut giua chung,
# nut dao chieu va danh sach ngon ngu khong bao gio duoc cap nhat, ma trang
# van "trong nhu binh thuong". Chi co chay that moi thay.
# ---------------------------------------------------------------------------
from tests import browser  # noqa: E402

_WHY = browser.available() or ([] if WEB_OK else [f"UI khong chay tai {WEB}"])


@unittest.skipIf(_WHY, " · ".join(_WHY))
class TestWebUiInRealBrowser(unittest.TestCase):
    res: dict = {}

    @classmethod
    def setUpClass(cls):
        with browser.brave(9799):
            cls.res = browser.run_driver(ROOT / "tests" / "e2e_webui.mjs", 9799, WEB)

    def test_driver_ran(self):
        self.assertTrue(self.res.get("ok"), f"driver loi: {self.res.get('error')}")

    def test_no_uncaught_exceptions_on_load(self):
        errs = self.res.get("consoleErrors", [])
        self.assertEqual(errs, [], "trang nem loi khi nap:\n  " + "\n  ".join(errs))

    def test_boot_completes(self):
        self.assertTrue(self.res.get("bootFinished"),
                        "boot() khong chay het — dong trang thai van rong")

    def test_sensible_defaults(self):
        self.assertEqual(self.res.get("defaultSource"), "auto")
        self.assertEqual(self.res.get("defaultEngine"), "auto")

    def test_swap_disabled_until_source_known(self):
        self.assertTrue(self.res.get("swapDisabledAtStart"),
                        "nguon la 'auto' va chua dich lan nao — nut dao chieu phai tat")
        self.assertTrue(self.res.get("swapEnabledAfter"),
                        "dich xong roi thi phai bat lai")

    def test_busy_state_is_visible_while_translating(self):
        """Khong co dau hieu nay, nguoi dung nhin thay ban dich CU va tuong
        do la ket qua cho cau vua go."""
        self.assertTrue(self.res.get("busyWhileTranslating"), "thieu trang thai dang dich")
        self.assertIn("đang dịch", self.res.get("busyLabel", ""))
        self.assertTrue(self.res.get("busyCleared"), "dich xong ma van con mo")

    def test_auto_engine_picks_envit5_for_en_vi(self):
        self.assertIn("EnViT5", self.res.get("engineUsed", ""))
        self.assertTrue(self.res.get("translation", "").strip())

    def test_same_language_option_is_disabled(self):
        self.assertTrue(self.res.get("sameLangOptionDisabled"),
                        "nguon=vi ma o dich van cho chon 'vi'")
        self.assertNotEqual(self.res.get("targetMovedOff"), "vi")

    def test_same_language_flips_instead_of_echoing(self):
        note = self.res.get("flipNote", "")
        self.assertIn("đã là vi", note, f"khong giai thich viec doi chieu: {note!r}")
        self.assertTrue(self.res.get("flipResult", "").strip())

    def test_history_has_a_clear_control(self):
        self.assertIn("mục gần đây", self.res.get("historyCount", ""))
        self.assertTrue(self.res.get("clearHistEnabled"))
