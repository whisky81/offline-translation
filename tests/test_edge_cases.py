"""Ca xau va ca bien.

Moi khang dinh o day deu do bang cach GOI THAT vao may chu roi ghi lai hanh vi,
khong phai doan. Vai cho ghi ro "day la han che cua upstream" de sau nay doc lai
con biet vi sao lai chap nhan.

    python3 -m unittest tests.test_edge_cases -v
"""
from __future__ import annotations

import json
import subprocess
import unittest

from tests.support import (EXTENSION, ROOT, WEB, multipart, reachable, request,
                           translate)

LT = WEB + "/api"          # LibreTranslate qua proxy
ENG = WEB + "/api2"        # EnViT5 qua proxy

needs_web = unittest.skipUnless(reachable(WEB + "/"), f"UI khong chay tai {WEB}")
needs_engine = unittest.skipUnless(reachable(ENG + "/health"), "EnViT5 chua bat")


@needs_web
class TestLibreTranslateBadInput(unittest.TestCase):
    """Dau vao hong phai bi tu choi ro rang, khong duoc lam sap may chu."""

    def test_missing_q_is_rejected(self):
        for q in ("", [], None):
            with self.subTest(q=q):
                r = translate(LT, q, "vi", "en")
                self.assertEqual(r.status, 400)
                self.assertIn("q", r.json()["error"])

    def test_whitespace_only_returns_empty_not_error(self):
        r = translate(LT, "   \t\n  ", "vi", "en")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.json()["translatedText"].strip(), "")

    def test_missing_target_is_rejected(self):
        r = request(LT + "/translate", data={"q": "hi", "source": "en", "format": "text"})
        self.assertEqual(r.status, 400)
        self.assertIn("target", r.json()["error"])

    def test_unknown_language_is_rejected(self):
        r = translate(LT, "hi", "vi", "xx")
        self.assertEqual(r.status, 400)
        self.assertIn("xx", r.json()["error"])

    def test_unknown_format_is_rejected(self):
        r = translate(LT, "hi", "vi", "en", fmt="markdown")
        self.assertEqual(r.status, 400)

    def test_malformed_json_is_rejected(self):
        r = request(LT + "/translate", raw=b"{ khong phai json",
                    headers={"Content-Type": "application/json"})
        self.assertEqual(r.status, 400)

    def test_numeric_q_is_an_upstream_bug(self):
        """LibreTranslate tra 500 khi `q` la so thay vi 400.

        Day la han che cua upstream, khong phai cua ta — moi client trong du an
        nay deu gui chuoi hoac mang chuoi. Ghi lai de neu ban moi sua duoc thi
        test nay do va ta biet ma cap nhat tai lieu."""
        r = translate(LT, 123, "vi", "en")
        self.assertEqual(r.status, 500,
                         "upstream da sua? cap nhat docs/issues.md")


@needs_web
class TestLibreTranslateOddText(unittest.TestCase):
    """Van ban ky quac van phai ra ket qua, khong duoc vo."""

    def test_punctuation_only(self):
        r = translate(LT, "!!! ??? ...", "vi", "en")
        self.assertEqual(r.status, 200)

    def test_very_long_single_word(self):
        r = translate(LT, "a" * 600, "vi", "en")
        self.assertEqual(r.status, 200)

    def test_emoji_passes_through(self):
        r = translate(LT, "🎉🎉🎉", "vi", "en")
        self.assertEqual(r.status, 200)
        self.assertIn("🎉", r.json()["translatedText"])

    def test_control_characters_do_not_crash(self):
        r = translate(LT, "hi\x00\x01there", "vi", "en")
        self.assertLess(r.status, 500)

    def test_large_batch(self):
        """LT_BATCH_LIMIT=-1 nen mang dai khong bi chan."""
        items = [f"line number {i}" for i in range(120)]
        r = translate(LT, items, "vi", "en")
        self.assertEqual(r.status, 200)
        self.assertEqual(len(r.json()["translatedText"]), 120)

    def test_long_paragraph(self):
        r = translate(LT, "The server runs entirely on local hardware. " * 80, "vi", "en")
        self.assertEqual(r.status, 200)
        self.assertGreater(len(r.json()["translatedText"]), 200)


