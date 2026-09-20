"""Test doc thanh tieng trong TRINH DUYET THAT (Brave/Chromium headless).

Vi sao phai co tang nay: test tinh va test may chu deu dat trong khi nut Doc
van co the im lang. Am thanh di qua nhieu lop ma chi trinh duyet moi co —
CSP media-src, chinh sach tu dong phat, tai lieu offscreen cua MV3 — va khong
lop nao trong so do nhin thay duoc tu Python.

    python3 -m unittest tests.test_tts_browser -v
"""
from __future__ import annotations

import unittest

from tests import browser
from tests.support import EXTENSION as EXT, ROOT, TTS, WEB, request

WHY = browser.available()


def _tts_up() -> bool:
    try:
        r = request(TTS + "/health", timeout=5)
        return r.status == 200 and r.json().get("voices", 0) > 0
    except (OSError, ValueError):
        return False


needs_browser = unittest.skipIf(WHY, f"khong chay duoc trinh duyet: {WHY}")
needs_tts = unittest.skipUnless(_tts_up(), f"may doc chua bat tai {TTS}")


@needs_browser
@needs_tts
class TestReaderOnWebUi(unittest.TestCase):
    """Mot phien trinh duyet cho ca lop: moi phien ton ~30 giay."""

    res: dict

    @classmethod
    def setUpClass(cls):
        port = 9351
        with browser.brave(port):
            cls.res = browser.run_driver(
                ROOT / "tests" / "e2e_tts_web.mjs", port, WEB, timeout=300)

    def setUp(self):
        if not self.res.get("ok"):
            self.fail(f"driver hong: {self.res.get('error')}")

    def test_hien_bo_dieu_khien_khi_may_doc_bat(self):
        self.assertTrue(self.res["rateVisible"], "o chon toc do van an")
        self.assertTrue(self.res["readinVisible"])
        self.assertTrue(self.res["readoutVisible"])

    def test_tat_nut_khi_chua_co_chu(self):
        self.assertTrue(self.res["readoutDisabledWhenEmpty"])

    def test_bat_nut_sau_khi_co_ban_dich(self):
        self.assertTrue(self.res["translation"], "chua dich duoc gi")
        self.assertTrue(self.res["readoutEnabledAfter"])

    def test_bam_doc_thi_goi_may_chu_va_phat_that(self):
        self.assertGreaterEqual(self.res["speaks"], 1, "khong goi /api3/speak lan nao")
        self.assertGreaterEqual(len(self.res["plays"]), 1, "khong phat lan nao")
        self.assertIsNone(self.res["playError"],
                          f"trinh duyet tu choi phat: {self.res['playError']}")

    def test_phat_bang_blob_url(self):
        """Neu khong phai blob: thi am thanh dang di duong khac — vd tai
        truc tiep tu URL, se mat kha nang huy giua chung."""
        self.assertTrue(self.res["blobUrlUsed"], self.res["plays"])

    def test_nhan_nut_doi_khi_dang_doc(self):
        self.assertEqual(self.res["labelWhilePlaying"], "Dừng")

    def test_bam_lai_thi_dung(self):
        self.assertEqual(self.res["labelAfterStop"], "Đọc")

    def test_van_ban_dai_duoc_cat_thanh_nhieu_doan(self):
        """Mot yeu cau duy nhat cho 2000 ky tu mat ~10 giay moi ra tieng.
        Cat nho thi tieng bat dau sau ~1 giay."""
        self.assertGreaterEqual(self.res["chunkedSpeaks"], 2,
                                "van ban dai van duoc goi trong mot lan")

    def test_khong_vi_pham_csp(self):
        self.assertEqual(self.res["cspViolations"], [],
                         "CSP chan — kiem tra media-src trong nginx.conf")

    def test_khong_co_loi_console(self):
        self.assertEqual(self.res["consoleErrors"], [])


@needs_browser
@needs_tts
class TestReaderOnExtensionCard(unittest.TestCase):
    """Duong day du: content script -> service worker -> offscreen -> phat ->
    bao nguoc -> doi nhan nut."""

    res: dict

    @classmethod
    def setUpClass(cls):
        port = 9352
        with browser.brave(port, extension=EXT):
            cls.res = browser.run_driver(
                ROOT / "tests" / "e2e_tts_card.mjs", port, WEB, timeout=300)

    def setUp(self):
        if not self.res.get("ok"):
            self.fail(f"driver hong: {self.res.get('error')}")

    def test_the_dich_hien_ra(self):
        self.assertTrue(self.res["bubbleShown"])
        self.assertTrue(self.res["cardShown"])

    def test_co_ca_nut_doc_goc_va_doc_ban_dich(self):
        sides = {b["side"]: b for b in self.res["buttonsOnCard"]}
        self.assertIn("src", sides)
        self.assertIn("out", sides)
        for side, b in sides.items():
            self.assertFalse(b["hidden"], f"nut '{side}' bi an du co giong")

    def test_bam_doc_thi_doi_nhan(self):
        self.assertEqual(self.res["labelWhileReading"], "Dừng")

    def test_tao_duoc_tai_lieu_offscreen(self):
        """Khong co no thi service worker cua MV3 khong phat duoc am thanh."""
        self.assertTrue(self.res["offscreenTarget"],
                        "khong tim thay offscreen.html trong danh sach target")

    def test_yeu_cau_that_su_den_may_chu(self):
        self.assertTrue(self.res["serverGotRequest"],
                        f"bo dem khong tang: {self.res['cacheBefore']} -> "
                        f"{self.res['cacheAfter']}")

    def test_nhan_tu_tro_ve_khi_doc_xong(self):
        """Day la doan duy nhat chung minh duong bao nguoc con song:
        offscreen -> service worker -> chrome.tabs.sendMessage -> content script.
        Dut o dau thi nut se ket o 'Dung' vinh vien."""
        self.assertIsNotNone(self.res["labelRestored"],
                             "nut ket o 'Dừng' — duong bao nguoc bi dut")
        self.assertEqual(self.res["labelRestored"]["label"], "Đọc bản dịch")

    def test_khong_co_loi_console(self):
        self.assertEqual(self.res["consoleErrors"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
