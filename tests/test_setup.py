#!/usr/bin/env python3
"""Test cau hinh project: co lap khoi Docker Desktop, tinh dung dan cua compose/systemd.

Khong can may chu dang chay. Cac test can noi chuyen voi Docker Engine se tu
bo qua neu shell hien tai chua co quyen (chua dang nhap lai sau khi vao group docker).

    python3 -m unittest tests.test_setup -v
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCKER_CONFIG = ROOT / "docker-config"
UNIT_INSTALLED = Path("/etc/systemd/system/libretranslate.service")


def _published_ports() -> list[str]:
    """Cac muc trong moi khoi `ports:` cua docker-compose.yml.

    Doc theo thut dau thay vi regex: gia tri nhu "${WEB_PORT:-5001}" co ca dau
    hai cham va ngoac nen regex de sai."""
    out, in_ports, indent = [], False, 0
    for raw in (ROOT / "docker-compose.yml").read_text().splitlines():
        stripped = raw.strip()
        if stripped.startswith("#") or not stripped:
            continue
        cur = len(raw) - len(raw.lstrip())
        if in_ports:
            if stripped.startswith("- ") and cur > indent:
                out.append(stripped[2:].strip().strip('"\''))
                continue
            in_ports = False
        if stripped == "ports:":
            in_ports, indent = True, cur
    return out


def docker_env() -> dict:
    env = dict(os.environ)
    env["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    env["DOCKER_CONFIG"] = str(DOCKER_CONFIG)
    env.pop("DOCKER_CONTEXT", None)
    return env


def docker_reachable() -> bool:
    if not shutil.which("docker"):
        return False
    r = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                       env=docker_env(), capture_output=True, timeout=30)
    return r.returncode == 0


DOCKER_OK = docker_reachable()


class TestDockerIsolation(unittest.TestCase):
    """Project khong duoc dinh gi toi cau hinh cua Docker Desktop."""

    def test_project_docker_config_exists(self):
        self.assertTrue((DOCKER_CONFIG / "config.json").is_file(),
                        "thieu docker-config/config.json")

    def test_project_config_has_no_desktop_credstore(self):
        cfg = json.loads((DOCKER_CONFIG / "config.json").read_text())
        self.assertNotIn("credsStore", cfg,
                         "config cua project khong duoc dung credential helper "
                         "(docker-credential-desktop hong khi Desktop tat)")

    def test_project_config_uses_default_context(self):
        cfg = json.loads((DOCKER_CONFIG / "config.json").read_text())
        self.assertEqual(cfg.get("currentContext"), "default")

    def test_project_config_has_no_desktop_plugin_hooks(self):
        cfg = json.loads((DOCKER_CONFIG / "config.json").read_text())
        self.assertNotIn("plugins", cfg, "hook plugin cua Desktop khong duoc co o day")
        self.assertNotIn("features", cfg)

    def test_compose_plugin_is_docker_ce_build(self):
        """Symlink khong nam trong git (duong dan he thong khac nhau giua cac
        may); scripts/_docker-env.sh tu tao khi chay."""
        link = DOCKER_CONFIG / "cli-plugins" / "docker-compose"
        if not link.exists():
            subprocess.run(["bash", "-c", f'. "{ROOT}/scripts/_docker-env.sh"'],
                           capture_output=True, timeout=30)
        if not link.exists():
            self.skipTest("khong tim thay plugin compose cua docker-ce tren may nay")
        target = str(link.resolve())
        self.assertNotIn("/usr/lib/docker/cli-plugins", target,
                         f"dang tro toi plugin cua Docker Desktop: {target}")

    def test_user_docker_config_left_untouched(self):
        """Ta co lap bang bien moi truong, KHONG duoc sua ~/.docker cua nguoi dung."""
        user_cfg = Path.home() / ".docker" / "config.json"
        if not user_cfg.is_file():
            self.skipTest("nguoi dung khong co ~/.docker/config.json")
        cfg = json.loads(user_cfg.read_text())
        self.assertEqual(cfg.get("currentContext"), "desktop-linux",
                         "cau hinh Docker Desktop cua nguoi dung da bi thay doi — "
                         "project phai co lap chu khong duoc sua file nay")

    def test_every_script_sources_shared_docker_env(self):
        shared = ROOT / "scripts" / "_docker-env.sh"
        self.assertTrue(shared.is_file())
        for name in ("ltctl", "install.sh", "uninstall.sh", "verify.sh"):
            with self.subTest(script=name):
                text = (ROOT / "scripts" / name).read_text()
                self.assertIn("_docker-env.sh", text,
                              f"{name} khong dung cau hinh Docker chung")

    def test_no_script_hardcodes_docker_host(self):
        """DOCKER_HOST chi duoc GAN o mot noi duy nhat (_docker-env.sh).

        Chi bat phep gan that su — nhac den ten bien trong cau thong bao
        thi khong sao."""
        assign = re.compile(r'^\s*(?:export\s+)?DOCKER_(?:HOST|CONFIG)=', re.M)
        for path in sorted((ROOT / "scripts").glob("*")):
            if path.name == "_docker-env.sh" or not path.is_file():
                continue
            with self.subTest(script=path.name):
                hits = assign.findall(path.read_text())
                self.assertFalse(hits,
                                 f"{path.name} tu gan DOCKER_HOST/DOCKER_CONFIG "
                                 f"thay vi source _docker-env.sh")

    @unittest.skipUnless(DOCKER_OK, "shell chua co quyen truy cap Docker Engine")
    def test_compose_resolves_without_desktop(self):
        r = subprocess.run(["docker", "compose", "--project-directory", str(ROOT),
                            "config", "--quiet"],
                           env=docker_env(), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, f"compose config that bai: {r.stderr}")

    @unittest.skipUnless(DOCKER_OK, "shell chua co quyen truy cap Docker Engine")
    def test_talking_to_system_engine_not_desktop_vm(self):
        r = subprocess.run(["docker", "info", "--format", "{{.Name}}"],
                           env=docker_env(), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("docker-desktop", r.stdout,
                         "dang noi chuyen voi VM cua Docker Desktop, khong phai engine he thong")


class TestComposeFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / "docker-compose.yml").read_text()

    def test_project_name_is_pinned(self):
        self.assertIn("name: setup-translate", self.text,
                      "ten project phai co dinh, khong phu thuoc ten thu muc")

    def test_restart_policy_left_to_systemd(self):
        self.assertIn('restart: "no"', self.text,
                      "compose khong duoc tu restart — systemd giu vong doi")

    def test_models_volume_is_named_so_it_survives_rename(self):
        self.assertIn("name: libretranslate_models", self.text)

    def test_published_port_is_hardcoded_to_loopback(self):
        """Dia chi phai GHI CUNG, khong lay tu bien: mot dong trong .env khong
        duoc phep vo tinh mo ca stack ra mang."""
        for entry in _published_ports():
            self.assertTrue(entry.startswith("127.0.0.1:"),
                            f"cong khong khoa loopback: {entry}")
        self.assertNotIn("${BIND_ADDR", self.text, "dia chi bind khong duoc lay tu bien")


class TestSystemdUnit(unittest.TestCase):
    def test_template_has_both_docker_placeholders(self):
        text = (ROOT / "systemd" / "libretranslate.service.in").read_text()
        self.assertIn("__PROJECT_DIR__", text)
        self.assertIn("__DOCKER_CONFIG__", text)

    @unittest.skipUnless(UNIT_INSTALLED.is_file(), "unit chua duoc cai")
    def test_installed_unit_has_no_placeholders_left(self):
        text = UNIT_INSTALLED.read_text()
        self.assertNotIn("__PROJECT_DIR__", text)
        self.assertNotIn("__DOCKER_CONFIG__", text,
                         "unit dang cai con placeholder — chay lai: sudo ./scripts/install.sh")

    @unittest.skipUnless(UNIT_INSTALLED.is_file(), "unit chua duoc cai")
    def test_installed_unit_isolates_docker_config(self):
        text = UNIT_INSTALLED.read_text()
        self.assertIn("DOCKER_HOST=unix:///var/run/docker.sock", text)
        self.assertIn("Environment=DOCKER_CONFIG=", text,
                      "unit dang cai chua co DOCKER_CONFIG — chay lai: sudo ./scripts/install.sh")

    @unittest.skipUnless(UNIT_INSTALLED.is_file(), "unit chua duoc cai")
    def test_unit_enabled_for_boot(self):
        r = subprocess.run(["systemctl", "is-enabled", "libretranslate.service"],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.stdout.strip(), "enabled",
                         "service phai enabled de tu chay luc boot")


class TestBootPersistence(unittest.TestCase):
    """Cac cong phai tu len lai sau khi khoi dong may, khong can dang nhap."""

    @unittest.skipUnless(UNIT_INSTALLED.is_file(), "unit chua duoc cai")
    def test_whole_dependency_chain_is_enabled(self):
        for unit in ("containerd.service", "docker.socket", "docker.service",
                     "libretranslate.service"):
            with self.subTest(unit=unit):
                r = subprocess.run(["systemctl", "is-enabled", unit],
                                   capture_output=True, text=True, timeout=30)
                self.assertIn(r.stdout.strip(), ("enabled", "static"),
                              f"{unit} se khong tu chay luc boot")

    @unittest.skipUnless(UNIT_INSTALLED.is_file(), "unit chua duoc cai")
    def test_unit_runs_before_login(self):
        self.assertIn("WantedBy=multi-user.target", UNIT_INSTALLED.read_text(),
                      "gan vao graphical/user target thi chi chay sau khi dang nhap")

    @unittest.skipUnless(UNIT_INSTALLED.is_file(), "unit chua duoc cai")
    def test_unit_starts_every_compose_service(self):
        """'docker compose up' khong kem ten service -> khoi dong tat ca.
        Neu ai do them '-d libretranslate' vao ExecStart thi service web bi bo sot."""
        line = next(l for l in UNIT_INSTALLED.read_text().splitlines()
                    if l.startswith("ExecStart="))
        # Tach theo TOKEN: chuoi "up" con nam trong duong dan 'setup-translate'.
        tokens = line.split("=", 1)[1].split()
        i = len(tokens) - 1 - tokens[::-1].index("up")
        leftover = [t for t in tokens[i + 1:] if not t.startswith("--")]
        self.assertFalse(leftover,
                         f"ExecStart loc service cu the ({leftover}) — cac service khac "
                         f"se khong len sau reboot")

    def test_only_one_port_is_published(self):
        """Chi nginx cong bo cong. LibreTranslate va engine chi tiep can duoc
        qua proxy — mot cua duy nhat de kiem soat."""
        published = _published_ports()
        self.assertEqual(len(published), 1, f"co {len(published)} cong duoc cong bo: {published}")
        self.assertIn("${WEB_PORT:-5001}:80", published[0])


class TestEnvFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = {}
        for line in (ROOT / ".env").read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cls.env[k.strip()] = v.strip()

    def test_no_bind_address_knob_in_env(self):
        """Bo han nut van nay khoi .env — dia chi nam trong compose."""
        self.assertIsNone(self.env.get("BIND_ADDR"))
        self.assertIsNone(self.env.get("HOST_PORT"),
                          "LibreTranslate khong con cong rieng")

    def test_stock_web_ui_is_disabled(self):
        """UI goc cua LibreTranslate la be mat thua: ta da co UI rieng."""
        self.assertEqual(self.env.get("LT_DISABLE_WEB_UI"), "true")

    def test_worker_count_fits_this_cpu(self):
        workers = int(self.env["LT_THREADS"])
        omp = int(self.env["OMP_NUM_THREADS"])
        self.assertLessEqual(workers * omp, 2 * os.cpu_count(),
                             f"{workers} worker x {omp} thread vuot qua kha nang "
                             f"{os.cpu_count()} luong cua may")

    def test_frontend_timeout_is_a_debounce_not_a_request_timeout(self):
        """Bay de dinh: ten bien nghe nhu timeout request, thuc ra la do tre
        debounce cua UI. Mac dinh goc 500 ms."""
        ms = int(self.env["LT_FRONTEND_TIMEOUT"])
        self.assertLessEqual(ms, 2000,
                             f"LT_FRONTEND_TIMEOUT={ms} -> UI doi {ms/1000:.0f}s moi dich")

    def test_frontend_source_language_is_auto(self):
        self.assertEqual(self.env["LT_FRONTEND_LANGUAGE_SOURCE"], "auto",
                         "khoa o nguon se lam nguoi dung go tieng khac vao bi ra rac")

    def test_batch_limit_not_restricted_locally(self):
        self.assertEqual(self.env["LT_BATCH_LIMIT"], "-1",
                         "chay local thi khong can chan so luong chuoi moi request")

    def test_env_example_stays_in_sync(self):
        self.assertEqual((ROOT / ".env").read_text(), (ROOT / ".env.example").read_text(),
                         ".env.example lech so voi .env")


if __name__ == "__main__":
    unittest.main(verbosity=2)