@needs_engine
class TestEngineBadInput(unittest.TestCase):
    """EnViT5 la may chu tu viet — day la noi de sinh loi 500/502 nhat."""

    def test_non_string_q_is_rejected_not_crashed(self):
        """Truoc day list(123) nem TypeError, handler chet, nginx tra 502."""
        for q in (123, {"a": 1}, ["hi", 5], True):
            with self.subTest(q=q):
                r = translate(ENG, q, "vi", "en")
                self.assertEqual(r.status, 400, f"phai tu choi tu te, nhan {r.status}")
                self.assertIn("chuoi", r.json()["error"])

    def test_empty_items_are_preserved_not_turned_into_junk(self):
        """Dua "en: " vao model sinh ra rac (thuong la dau hai cham) chu khong
        phai chuoi rong — nen phan tu rong phai duoc bo qua."""
        r = translate(ENG, ["", "hello", "  "], "vi", "en")
        self.assertEqual(r.status, 200)
        out = r.json()["translatedText"]
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0], "")
        self.assertTrue(out[1].strip())
        self.assertNotIn(":", out[0])

    def test_all_empty_batch_is_rejected(self):
        r = translate(ENG, ["", "   "], "vi", "en")
        self.assertEqual(r.status, 400)

    def test_unsupported_pair_is_rejected_clearly(self):
        for target in ("ja", "ko", "zh-Hans"):
            with self.subTest(target=target):
                r = translate(ENG, "hello", target, "en")
                self.assertEqual(r.status, 400)
                self.assertIn("en<->vi", r.json()["error"])

    def test_same_language_is_rejected(self):
        r = translate(ENG, "hello", "en", "en")
        self.assertEqual(r.status, 400)

    def test_cjk_with_auto_source_is_refused_not_guessed(self):
        """Heuristic 'khong co dau tieng Viet => tieng Anh' se coi tieng Nhat
        la tieng Anh va tra ve rac. Phai tu choi thay vi doan."""
        for text in ("今日はいい天気です", "안녕하세요", "今天天气很好"):
            with self.subTest(text=text[:6]):
                r = translate(ENG, text, "vi", "auto")
                self.assertEqual(r.status, 400)
                self.assertIn("Han/Kana/Hangul", r.json()["error"])

    def test_malformed_json_is_rejected(self):
        r = request(ENG + "/translate", raw=b"{ hong",
                    headers={"Content-Type": "application/json"})
        self.assertEqual(r.status, 400)

    def test_wrong_method_and_path(self):
        self.assertEqual(request(ENG + "/translate").status, 404)   # GET
        self.assertEqual(request(ENG + "/khong-co").status, 404)

    def test_html_format_is_refused(self):
        r = translate(ENG, "<p>hi</p>", "vi", "en", fmt="html")
        self.assertEqual(r.status, 400)
        self.assertIn("HTML", r.json()["error"])

    def test_long_text_still_answers(self):
        r = translate(ENG, "The server runs locally. " * 120, "vi", "en")
        self.assertEqual(r.status, 200)
        self.assertTrue(r.json()["translatedText"].strip())


@needs_web
class TestProxyEdges(unittest.TestCase):
    def test_unknown_path_is_404(self):
        self.assertEqual(request(WEB + "/khong-co-trang-nay").status, 404)

    def _upload(self, filename: str, content: bytes):
        body, ctype = multipart({"source": "en", "target": "vi"}, ("file", filename, content))
        return request(WEB + "/api/translate_file", raw=body,
                       headers={"Content-Type": ctype}, timeout=120)

    def test_empty_file_is_accepted_and_returns_a_link(self):
        """Tep rong khong bi coi la loi — van tra ve link tep da 'dich'.
        Ghi lai vi day la hanh vi de ngo nhan la hong."""
        r = self._upload("empty.txt", b"")
        self.assertEqual(r.status, 200)
        self.assertIn("translatedFileUrl", r.json())

    def test_unsupported_extension_is_rejected(self):
        for name in ("a.xyz", "noext"):
            with self.subTest(name=name):
                r = self._upload(name, b"hello")
                self.assertEqual(r.status, 400)
                self.assertIn("format not supported", r.json()["error"])

    def test_supported_extension_works(self):
        r = self._upload("ok.txt", b"Hello there.")
        self.assertEqual(r.status, 200)

    def test_engine_down_gives_502_not_a_dead_ui(self):
        """nginx phan giai upstream theo tung request. Neu viet cung ten host,
        engine chua ton tai se lam nginx khong khoi dong duoc va mat ca UI."""
        conf = (ROOT / "web" / "nginx.conf").read_text()
        self.assertIn("resolver 127.0.0.11", conf)
        # UI van song dong thoi voi /api2 co the 502
        self.assertEqual(request(WEB + "/").status, 200)


