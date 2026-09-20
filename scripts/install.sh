#!/usr/bin/env bash
# Cai LibreTranslate thanh daemon he thong (tu chay tu luc boot).
# Chay: sudo ./scripts/install.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/scripts/_docker-env.sh"
UNIT_SRC="$PROJECT_DIR/systemd/libretranslate.service.in"
UNIT_DST="/etc/systemd/system/libretranslate.service"
G=$'\e[32m'; Y=$'\e[33m'; B=$'\e[1m'; N=$'\e[0m'
step() { echo; echo "${B}==> $*${N}"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Script nay can quyen root. Chay lai: sudo $0" >&2
  exit 1
fi

TARGET_USER="${SUDO_USER:-root}"
echo "Thu muc du an : $PROJECT_DIR"
echo "User su dung  : $TARGET_USER"

step "1/5 Bat Docker Engine he thong"
# Docker Desktop chay trong VM theo phien GUI -> khong lam daemon duoc.
# Ta dung docker.service (rootful) de container song tu luc boot.
systemctl enable --now docker.socket docker.service
if systemctl is-active --quiet docker.service; then
  echo "${G}docker.service dang chay va da enabled${N}"
else
  echo "Khong khoi dong duoc docker.service. Xem: journalctl -u docker -n 50" >&2
  exit 1
fi

step "2/5 Them '$TARGET_USER' vao group docker"
if [ "$TARGET_USER" != "root" ]; then
  if id -nG "$TARGET_USER" | tr ' ' '\n' | grep -qx docker; then
    echo "Da co san, bo qua."
  else
    usermod -aG docker "$TARGET_USER"
    echo "${Y}Da them. Can DANG XUAT va DANG NHAP LAI thi 'docker' moi chay khong can sudo.${N}"
    echo "${Y}(Tam thoi co the dung: newgrp docker)${N}"
  fi
fi

step "3/5 Keo image ve"
docker compose --project-directory "$PROJECT_DIR" pull

step "4/5 Cai systemd unit"
sed -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
    -e "s|__DOCKER_CONFIG__|$DOCKER_CONFIG|g" "$UNIT_SRC" > "$UNIT_DST"
chmod 0644 "$UNIT_DST"
systemctl daemon-reload
systemctl enable libretranslate.service
echo "${G}Da cai $UNIT_DST va enable (tu chay luc boot)${N}"

step "5/5 Khoi dong"
systemctl restart libretranslate.service
echo "Dang khoi dong. Lan dau phai TAI MODEL nen co the mat 2-10 phut."
echo "Xem tien trinh:  journalctl -u libretranslate -f"

. "$PROJECT_DIR/scripts/_config.sh"
port=$LT_API_PORT
addr=$LT_HOST

echo
echo "Cho may chu san sang (toi da 15 phut)..."
for i in $(seq 1 180); do
  if curl -sf --max-time 3 "http://${addr}:${port}/languages" >/dev/null 2>&1; then
    echo "${G}San sang!${N}"
    echo
    echo "  Web UI   : http://${addr}:${port}/"
    echo "  API docs : http://${addr}:${port}/docs"
    echo "  Kiem tra : $PROJECT_DIR/scripts/verify.sh"
    exit 0
  fi
  sleep 5
  if [ $((i % 12)) -eq 0 ]; then echo "  ... con dang tai model ($((i*5))s)"; fi
done

echo "${Y}Het thoi gian cho. Kiem tra log: journalctl -u libretranslate -n 100 --no-pager${N}"
exit 1
