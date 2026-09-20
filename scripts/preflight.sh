#!/usr/bin/env bash
# Kiem tra moi truong truoc khi cai. Khong can sudo, khong thay doi gi.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/scripts/_docker-env.sh"
. "$PROJECT_DIR/scripts/_config.sh"
ok=0; warn=0; err=0
G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; N=$'\e[0m'
pass() { echo "  ${G}OK${N}    $*"; ok=$((ok+1)); }
note() { echo "  ${Y}CHU Y${N} $*"; warn=$((warn+1)); }
fail() { echo "  ${R}THIEU${N} $*"; err=$((err+1)); }

echo "=== Kiem tra moi truong cho LibreTranslate ==="
echo

echo "[He thong]"
. /etc/os-release 2>/dev/null
pass "OS: ${PRETTY_NAME:-unknown} ($(uname -m))"
pass "Kernel: $(uname -r)"
cores=$(nproc)
pass "CPU: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs) — ${cores} luong"
if grep -qiE 'nvidia|amd/ati' <(lspci 2>/dev/null | grep -iE 'vga|3d'); then
  pass "Co GPU roi — co the cannhac image libretranslate/libretranslate:latest-cuda"
else
  note "Khong co GPU roi, se chay CPU (dung, da chon image CPU)"
fi

mem_mb=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
if [ "$mem_mb" -ge 4096 ]; then pass "RAM: ${mem_mb} MB"; else fail "RAM chi ${mem_mb} MB, nen co >= 4096 MB"; fi

free_gb=$(df -BG --output=avail "$PROJECT_DIR" | tail -1 | tr -dc '0-9')
if [ "${free_gb:-0}" -ge 5 ]; then pass "Dung luong trong: ${free_gb} GB"; else fail "Chi con ${free_gb} GB, can >= 5 GB (image ~600 MB + model)"; fi

echo
echo "[Docker]"
if command -v docker >/dev/null 2>&1; then
  pass "docker CLI: $(docker --version | cut -d, -f1)"
else
  fail "Chua co docker CLI"
fi
if docker compose version >/dev/null 2>&1; then
  pass "compose plugin: $(docker compose version --short 2>/dev/null)"
else
  fail "Chua co plugin 'docker compose'"
fi

if systemctl list-unit-files docker.service >/dev/null 2>&1 && \
   systemctl cat docker.service >/dev/null 2>&1; then
  state=$(systemctl is-enabled docker.service 2>/dev/null)
  active=$(systemctl is-active docker.service 2>/dev/null)
  if [ "$state" = "enabled" ]; then pass "docker.service: enabled (tu chay luc boot)"
  else note "docker.service: ${state} — install.sh se bat len"; fi
  if [ "$active" = "active" ]; then pass "docker.service: dang chay"
  else note "docker.service: ${active} — install.sh se khoi dong"; fi
else
  fail "Khong tim thay docker.service (Docker Engine he thong chua duoc cai)"
fi

echo
echo "[Co lap khoi Docker Desktop]"
pass "DOCKER_CONFIG cua project: ${DOCKER_CONFIG#$PROJECT_DIR/}"
if [ -f "$HOME/.docker/config.json" ] \
   && grep -q '"credsStore"' "$HOME/.docker/config.json" 2>/dev/null; then
  helper=$(grep -o '"credsStore": *"[^"]*"' "$HOME/.docker/config.json" | cut -d'"' -f4)
  note "~/.docker dung credential helper '${helper}' (hong khi Desktop tat)"
  note "  -> project dung config rieng nen khong bi, va ~/.docker giu nguyen"
fi
plug=$(readlink -f "$DOCKER_CONFIG/cli-plugins/docker-compose" 2>/dev/null)
case "$plug" in
  /usr/libexec/*) pass "compose plugin: ban docker-ce ($(docker compose version --short 2>/dev/null))" ;;
  "")             note "chua co symlink compose rieng, se dung ban he thong" ;;
  *)              note "compose plugin dang tro toi ${plug}" ;;
esac

if id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
  pass "User '$USER' da o trong group docker"
else
  note "User '$USER' chua o trong group docker — install.sh se them (can dang xuat/dang nhap lai)"
fi

echo
echo "[Cong mang]"
port=$LT_API_PORT
if ss -ltn 2>/dev/null | grep -qE "[:.]${port}\b"; then
  # Phan biet "bi ke khac chiem" voi "chinh service cua ta dang chay".
  if curl -sf --max-time 4 "http://127.0.0.1:${port}/languages" >/dev/null 2>&1; then
    pass "Cong ${port}: LibreTranslate cua project dang chay o day"
  else
    fail "Cong ${port} bi tien trinh khac chiem:"
    ss -ltnp 2>/dev/null | grep -E "[:.]${port}\b" | sed 's/^/        /'
  fi
else
  pass "Cong ${port} dang trong"
fi

echo
echo "[Ket noi mang (chi can cho lan cai dau)]"
if curl -sS -o /dev/null --max-time 10 https://registry-1.docker.io/v2/ 2>/dev/null || [ $? -le 22 ]; then
  pass "Ra duoc Docker Hub"
else
  note "Khong ra duoc Docker Hub — can mang de keo image lan dau"
fi
if curl -sS -o /dev/null --max-time 10 https://www.argosopentech.com/argospm/index/ 2>/dev/null; then
  pass "Ra duoc kho model Argos"
else
  note "Khong kiem tra duoc kho model Argos — can mang de tai model lan dau"
fi

echo
echo "=== Tong ket: ${ok} dat / ${warn} luu y / ${err} thieu ==="
if [ "$err" -gt 0 ]; then
  echo "Co muc THIEU, xu ly truoc khi chay install.sh."
  exit 1
fi
echo "San sang. Buoc tiep: sudo ./scripts/install.sh"
