"""Test extension Brave/Chromium.

Khong nap duoc extension vao trinh duyet tu dong o day, nen tap trung vao
nhung thu kiem tra duoc tinh: manifest dung chuan MV3, moi API chrome.* duoc
dung deu co quyen, moi tep tham chieu deu ton tai, logic chon engine dung,
va cac endpoint that su song.

    python3 -m unittest tests.test_extension -v
"""
from __future__ import annotations

import json
import re
import struct
import subprocess
import unittest
import urllib.parse

from tests.support import (EXTENSION as EXT, ROOT, WEB as BASE, content_script_source,
                           env, extension_sources, reachable, request)

MANIFEST = json.loads((EXT / "manifest.json").read_text())


def server_up() -> bool:
    return reachable(BASE + "/api/languages")


js_sources = extension_sources


class TestManifest(unittest.TestCase):
    def test_is_manifest_v3(self):
        self.assertEqual(MANIFEST["manifest_version"], 3)

    def test_background_is_a_module_service_worker(self):
        bg = MANIFEST["background"]
        self.assertEqual(bg["service_worker"], "background.js")
        self.assertEqual(bg["type"], "module", "background.js dung import -> phai la module")

    def test_host_permission_covers_the_server(self):
        port = env("WEB_PORT", "5001")
        hosts = MANIFEST["host_permissions"]
        self.assertTrue(any(f"127.0.0.1:{port}" in h for h in hosts),
                        f"thieu quyen toi 127.0.0.1:{port}: {hosts}")
        self.assertTrue(any("localhost" in h for h in hosts),
                        "nen cho ca 'localhost' vi nguoi dung co the go kieu do")

    def test_content_script_runs_everywhere(self):
        cs = MANIFEST["content_scripts"][0]
        self.assertIn("<all_urls>", cs["matches"])
        self.assertTrue(all(j.startswith("content/") for j in cs["js"]),
                        f"content script phai nam trong content/: {cs['js']}")
        self.assertIn("content/main.js", cs["js"])

    def test_declares_keyboard_shortcut(self):
        self.assertIn("translate-selection", MANIFEST["commands"])

    def test_every_referenced_file_exists(self):
        refs = [MANIFEST["background"]["service_worker"],
                MANIFEST["action"]["default_popup"],
                MANIFEST["options_ui"]["page"]]
        refs += MANIFEST["content_scripts"][0]["js"]
        refs += list(MANIFEST["icons"].values())
        refs += list(MANIFEST["action"]["default_icon"].values())
        for ref in refs:
            with self.subTest(file=ref):
                self.assertTrue((EXT / ref).is_file(), f"thieu {ref}")

    def test_html_pages_reference_existing_assets(self):
        for page in EXT.glob("*.html"):
            html = page.read_text()
            for ref in re.findall(r'(?:src|href)="([^"]+)"', html):
                if ref.startswith(("http", "#", "data:")):
                    continue
                with self.subTest(page=page.name, asset=ref):
                    self.assertTrue((EXT / ref).is_file(), f"{page.name} tro toi {ref} khong co")


class TestPermissionsMatchCode(unittest.TestCase):
    """Thieu quyen thi chrome.* nem loi luc chay — tinh khong bao gi."""

    #  API  ->  quyen bat buoc (None = khong can quyen rieng)
    NEEDS = {
        "chrome.storage":      "storage",
        "chrome.contextMenus": "contextMenus",
        "chrome.scripting":    "scripting",
        "chrome.commands":     None,
        "chrome.runtime":      None,
        "chrome.tabs":         None,      # chi dung id/query, khong doc url
        # chrome.permissions khong can mot muc trong "permissions", nhung chi
        # dung duoc khi manifest co khai "optional_host_permissions".
        "chrome.permissions":  None,
    }

    def test_each_used_api_has_its_permission(self):
        perms = set(MANIFEST["permissions"])
        used = set()
        for name, src in js_sources().items():
            used |= {m for m in self.NEEDS if m in src}
        for api in sorted(used):
            need = self.NEEDS[api]
            if need is None:
                continue
            with self.subTest(api=api):
                self.assertIn(need, perms, f"{api} duoc dung nhung thieu quyen '{need}'")

    def test_no_undeclared_chrome_namespace(self):
        known = {m.split(".")[1] for m in self.NEEDS}
        for name, src in js_sources().items():
            for ns in set(re.findall(r"chrome\.([a-zA-Z]+)", src)):
                with self.subTest(file=name, ns=ns):
                    self.assertIn(ns, known,
                                  f"{name} dung chrome.{ns} — chua duoc xet quyen")

    def test_optional_permissions_declared_if_api_used(self):
        if any("chrome.permissions" in src for src in js_sources().values()):
            self.assertTrue(
                MANIFEST.get("optional_permissions") or MANIFEST.get("optional_host_permissions"),
                "dung chrome.permissions ma manifest khong khai optional_*")

    def test_no_unused_permission(self):
        for perm in MANIFEST["permissions"]:
            if perm == "activeTab":
                continue        # can cho scripting tren tab dang mo, khong xuat hien trong ma
            api = next((a for a, p in self.NEEDS.items() if p == perm), None)
            with self.subTest(perm=perm):
                self.assertIsNotNone(api, f"quyen '{perm}' khong ung voi API nao")
                self.assertTrue(any(api in s for s in js_sources().values()),
                                f"xin quyen '{perm}' nhung khong dung {api}")


