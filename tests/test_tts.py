"""Test may doc (Piper) va phan doc thanh tieng cua web UI + extension.

Phan goi may chu tu bo qua neu may doc chua bat; phan kiem tra ma nguon thi
luon chay.

    python3 -m unittest tests.test_tts -v
"""
from __future__ import annotations

import io
import json
import unittest
import uuid
import wave

from tests.support import (EXTENSION as EXT, ROOT, TTS, extension_sources,
                           reachable, request)

def _tts_up() -> bool:
    """reachable() coi 404 la 'song' (no chi loai >= 500). Khi nginx chua nap
    lai cau hinh, /api3/health tra 404 va ca bo test se chay roi that bai hang
    loat thay vi bo qua. Doi hoi dung 200 + than JSON co giong."""
    try:
        r = request(TTS + "/health", timeout=5)
        return r.status == 200 and r.json().get("voices", 0) > 0
    except (OSError, ValueError):
        return False


needs_tts = unittest.skipUnless(_tts_up(), f"may doc chua bat tai {TTS}")


def speak(**body):
    return request(TTS + "/speak", data=body, timeout=180)


def wav_info(blob: bytes) -> tuple[int, int, int]:
    """(so mau, tan so, so kenh) — doc that tu tep chu khong tin header HTTP."""
    with wave.open(io.BytesIO(blob)) as w:
        return w.getnframes(), w.getframerate(), w.getnchannels()


