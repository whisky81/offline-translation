#!/usr/bin/env bash
# Go LibreTranslate. Chay: sudo ./scripts/uninstall.sh [--purge]
# --purge: xoa luon volume chua model da tai ve.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/scripts/_docker-env.sh"
UNIT_DST="/etc/systemd/system/libretranslate.service"
PURGE=0
if [ "${1:-}" = "--purge" ]; then PURGE=1; fi

[ "$(id -u)" -eq 0 ] || { echo "Can root: sudo $0 ${1:-}" >&2; exit 1; }

echo "==> Dung va tat service"
systemctl disable --now libretranslate.service 2>/dev/null || true

echo "==> Go container"
docker compose --project-directory "$PROJECT_DIR" down --remove-orphans || true

echo "==> Xoa unit"
rm -f "$UNIT_DST"
systemctl daemon-reload

if [ "$PURGE" -eq 1 ]; then
  echo "==> Xoa volume model (libretranslate_models)"
  docker volume rm libretranslate_models || true
  echo "==> Xoa image"
  docker image rm "${LT_IMAGE:-libretranslate/libretranslate:latest}" 2>/dev/null || true
else
  echo "Volume model giu lai. Muon xoa het: sudo $0 --purge"
fi

echo
echo "Da go. Luu y: docker.service van con enabled."
echo "Muon tat han:  sudo systemctl disable --now docker.service docker.socket"
