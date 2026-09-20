"""Test trinh doc PDF cua extension — CHAY THAT trong Brave headless.

Day la loai test da thieu truoc day: bo test tinh dat het trong khi extension
hong ngoai doi. Test nay nap extension vao trinh duyet that, boi den bang su
kien chuot that, bam nut, roi doc ban dich ra tu shadow DOM.

Tu bo qua neu khong co Brave/Node hoac may chu dich khong chay.

    python3 -m unittest tests.test_pdf_viewer -v
"""
from __future__ import annotations

import json
import unittest

from tests import browser
from tests.support import EXTENSION as EXT, ROOT, WEB as BASE, reachable

PDF_URL = BASE + "/test.pdf"


REASONS = browser.available()
if not reachable(PDF_URL):
    REASONS.append(f"khong tai duoc {PDF_URL} (may chu chua chay?)")


@unittest.skipIf(REASONS, " · ".join(REASONS))
class TestPdfViewerInRealBrowser(unittest.TestCase):
    result: dict = {}

    @classmethod
    def setUpClass(cls):
        port = 9788
        with browser.brave(port, extension=EXT):
            ext_id = browser.extension_id(port)
            if not ext_id:
                raise unittest.SkipTest("khong thay service worker cua extension")
            cls.result = browser.run_driver(
                ROOT / "tests" / "e2e_pdf.mjs", port, ext_id, PDF_URL)

    def test_driver_ran(self):
        self.assertTrue(self.result.get("ok"), f"driver loi: {self.result.get('error')}")

    def test_pdf_rendered(self):
        self.assertGreaterEqual(self.result.get("pages", 0), 1, "khong ve duoc trang nao")

    def test_text_layer_exists(self):
        """Khong co lop van ban thi khong the boi den — ca tinh nang vo nghia."""
        self.assertGreater(self.result.get("spans", 0), 0, "lop .textLayer rong")
        self.assertIn("Good morning", self.result.get("text", ""))

    def test_webassembly_is_permitted(self):
        """pdf.js dung WebAssembly cho JBIG2 (nen anh trong PDF quet), JPEG2000
        va quan ly mau. CSP mac dinh cua MV3 la script-src 'self' — chan WASM,
        va console bao 'neither wasm-eval nor unsafe-eval is an allowed source'.
        PDF chi co chu thi khong lo ra; PDF quet thi mat ca anh."""
        self.assertTrue(self.result.get("wasmAllowed"),
                        "CSP dang chan WebAssembly — them 'wasm-unsafe-eval'")

    def test_no_console_errors(self):
        self.assertEqual(self.result.get("consoleErrors", -1), 0)

    def test_no_console_warnings(self):
        self.assertEqual(self.result.get("consoleWarnings", -1), 0,
                         "warning cua pdf.js dang lot ra trang loi cua extension")

    def test_mouse_selection_works(self):
        self.assertTrue(self.result.get("selected", "").strip(),
                        "keo chuot tren lop van ban khong tao duoc vung boi den")

    def test_bubble_appears_on_selection(self):
        self.assertTrue(self.result.get("bubbleShown"), "khong hien nut Dich")

    def test_clicking_bubble_produces_a_translation(self):
        tr = self.result.get("translation", "")
        self.assertTrue(tr, "bam nut nhung khong ra ban dich")
        self.assertFalse(self.result.get("isError"), f"the bao loi: {tr}")
        self.assertNotEqual(tr.strip(), self.result.get("selected", "").strip(),
                            "ket qua y het dau vao — khong he duoc dich")