class TestEngineSelectionEdges(unittest.TestCase):
    """Logic chon engine — chay that bang Node, khong can trinh duyet."""

    @classmethod
    def setUpClass(cls):
        script = f"""
import {{ pickEngine, engineHandles, normLang }} from "{EXTENSION / 'common.js'}";
const cases = {{
  unknownEngineKey: engineHandles("khong-co", "en", "vi"),
  autoWithRestricted: engineHandles("hf", "auto", "vi"),
  zhAlias: engineHandles("hf", "zh", "vi"),
  normUndefined: String(normLang(undefined)),
  normEmpty: String(normLang("")),
  prefUnknown: pickEngine("khong-co", "en", "vi").key,
  sameLangPair: engineHandles("hf", "en", "en"),
  ltAlwaysTrue: engineHandles("lt", "ja", "ko"),
}};
console.log(JSON.stringify(cases));
"""
        r = subprocess.run(["node", "--input-type=module", "-e", script],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise unittest.SkipTest(f"node loi: {r.stderr[:200]}")
        cls.v = json.loads(r.stdout)

    def test_unknown_engine_key_never_claims_support(self):
        self.assertFalse(self.v["unknownEngineKey"])

    def test_unknown_preference_falls_back_to_libretranslate(self):
        self.assertEqual(self.v["prefUnknown"], "lt")

    def test_auto_source_never_matches_restricted_engine(self):
        self.assertFalse(self.v["autoWithRestricted"])

    def test_zh_alias_is_not_mistaken_for_a_supported_pair(self):
        self.assertFalse(self.v["zhAlias"], "EnViT5 khong biet tieng Trung")

    def test_same_language_pair_is_not_supported(self):
        self.assertFalse(self.v["sameLangPair"])

    def test_unrestricted_engine_accepts_anything(self):
        self.assertTrue(self.v["ltAlwaysTrue"])

    def test_normalising_odd_values_does_not_throw(self):
        self.assertEqual(self.v["normUndefined"], "undefined")
        self.assertEqual(self.v["normEmpty"], "")


class TestPlacementEdges(unittest.TestCase):
    """Toan dat vi tri — chay bang Node voi window gia lap."""

    @classmethod
    def setUpClass(cls):
        src = (EXTENSION / "content" / "placement.js").read_text()
        script = f"""
globalThis.window = {{ innerWidth: 1000, innerHeight: 700 }};
{src}
const P = window.DichOffline.placement;
const mk = (w, h) => {{
  const st = {{}};
  return {{ style: st, getBoundingClientRect: () => ({{ width: w, height: h }}),
           at: () => [parseFloat(st.left), parseFloat(st.top)] }};
}};
const out = {{}};
// vung chon to hon ca khung nhin
let el = mk(380, 145);
P.placeCard(el, {{ left: -200, top: -100, right: 1400, bottom: 900, width: 1600, height: 1000 }});
out.hugeRect = el.at();
// vung chon kich thuoc 0
el = mk(380, 145);
P.placeCard(el, {{ left: 500, top: 350, right: 500, bottom: 350, width: 0, height: 0 }});
out.zeroRect = el.at();
// the to hon khung nhin
el = mk(2000, 2000);
P.placeCard(el, {{ left: 10, top: 10, right: 100, bottom: 30, width: 90, height: 20 }});
out.oversizeCard = el.at();
// nut sat mep phai
el = mk(70, 30);
P.placeBubble(el, {{ left: 900, top: 20, right: 995, bottom: 40, width: 95, height: 20 }});
out.bubbleAtRightEdge = el.at();
console.log(JSON.stringify(out));
"""
        r = subprocess.run(["node", "--input-type=module", "-e", script],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise unittest.SkipTest(f"node loi: {r.stderr[:300]}")
        cls.v = json.loads(r.stdout)

    def _inside(self, xy, w, h):
        x, y = xy
        self.assertGreaterEqual(x, 0, f"tran trai: {xy}")
        self.assertGreaterEqual(y, 0, f"tran tren: {xy}")

    def test_rect_bigger_than_viewport(self):
        self._inside(self.v["hugeRect"], 380, 145)

    def test_zero_size_rect(self):
        self._inside(self.v["zeroRect"], 380, 145)

    def test_card_bigger_than_viewport_is_clamped_to_origin(self):
        x, y = self.v["oversizeCard"]
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)

    def test_bubble_near_right_edge_stays_visible(self):
        x, y = self.v["bubbleAtRightEdge"]
        self.assertLessEqual(x + 70, 1000, f"nut tran phai: {x}")
        self.assertGreaterEqual(x, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
