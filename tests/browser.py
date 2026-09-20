"""Khoi dong Brave/Chromium headless cho cac test chay trong trinh duyet that.

Tach rieng vi ca test PDF lan test UI web deu can, va khoi dong trinh duyet
co nhieu cho de sai (cho CDP san sang, lay dung extension id, don profile).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

BROWSER = next((p for p in ("/opt/brave.com/brave/brave",
                            "/usr/bin/brave-browser",
                            "/usr/bin/brave-browser-stable",
                            shutil.which("chromium") or "",
                            shutil.which("google-chrome") or "")
                if p and Path(p).exists()), None)

FLAGS = ["--headless=new", "--no-sandbox", "--disable-gpu", "--no-first-run",
         "--disable-sync", "--disable-component-update", "--disable-background-networking"]


def available() -> list[str]:
    """Danh sach ly do KHONG chay duoc; rong nghia la chay duoc."""
    why = []
    if BROWSER is None:
        why.append("khong tim thay Brave/Chromium")
    if shutil.which("node") is None:
        why.append("khong co node")
    return why


def _cdp_ready(port: int, timeout_s: int = 40) -> bool:
    for _ in range(timeout_s):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def extension_id(port: int, tries: int = 25) -> str | None:
    for _ in range(tries):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as r:
                for t in json.loads(r.read()):
                    m = re.match(r"chrome-extension://([a-p]{32})/background\.js", t.get("url", ""))
                    if m:
                        return m.group(1)
        except OSError:
            pass
        time.sleep(1)
    return None


@contextmanager
def brave(port: int, extension: Path | None = None):
    """Mo mot phien headless, dong va don sach khi ra khoi khoi with."""
    profile = tempfile.mkdtemp(prefix="dich-test-")
    cmd = [BROWSER, *FLAGS, f"--user-data-dir={profile}",
           f"--remote-debugging-port={port}"]
    if extension:
        cmd.append(f"--load-extension={extension}")
    cmd.append("about:blank")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    try:
        if not _cdp_ready(port):
            raise RuntimeError(f"CDP khong len o cong {port}")
        yield proc
    finally:
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except OSError:
                proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


def run_driver(script: Path, *args, timeout: int = 180) -> dict:
    """Chay mot driver CDP viet bang node, doc dong JSON cuoi cung."""
    r = subprocess.run(["node", str(script), *map(str, args)],
                       capture_output=True, text=True, timeout=timeout)
    lines = [l for l in r.stdout.strip().splitlines() if l.strip().startswith("{")]
    if not lines:
        raise RuntimeError(f"driver khong tra ve JSON:\nstdout={r.stdout[-400:]}\nstderr={r.stderr[-400:]}")
    return json.loads(lines[-1])
