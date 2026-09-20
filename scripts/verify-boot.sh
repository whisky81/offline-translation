#!/usr/bin/env bash
# Kiem tra moi dieu kien de cac cong tu len lai sau khi khoi dong may.
# Khong can sudo. Them --simulate de dien tap that (can sudo, se ngat dich vu ~1 phut).
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/scripts/_docker-env.sh"
UNIT=/etc/systemd/system/libretranslate.service
G=$'\e[32m'; R=$'\e[31m'; Y=$'\e[33m'; B=$'\e[1m'; N=$'\e[0m'
ok=0; bad=0
pass() { echo "  ${G}OK${N}   $*"; ok=$((ok+1)); }
fail() { echo "  ${R}HONG${N} $*"; bad=$((bad+1)); }

. "$PROJECT_DIR/scripts/_config.sh"
API_PORT=$LT_API_PORT
WEB_PORT=$LT_WEB_PORT
ADDR=$LT_HOST

echo "${B}=== Kiem tra kha nang tu chay sau reboot ===${N}"
echo

echo "[Chuoi phu thuoc luc boot]"
for u in containerd.service docker.socket docker.service libretranslate.service; do
  state=$(systemctl is-enabled "$u" 2>/dev/null)
  if [ "$state" = "enabled" ] || [ "$state" = "static" ]; then
    pass "$u: $state"
  else
    fail "$u: ${state:-khong ro} — se KHONG tu chay (sudo systemctl enable $u)"
  fi
done

echo
echo "[Unit]"
if [ -f "$UNIT" ]; then
  pass "co $UNIT"
else
  fail "chua cai unit — sudo ./scripts/install.sh"
  echo; echo "${B}=== $ok dat / $bad hong ===${N}"; exit 1
fi

grep -q '^WantedBy=multi-user.target' "$UNIT" \
  && pass "WantedBy=multi-user.target (chay ca khi chua dang nhap)" \
  || fail "thieu WantedBy=multi-user.target"

grep -q '^Requires=docker.service' "$UNIT" \
  && pass "Requires=docker.service" || fail "thieu Requires=docker.service"

grep -qE '^After=.*docker.service' "$UNIT" \
  && pass "After=docker.service (doi Docker san sang)" || fail "thieu After=docker.service"

grep -q '^Restart=always' "$UNIT" \
  && pass "Restart=always (tu dung day neu sap)" || fail "thieu Restart=always"

echo
echo "[Unit co bao phu het service khong]"
exec_line=$(grep -E '^ExecStart=' "$UNIT")
services=$(docker compose --project-directory "$PROJECT_DIR" config --services 2>/dev/null)
nsvc=$(echo "$services" | grep -c .)
# 'docker compose up' khong kem ten service -> khoi dong tat ca.
if echo "$exec_line" | grep -qE 'up( --[a-z-]+)*\s*$'; then
  pass "ExecStart chay 'up' khong loc service -> khoi dong ca $nsvc service:"
  echo "$services" | sed 's/^/         - /'
else
  fail "ExecStart chi dinh service cu the, se bo sot:"
  echo "         $exec_line"
fi

echo
echo "[Cong se mo]"
# Phai doc cau hinh DA GIAI BIEN: trong file goc cong viet dang ${HOST_PORT:-5000}.
resolved=$(docker compose --project-directory "$PROJECT_DIR" config 2>/dev/null)
for pair in "$API_PORT API + UI goc" "$WEB_PORT UI tieng Viet"; do
  p=${pair%% *}; label=${pair#* }
  if echo "$resolved" | grep -qE "published: \"?${p}\"?"; then
    pass "cong $p ($label) se duoc mo"
  else
    fail "cong $p khong co trong cau hinh da giai bien"
  fi
done

echo
echo "[Trang thai hien tai]"
# Lay ten container tu compose thay vi viet cung — them service moi la tu bao phu.
CONTAINERS=$(docker compose --project-directory "$PROJECT_DIR" ps -a --format '{{.Name}}' 2>/dev/null)
[ -n "$CONTAINERS" ] || CONTAINERS="libretranslate lt-web"
for c in $CONTAINERS; do
  h=$(docker inspect "$c" --format '{{.State.Health.Status}}' 2>/dev/null)
  case "$h" in
    healthy)   pass "$c: healthy" ;;
    "")        fail "$c: chua chay" ;;
    *)         fail "$c: $h" ;;
  esac