# ---------------------------------------------------------------- may chu
@needs_tts
class TestTtsService(unittest.TestCase):
    def test_health_liet_ke_ngon_ngu(self):
        r = request(TTS + "/health")
        self.assertEqual(r.status, 200)
        h = r.json()
        self.assertEqual(h["status"], "ok")
        self.assertGreater(h["voices"], 0)
        self.assertIn("vi", h["languages"])

    def test_voices_co_du_thong_tin_chon_giong(self):
        voices = request(TTS + "/voices").json()
        self.assertTrue(voices)
        for v in voices:
            for key in ("id", "lang", "locale", "sample_rate"):
                self.assertIn(key, v, f"giong {v.get('id')} thieu '{key}'")
            # Duong dan tep tren may chu khong duoc lo ra ngoai.
            self.assertNotIn("path", v)

    def test_info_ghi_ro_giay_phep(self):
        info = request(TTS + "/info").json()
        self.assertEqual(info["engine"], "piper")
        self.assertIn("GPL-3.0", info["license"])

    def test_doc_tieng_viet_ra_wav_that(self):
        r = speak(q="Xin chào, đây là một câu thử.", lang="vi")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers["Content-Type"], "audio/wav")
        self.assertEqual(r.headers["X-Lang"], "vi")
        frames, rate, channels = wav_info(r.body)
        self.assertGreater(frames, 0, "tep WAV khong co mau nao")
        self.assertEqual(channels, 1)
        # Mot cau nhu vay phai dai hon nua giay; ngan hon la dau hieu bi cat.
        self.assertGreater(frames / rate, 0.5)

    def test_header_khop_voi_noi_dung_tep(self):
        r = speak(q="Kiểm tra độ dài.", lang="vi")
        frames, rate, _ = wav_info(r.body)
        self.assertAlmostEqual(float(r.headers["X-Seconds"]), frames / rate, places=2)
        self.assertEqual(int(r.headers["Content-Length"]), len(r.body))

    def test_lan_hai_lay_tu_bo_dem(self):
        # Van ban phai MOI moi lan chay. Dung chuoi co dinh thi lan chay truoc
        # da nap no vao bo dem, va "lan dau" se tra ve X-Cached: 1 ngay.
        body = {"q": f"Câu này đọc hai lần, lần chạy {uuid.uuid4().hex[:8]}.",
                "lang": "vi"}
        first = speak(**body)
        second = speak(**body)
        self.assertEqual(first.headers["X-Cached"], "0")
        self.assertEqual(second.headers["X-Cached"], "1")
        self.assertEqual(first.body, second.body)

    def test_toc_do_doi_do_dai(self):
        slow = speak(q="Một câu để đo tốc độ.", lang="vi", speed=0.5)
        fast = speak(q="Một câu để đo tốc độ.", lang="vi", speed=2.0)
        self.assertGreater(float(slow.headers["X-Seconds"]),
                           float(fast.headers["X-Seconds"]) * 1.3)

    def test_toc_do_ngoai_khoang_bi_ke_lai(self):
        # 99 phai cho ra dung ket qua nhu 2.0 — neu khong, gioi han khong chay.
        at_max = speak(q="Ghim tốc độ.", lang="vi", speed=2.0)
        beyond = speak(q="Ghim tốc độ.", lang="vi", speed=99)
        self.assertEqual(at_max.body, beyond.body)
        at_min = speak(q="Ghim tốc độ.", lang="vi", speed=0.5)
        below = speak(q="Ghim tốc độ.", lang="vi", speed=-5)
        self.assertEqual(at_min.body, below.body)

    def test_chon_giong_bang_id(self):
        vid = request(TTS + "/voices").json()[0]["id"]
        r = speak(q="Chọn giọng trực tiếp.", voice=vid)
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers["X-Voice"], vid)

    def test_ma_ngon_ngu_co_vung(self):
        self.assertEqual(speak(q="Có vùng.", lang="vi-VN").status, 200)

    def test_cat_van_ban_qua_dai_va_bao_lai(self):
        limit = request(TTS + "/info").json()["max_chars"]
        r = speak(q="Câu dài. " * (limit // 4), lang="vi")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers["X-Truncated"], "1")
        self.assertEqual(int(r.headers["X-Chars"]), limit)


@needs_tts
class TestTtsBadInput(unittest.TestCase):
    """Moi dau vao hong phai ra 400 kem thong bao doc duoc — khong phai 500,
    khong phai 502, va khong phai mot tep WAV rong."""

    def assert400(self, **body):
        r = speak(**body)
        self.assertEqual(r.status, 400, f"{body} -> {r.status} {r.text[:120]}")
        self.assertTrue(r.json().get("error"), "loi 400 ma khong co thong bao")
        return r.json()["error"]

    def test_q_rong(self):
        self.assert400(q="", lang="vi")
        self.assert400(q="   \n\t  ", lang="vi")

    def test_q_sai_kieu(self):
        for bad in (123, 1.5, True, None, ["a"], {"x": 1}):
            with self.subTest(q=bad):
                self.assertIn("chuoi", self.assert400(q=bad, lang="vi"))

    def test_thieu_ngon_ngu(self):
        self.assert400(q="xin chào")

    def test_ngon_ngu_chua_co_giong(self):
        msg = self.assert400(q="xin chào", lang="ja")
        self.assertIn("ja", msg)

    def test_giong_khong_ton_tai(self):
        self.assert400(q="xin chào", voice="khong-co-giong-nay")

    def test_speed_sai_kieu(self):
        self.assert400(q="xin chào", lang="vi", speed="nhanh")
        self.assert400(q="xin chào", lang="vi", speed=True)

    def test_van_ban_khong_co_chu(self):
        # Truoc day cac chuoi nay cho ra WAV rong: bam Doc, khong nghe gi,
        # khong bao gi. Gio phai tu choi ro rang.
        for junk in ("... !!! ???", "🙂🙂🙂", "—–-", "   ...   "):
            with self.subTest(q=junk):
                self.assert400(q=junk, lang="vi")

    def test_than_khong_phai_json(self):
        r = request(TTS + "/speak", raw=b"khong phai json",
                    headers={"Content-Type": "application/json"})
        self.assertEqual(r.status, 400)

    def test_than_la_mang(self):
        r = request(TTS + "/speak", data=[1, 2, 3])
        self.assertEqual(r.status, 400)

    def test_endpoint_la(self):
        self.assertEqual(request(TTS + "/khong-co").status, 404)
        self.assertEqual(request(TTS + "/khong-co", data={}).status, 404)

    def test_ky_tu_dieu_khien_bi_loai_chu_khong_lam_hong(self):
        r = speak(q="Xin\x00chào\x07 bạn.", lang="vi")
        self.assertEqual(r.status, 200)


@needs_tts
class TestTtsSurface(unittest.TestCase):
    def test_khong_co_header_cors(self):
        """Giong /api va /api2: khong trang web nao duoc goi may doc nay."""
        r = speak(q="Kiểm tra CORS.", lang="vi")
        for h in r.headers:
            self.assertFalse(h.lower().startswith("access-control-"),
                             f"lo header CORS: {h}")

    def test_nosniff(self):
        r = speak(q="Kiểm tra nosniff.", lang="vi")
        self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")

    def test_khong_mo_cong_rieng(self):
        """May doc chi duoc tiep can qua nginx, khong co cong cua rieng."""
        from tests.support import reachable as ok
        self.assertFalse(ok("http://127.0.0.1:8100/health", timeout=2),
                         "cong 8100 khong duoc cong bo ra host")


# ------------------------------------------------------------- ma nguon
class TestTtsWiring(unittest.TestCase):
    """Chay duoc ke ca khi may doc dang tat."""

    def test_hai_ban_tts_js_giong_het_nhau(self):
        """web/html/js/tts.js va extension/tts.js la ban sao cua nhau.

        Day la cho de troi ra nhau nhat: sua bug o mot ben, ben kia van hong.
        So sanh tung byte de khong the quen."""
        web = (ROOT / "web/html/js/tts.js").read_bytes()
        ext = (ROOT / "extension/tts.js").read_bytes()
        self.assertEqual(web, ext,
                         "web/html/js/tts.js va extension/tts.js da khac nhau — "
                         "chep de len nhau roi chay lai test")

    def test_nginx_proxy_api3(self):
        conf = (ROOT / "web/nginx.conf").read_text()
        self.assertIn("location /api3/", conf)
        self.assertIn("http://tts:8100", conf)
        # Phai dung bien + resolver, nhu /api2: neu khong, may doc tat la
        # nginx khong khoi dong duoc va mat luon ca UI.
        self.assertIn("set                $tts", conf)
        block = conf.split("location /api3/")[1].split("location /")[0]
        self.assertIn("proxy_hide_header Access-Control-Allow-Origin", block)

    def test_csp_cho_phep_blob_media(self):
        """UI phat am thanh bang blob: URL. Thieu media-src thi no thua ke
        default-src 'self' va trinh duyet chan, nut Doc im lang."""
        conf = (ROOT / "web/nginx.conf").read_text()
        self.assertIn("media-src 'self' blob:", conf)

    def test_compose_khong_cong_bo_cong_tts(self):
        compose = (ROOT / "docker-compose.yml").read_text()
        self.assertIn("  tts:", compose)
        block = compose.split("  tts:")[1].split("\n  web:")[0]
        self.assertIn('expose:', block)
        self.assertNotIn("ports:", block)
        self.assertIn("no-new-privileges:true", block)

    def test_manifest_co_quyen_offscreen(self):
        m = json.loads((EXT / "manifest.json").read_text())
        self.assertIn("offscreen", m["permissions"],
                      "thieu quyen 'offscreen' thi khong phat duoc am thanh")

    def test_offscreen_loc_thu_goi_dich_danh_cho_minh(self):
        """Khong loc thi tai lieu offscreen se nhan ca thu no tu gui di."""
        src = (EXT / "offscreen.js").read_text()
        self.assertIn('msg?.target !== "offscreen"', src)

    def test_background_khong_cuop_thu_cua_offscreen(self):
        src = (EXT / "background.js").read_text()
        self.assertIn('msg?.target === "offscreen"', src)

    def test_content_script_khong_tu_phat_am_thanh(self):
        """Phat trong trang se dinh CSP media-src cua trang. Viec phat phai
        nam o tai lieu offscreen."""
        for name, src in extension_sources().items():
            if not name.startswith("content/"):
                continue
            code = "\n".join(l for l in src.splitlines()
                             if not l.strip().startswith(("//", "*", "/*")))
            self.assertNotIn("new Audio", code, f"{name} tu tao the audio")
            self.assertNotIn("/api3", code, f"{name} goi thang may doc")

    def test_env_example_co_cau_hinh_giong(self):
        ex = (ROOT / ".env.example").read_text()
        self.assertIn("TTS_VOICES=", ex)
        self.assertIn("vi_VN", ex, "phai co san mot giong tieng Viet")


if __name__ == "__main__":
    unittest.main(verbosity=2)