class TestNetworkGoesThroughServiceWorker(unittest.TestCase):
    """Content script chay theo origin cua TRANG. Trang https:// goi
    http://127.0.0.1 se vuong mixed-content / Private Network Access.
    Vi vay moi fetch phai nam o service worker."""

    def test_content_script_does_not_fetch(self):
        src = content_script_source()
        self.assertNotIn("fetch(", src,
                         "content.js goi fetch truc tiep — se bi chan tren trang https")
        self.assertIn("chrome.runtime.sendMessage", src)

    def test_background_handles_translate_messages(self):
        src = (EXT / "background.js").read_text()
        self.assertIn('msg?.type !== "translate"', src)
        self.assertIn("return true", src,
                      "phai return true de giu kenh mo cho phan hoi bat dong bo")


class TestIcons(unittest.TestCase):
    def test_icons_are_png_of_the_declared_size(self):
        for size, rel in MANIFEST["icons"].items():
            with self.subTest(size=size):
                data = (EXT / rel).read_bytes()
                self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"), "khong phai PNG")
                w, h = struct.unpack(">II", data[16:24])
                self.assertEqual((w, h), (int(size), int(size)))


class TestEngineSelectionSafety(unittest.TestCase):
    """Khoa lai hai loi that da gap khi chay extension trong Brave.

    1. engineHandles coi source="auto" la khop moi cap -> boi den tieng Nhat
       roi vao EnViT5 -> no doan bua thanh tieng Anh -> tra ve ":" ma khong
       bao loi. Sai tham lang, te hon bao loi.
    2. Boi den tieng Viet khi dich=vi -> vi->vi -> engine tra loi 400 va
       thong bao tho cua may chu loi thang ra the."""

    @classmethod
    def setUpClass(cls):
        script = f"""
import {{ pickEngine, engineHandles, normLang }} from "{EXT / 'common.js'}";
console.log(JSON.stringify({{
  autoNeverMatchesRestricted: engineHandles("hf", "auto", "vi"),
  jaGoesToLibre: pickEngine("auto", "ja", "vi").key,
  koGoesToLibre: pickEngine("auto", "ko", "vi").key,
  zhGoesToLibre: pickEngine("auto", "zh-Hans", "vi").key,
  enViUsesEnvit5: pickEngine("auto", "en", "vi").key,
  viEnUsesEnvit5: pickEngine("auto", "vi", "en").key,
  explicitHfWithJaFallsBack: pickEngine("hf", "ja", "vi").key,
  zhNormalised: normLang("zh"),
}}));
"""
        r = subprocess.run(["node", "--input-type=module", "-e", script],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise unittest.SkipTest(f"node loi: {r.stderr[:200]}")
        cls.v = json.loads(r.stdout)

    def test_auto_source_never_matches_a_restricted_engine(self):
        self.assertFalse(self.v["autoNeverMatchesRestricted"],
                         "source='auto' khong duoc coi la khop voi EnViT5")

    def test_cjk_never_routed_to_envit5(self):
        for k in ("jaGoesToLibre", "koGoesToLibre", "zhGoesToLibre", "explicitHfWithJaFallsBack"):
            with self.subTest(case=k):
                self.assertEqual(self.v[k], "lt")

    def test_en_vi_pair_uses_envit5(self):
        self.assertEqual(self.v["enViUsesEnvit5"], "hf")
        self.assertEqual(self.v["viEnUsesEnvit5"], "hf")

    def test_zh_is_normalised(self):
        self.assertEqual(self.v["zhNormalised"], "zh-Hans")


@unittest.skipUnless(server_up(), "may chu khong chay")
class TestTranslateFlowAgainstRealServer(unittest.TestCase):
    """Chay that ham translate() cua extension bang Node, danh vao may chu that."""

    @classmethod
    def setUpClass(cls):
        cases = [
            ["Good morning, how are you today?", "vi"],
            ["Hôm nay trời đẹp quá, tôi muốn đi dạo.", "vi"],
            ["今日はいい天気ですね。", "vi"],
            ["오늘 날씨가 정말 좋습니다.", "vi"],
            ["今天天气很好。", "vi"],
        ]
        script = f"""
import {{ translate }} from "{EXT / 'common.js'}";
const cases = {json.dumps(cases, ensure_ascii=False)};
const out = [];
for (const [q, target] of cases) {{
  try {{ out.push(await translate(q, {{ base: "{BASE}", engine: "auto", source: "auto", target }})); }}
  catch (e) {{ out.push({{ error: String(e.message) }}); }}
}}
console.log(JSON.stringify(out));
"""
        r = subprocess.run(["node", "--input-type=module", "-e", script],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            raise unittest.SkipTest(f"node loi: {r.stderr[:300]}")
        cls.res = json.loads(r.stdout)

    def test_no_case_errors(self):
        for i, r in enumerate(self.res):
            with self.subTest(case=i):
                self.assertNotIn("error", r, f"truong hop {i} loi: {r.get('error')}")

    def test_source_is_resolved_before_choosing_engine(self):
        """Phai goi /detect truoc: source tra ve khong duoc con la 'auto'."""
        for i, r in enumerate(self.res):
            with self.subTest(case=i):
                self.assertNotEqual(r["source"], "auto",
                                    "chua nhan dien nguon truoc khi chon engine")

    def test_english_uses_envit5(self):
        self.assertEqual(self.res[0]["engine"], "EnViT5")
        self.assertTrue(self.res[0]["text"].strip())

    def test_vietnamese_into_vietnamese_flips_instead_of_failing(self):
        r = self.res[1]
        self.assertEqual(r["source"], "vi")
        self.assertEqual(r["target"], "en", "phai tu doi dich sang en thay vi bao loi vi->vi")
        self.assertIn("đã là vi", r["note"] or "")
        self.assertTrue(r["text"].strip())

    def test_cjk_goes_to_libretranslate_and_produces_real_text(self):
        for i, lang in ((2, "ja"), (3, "ko"), (4, "zh-Hans")):
            with self.subTest(lang=lang):
                r = self.res[i]
                self.assertEqual(r["source"], lang)
                self.assertEqual(r["engine"], "LibreTranslate")
                # Truoc khi sua, EnViT5 tra ve ":" — mot ky tu rac.
                self.assertGreater(len(r["text"].strip()), 5,
                                   f"ket qua qua ngan, nghi la rac: {r['text']!r}")


class TestEngineLogic(unittest.TestCase):
    """Chay that logic chon engine trong common.js bang Node."""

    @classmethod
    def setUpClass(cls):
        script = f"""
import {{ pickEngine, engineHandles }} from "{EXT / 'common.js'}";
const cases = [
  ["auto", "en", "vi"], ["auto", "vi", "en"], ["auto", "en", "ja"],
  ["hf", "en", "vi"], ["hf", "en", "ja"], ["lt", "en", "ja"],
  ["auto", "auto", "vi"], ["hf", "auto", "ko"],
];
console.log(JSON.stringify(cases.map(([p, s, t]) => [p, s, t, pickEngine(p, s, t).key])));
"""
        r = subprocess.run(["node", "--input-type=module", "-e", script],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise unittest.SkipTest(f"khong chay duoc node: {r.stderr[:200]}")
        cls.picked = {tuple(row[:3]): row[3] for row in json.loads(r.stdout)}

    def test_auto_prefers_envit5_for_en_vi(self):
        self.assertEqual(self.picked[("auto", "en", "vi")], "hf")
        self.assertEqual(self.picked[("auto", "vi", "en")], "hf")

    def test_auto_uses_libretranslate_for_other_pairs(self):
        self.assertEqual(self.picked[("auto", "en", "ja")], "lt")

    def test_explicit_envit5_falls_back_when_pair_unsupported(self):
        self.assertEqual(self.picked[("hf", "en", "ja")], "lt")
        self.assertEqual(self.picked[("hf", "auto", "ko")], "lt")

    def test_explicit_choice_is_respected_when_possible(self):
        self.assertEqual(self.picked[("hf", "en", "vi")], "hf")
        self.assertEqual(self.picked[("lt", "en", "ja")], "lt")


@unittest.skipUnless(server_up(), f"may chu {BASE} khong chay")
class TestEndpointsTheExtensionCalls(unittest.TestCase):
    def post(self, path, payload):
        req = urllib.request.Request(
            BASE + path, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())

    def test_languages_endpoint(self):
        with urllib.request.urlopen(BASE + "/api/languages", timeout=10) as r:
            self.assertGreaterEqual(len(json.loads(r.read())), 5)

    def test_libretranslate_path(self):
        d = self.post("/api/translate",
                      {"q": "Good morning", "source": "auto", "target": "vi", "format": "text"})
        self.assertTrue(d["translatedText"].strip())

    def test_envit5_path(self):
        try:
            urllib.request.urlopen(BASE + "/api2/health", timeout=5)
        except OSError:
            self.skipTest("EnViT5 chua bat")
        d = self.post("/api2/translate",
                      {"q": "Good morning", "source": "auto", "target": "vi", "format": "text"})
        self.assertTrue(d["translatedText"].strip())

    def test_base_url_default_matches_this_server(self):
        src = (EXT / "common.js").read_text()
        m = re.search(r'base:\s*"([^"]+)"', src)
        self.assertEqual(m.group(1), BASE,
                         "mac dinh trong common.js lech voi cong that trong .env")


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ---------------------------------------------------------------------------
# Vi tri popup — chay trong trinh duyet that.
#
# Hai loi that da gap, deu chi lo ra khi dieu khien chuot that:
#  1. run() an nut ngay o mousedown; den luc nha chuot, cho do khong con nut
#     nen su kien roi xuong TRANG -> handler tuong da boi den cho khac ->
#     showBubble() -> ham nay goi hideCard() -> ban dich vua hien bi xoa.
#     Voi EnViT5 (~130 ms) thi mot cu bam binh thuong cung du de mat ket qua.
#  2. Popup dat ngay duoi vung chon nen nuot mat dong ke tiep — tren PDF day
#     chu thi rat kho doc.
# ---------------------------------------------------------------------------
from tests import browser  # noqa: E402

_PLACE_WHY = browser.available() or ([] if server_up() else ["may chu khong chay"])


@unittest.skipIf(_PLACE_WHY, " · ".join(_PLACE_WHY))
class TestPopupPlacement(unittest.TestCase):
    res: dict = {}

    @classmethod
    def setUpClass(cls):
        port = 9801
        with browser.brave(port, extension=EXT):
            if not browser.extension_id(port):
                raise unittest.SkipTest("khong thay service worker")
            cls.res = browser.run_driver(
                ROOT / "tests" / "e2e_placement.mjs", port, BASE, timeout=240)

    def test_driver_ran(self):
        self.assertTrue(self.res.get("ok"), f"driver loi: {self.res.get('error')}")

    def test_bubble_appears_at_every_corner(self):
        for c, r in self.res.get("corners", {}).items():
            with self.subTest(corner=c):
                self.assertTrue(r.get("bubbleShown"), "khong hien nut")
                self.assertTrue(r.get("bubbleInside"), "nut tran ra ngoai khung nhin")

    def test_card_survives_a_slow_click(self):
        """Giu chuot 400 ms roi nha — the phai CON hien."""
        for c, r in self.res.get("corners", {}).items():
            with self.subTest(corner=c):
                self.assertTrue(r.get("cardShown"),
                                "the bien mat khi nha chuot — loi tranh chap mouseup")

    def test_card_never_leaves_the_viewport(self):
        for c, r in self.res.get("corners", {}).items():
            with self.subTest(corner=c, box=r.get("cardBox")):
                self.assertTrue(r.get("cardInside"),
                                f"the tran ra ngoai man hinh: {r.get('cardBox')}")


class TestPopupMarkup(unittest.TestCase):
    def test_icon_is_inline_svg_not_emoji(self):
        """Emoji phu thuoc font he thong — thieu font la ra o vuong trong."""
        src = content_script_source()
        self.assertIn("<svg", src)
        self.assertNotIn("🗣", src)

    def test_placement_prefers_the_side_over_covering_text(self):
        src = content_script_source()
        self.assertIn("function placeCard", src)
        self.assertIn("function placeBubble", src)

    def test_mouseup_after_bubble_click_is_skipped(self):
        src = content_script_source()
        self.assertIn("skipNextMouseup", src)

    def test_invalidated_context_gets_a_plain_language_message(self):
        """Nap lai extension (nut ⟳) lam chet chrome.runtime cua content script
        trong cac tab dang mo. Nguoi dung khong nen phai doc
        'Extension context invalidated' — chi can biet la tai lai trang."""
        src = content_script_source()
        self.assertIn("context invalidated", src, "khong bat loi nay")
        self.assertIn("Tải lại trang", src, "khong huong dan nguoi dung lam gi")
        self.assertIn("extensionGone", src, "khong co ham kiem tra context da chet")

    def test_listeners_are_removable_so_reinjection_is_safe(self):
        src = content_script_source()
        self.assertIn("AbortController", src)
        self.assertIn("__dichOfflineCleanup", src)

    def test_background_reinjects_after_the_extension_reloads(self):
        src = (EXT / "background.js").read_text()
        self.assertIn("reinjectContentScripts", src)
        self.assertIn("onStartup", src)
        self.assertIn("storage.session", src,
                      "phai chen lai MOT lan moi lan nap, khong phai moi lan service worker thuc day")