done

# Container phai thuoc dung project ma unit quan, neu khong systemd se khong biet toi no.
for c in $CONTAINERS; do
  proj=$(docker inspect "$c" --format '{{index .Config.Labels "com.docker.compose.project"}}' 2>/dev/null)
  if [ "$proj" = "setup-translate" ]; then
    pass "$c thuoc project 'setup-translate' (unit quan duoc)"
  else
    fail "$c thuoc project '${proj:-?}' — systemd se khong quan ly no"
  fi
done


# Container tao TRUOC lan khoi dong gan nhat cua unit la do chay tay -> khong
# duoc systemd giam sat, va khong chac len lai sau reboot.
unit_start=$(date -d "$(systemctl show libretranslate.service -p ActiveEnterTimestamp --value)" +%s 2>/dev/null || echo 0)
for c in $CONTAINERS; do
  created=$(docker inspect "$c" --format '{{.Created}}' 2>/dev/null)
  [ -n "$created" ] || continue
  cts=$(date -d "$created" +%s 2>/dev/null || echo 0)
  # systemd chay 'docker compose up' MOT lan, tao moi container gan nhu cung luc.
  # Lech nhieu so voi thoi diem unit khoi dong => container do duoc tao bang tay.
  diff=$(( cts - unit_start )); [ "$diff" -lt 0 ] && diff=$(( -diff ))
  if [ "$diff" -le 120 ]; then
    pass "$c do systemd tao (lech ${diff}s so voi luc unit khoi dong)"
  else
    fail "$c tao bang tay (lech ${diff}s) -> systemd chua giam sat no."
    echo "         Van len sau reboot, nhung nen dong bo: sudo systemctl restart libretranslate"
  fi
done

echo
echo "[Cong dang phuc vu]"
for pair in "$API_PORT /languages" "$WEB_PORT /"; do
  p=${pair%% *}; path=${pair#* }
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 "http://${ADDR}:${p}${path}")
  [ "$code" = "200" ] && pass "http://${ADDR}:${p}${path} -> 200" \
                      || fail "http://${ADDR}:${p}${path} -> ${code}"
done

echo
echo "${B}=== $ok dat / $bad hong ===${N}"

if [ "${1:-}" = "--simulate" ]; then
  echo
  echo "${B}=== Dien tap: chay dung chuoi lenh ma systemd chay luc boot ===${N}"
  echo "(ExecStartPre 'down' roi ExecStart 'up' — giong het khi khoi dong may)"
  sudo systemctl restart libretranslate.service
  echo "Dang cho ca hai cong tra loi..."
  for i in $(seq 1 60); do
    a=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://${ADDR}:${API_PORT}/languages")
    w=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://${ADDR}:${WEB_PORT}/")
    if [ "$a" = "200" ] && [ "$w" = "200" ]; then
      echo "${G}Ca hai cong len sau ~$((i*2))s — reboot se cho ket qua tuong tu.${N}"
      exit 0
    fi
    sleep 2
  done
  echo "${Y}Sau 120s van chua du hai cong (API=$a WEB=$w). Xem: journalctl -u libretranslate -n 80${N}"
  exit 1
fi

if [ "$bad" -gt 0 ]; then
  echo "Co muc HONG — xu ly roi chay lai."
  exit 1
fi
echo "Moi dieu kien dat. Dien tap that: ./scripts/verify-boot.sh --simulate"