@unittest.skipIf(REASONS, " · ".join(REASONS))
class TestPdfSelection(unittest.TestCase):
    """Boi den trong lop van ban cua pdf.js, va cuon khong duoc lam mat ban dich.

    Chay rieng phien trinh duyet: gop chung voi test dich thi the ket qua con
    mo se che dung vung chu sap keo qua, lam phep thu vo nghia."""

    res: dict = {}

    @classmethod
    def setUpClass(cls):
        port = 9789
        with browser.brave(port, extension=EXT):
            ext_id = browser.extension_id(port)
            if not ext_id:
                raise unittest.SkipTest("khong thay service worker")
            cls.res = browser.run_driver(ROOT / "tests" / "e2e_pdf_select.mjs",
                                         port, ext_id, BASE + "/test-multi.pdf", timeout=240)

    def test_driver_ran(self):
        self.assertTrue(self.res.get("ok"), f"driver loi: {self.res.get('error')}")

    def test_each_text_layer_has_an_end_of_content(self):
        """pdf.js chia viec: thu vien ve span, VIEWER lo phan boi den. Thieu
        .endOfContent thi keo chuot hay nhay sang doan khac, copy ra sai chu."""
        self.assertGreater(self.res.get("textLayers", 0), 0)
        self.assertEqual(self.res.get("endOfContent"), self.res.get("textLayers"))

    def test_text_layer_lines_up_with_the_rendered_glyphs(self):
        """Doc pixel that tren canvas de tim mep phai cua chu, roi so voi mep
        phai cua span vo hinh.

        pdf.js 6.x doc bien CSS --total-scale-factor (ban cu la --scale-factor).
        Dat nham ten thi calc() trong textlayer.css hong, font-size cua span roi
        ve mac dinh 14px thay vi 20px, span ngan hon chu that toi ~150px. Hau qua:
        keo het dong nhin thay la da lan sang span ke tiep — nhin mot dang, copy
        ra mot neo."""
        rows = self.res.get("alignment")
        self.assertTrue(rows, "khong do duoc canh chinh")
        for r in rows:
            with self.subTest(span=r["span"], ink=r["ink"]):
                self.assertLessEqual(abs(r["gap"]), 8,
                                     f"lop chu lech {r['gap']}px so voi chu ve tren canvas")

    def test_selecting_class_toggles_with_the_drag(self):
        self.assertTrue(self.res.get("selectingDuringDrag"),
                        "dang keo ma khong co class 'selecting'")
        self.assertFalse(self.res.get("selectingAfterRelease"),
                         "nha chuot roi van con class 'selecting'")

    def test_multiline_selection_is_contiguous(self):
        self.assertGreaterEqual(self.res.get("lineCount", 0), 3,
                                f"keo qua nhieu dong ma chi lay duoc {self.res.get('lineCount')}")
        self.assertTrue(self.res.get("contiguous"),
                        f"cac dong lay duoc khong lien mach: {self.res.get('lineNumbers')}")

    def test_scrolling_does_not_close_the_translation(self):
        """Tren touchpad chi can hai ngon nhich nhe la cuon. Neu cuon dong the
        thi vua bam dich xong ban dich da bien mat, phai bam lai."""
        self.assertTrue(self.res.get("cardBeforeScroll"), "the khong hien sau khi bam")
        self.assertTrue(self.res.get("cardAfterScroll"),
                        "cuon trang lam mat ban dich")

    def test_scrolling_hides_the_bubble(self):
        self.assertFalse(self.res.get("bubbleAfterScroll"),
                         "nut neo theo vung chon nen phai an khi cuon")

    def test_escape_still_closes_the_card(self):
        """Va phai dong HAN: neu bam Esc trong luc dang dich ma khong huy yeu
        cau, ket qua ve muon se tu bat the len lai vai tram ms sau."""
        self.assertTrue(self.res.get("translationText"), "khong co ban dich de thu")
        self.assertFalse(self.res.get("cardAfterEscape"),
                         f"Esc khong dong duoc the: {self.res.get('cardStyleAfterEscape')}")


    def test_escape_cancels_a_translation_in_flight(self):
        """Bam Esc khi dang dich phai HUY han. Neu khong, vai tram ms sau ket
        qua ve va tu bat the len lai — nguoi dung tuong no khong chiu tat."""
        self.assertFalse(self.res.get("cardAfterEscapeMidFlight"),
                         "ban dich ve muon da tu mo lai the sau khi bam Esc")


    def test_reinjecting_replaces_instead_of_duplicating(self):
        """Khi extension duoc nap lai, Chrome khong tu chen content script vao
        tab dang mo — ta tu chen lai. Ban moi phai goi ban cu tu don (go het
        listener qua AbortController, xoa host), neu khong se co hai bo UI
        chong len nhau."""
        self.assertEqual(self.res.get("cleanupExposed"), "function",
                         "content.js khong lo ra ham don dep")
        self.assertEqual(self.res.get("hostsBefore"), 1)
        # Ban cu don sach; ban moi tao host theo kieu lazy nen ngay sau khi nap
        # co the la 0 — dieu quan trong la KHONG bao gio thanh 2.
        self.assertLessEqual(self.res.get("hostsAfterReinject", 9), 1,
                             "nap lan hai sinh them UI thu hai thay vi thay the")
        self.assertEqual(self.res.get("hostsAfterUse"), 1,
                         "dung lai sau khi nap lai phai co dung mot UI")
        self.assertTrue(self.res.get("bubbleAfterReinject"),
                        "ban vua nap khong hoat dong")


class TestPdfViewerFiles(unittest.TestCase):
    """Kiem tra tinh — chay duoc ca khi khong co trinh duyet."""

    def test_pdfjs_is_vendored_not_from_cdn(self):
        for rel in ("vendor/pdfjs/pdf.mjs", "vendor/pdfjs/pdf.worker.mjs",
                    "vendor/pdfjs/textlayer.css", "vendor/pdfjs/LICENSE"):
            with self.subTest(file=rel):
                self.assertTrue((EXT / rel).is_file(), f"thieu {rel}")
        html = (EXT / "viewer.html").read_text()
        self.assertNotIn("http://", html.replace('lang="vi"', ""))
        self.assertNotIn("cdn", (EXT / "viewer.js").read_text().lower())

    def test_font_and_cmap_data_present(self):
        """Thieu standard_fonts thi PDF dung Helvetica se khong ve duoc chu."""
        self.assertTrue((EXT / "vendor/pdfjs/standard_fonts").is_dir())
        self.assertTrue((EXT / "vendor/pdfjs/cmaps").is_dir())

    def test_viewer_reuses_the_same_selection_ui(self):
        """viewer.html nhung content.js -> nut va the dich giong het tren web."""
        html = (EXT / "viewer.html").read_text()
        for part in ("placement", "selection", "ui", "main"):
            with self.subTest(part=part):
                self.assertIn(f'src="content/{part}.js"', html)

    def test_scale_factor_is_set_for_text_alignment(self):
        """pdf.js dinh vi lop chu bang --scale-factor; thieu no chu se lech."""
        self.assertIn("--scale-factor", (EXT / "viewer.js").read_text())

    def test_csp_allows_wasm_but_not_eval(self):
        """'wasm-unsafe-eval' chi mo WebAssembly, KHONG mo eval() cho chuoi JS.
        Day la muc toi thieu pdf.js can."""
        m = json.loads((EXT / "manifest.json").read_text())
        csp = m.get("content_security_policy", {}).get("extension_pages", "")
        self.assertIn("wasm-unsafe-eval", csp)
        self.assertNotIn("'unsafe-eval'", csp.replace("'wasm-unsafe-eval'", ""))
        self.assertIn("script-src 'self'", csp)

    def test_viewer_quiets_document_warnings_but_keeps_errors(self):
        """pdf.js canh bao ve moi khiem khuyet cua tai lieu (vd font khai dung
        ham hinting ma khong dinh nghia). Do la loi cua tep PDF, nguoi dung
        khong sua duoc, va chung lam day trang loi trong brave://extensions."""
        src = (EXT / "viewer.js").read_text()
        self.assertIn("VerbosityLevel.ERRORS", src)
        self.assertIn("?debug=1", src, "phai con duong bat lai de chan doan")

    def test_wasm_decoders_are_vendored(self):
        wasm = EXT / "vendor" / "pdfjs" / "wasm"
        self.assertTrue(wasm.is_dir(), "thieu thu muc wasm -> PDF quet mat anh")

    def test_manifest_allows_local_files(self):
        m = json.loads((EXT / "manifest.json").read_text())
        self.assertIn("file:///*", m["host_permissions"])

    def test_broad_access_is_optional_not_granted_upfront(self):
        m = json.loads((EXT / "manifest.json").read_text())
        self.assertNotIn("<all_urls>", m["host_permissions"],
                         "khong duoc doi quyen doc moi trang web ngay tu dau")
        self.assertIn("<all_urls>", m.get("optional_host_permissions", []))

    def test_viewer_is_web_accessible(self):
        m = json.loads((EXT / "manifest.json").read_text())
        res = [r for e in m.get("web_accessible_resources", []) for r in e["resources"]]
        self.assertIn("viewer.html", res)

    def test_context_menu_offers_viewer_on_pdf_pages(self):
        bg = (EXT / "background.js").read_text()
        self.assertIn("documentUrlPatterns", bg)
        self.assertIn("*://*/*.pdf", bg)
        self.assertIn("viewer.html", bg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
