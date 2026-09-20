# Doc cau hinh tu .env. Source, khong chay truc tiep.
#
# Truoc day moi script tu grep lai .env de lay cong va dia chi — sau ban sao,
# va cai nao cung phai nho rang BIND_ADDR=0.0.0.0 la dia chi LANG NGHE chu
# khong phai dia chi de goi toi.

_LT_ROOT="${_LT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# lt_env TEN [MAC_DINH] -> in gia tri bien trong .env
lt_env() {
  local val
  val=$(grep -E "^$1=" "$_LT_ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2-)
  printf '%s' "${val:-$2}"
}

LT_WEB_PORT=$(lt_env WEB_PORT 5001)

# Chi mo tren loopback — xem ghi chu trong .env.
LT_HOST=127.0.0.1
LT_WEB_URL="http://${LT_HOST}:${LT_WEB_PORT}"   # nginx: UI + /api + /api2
LT_API_URL="${LT_WEB_URL}/api"                  # LibreTranslate qua proxy
LT_ENGINE_URL="${LT_WEB_URL}/api2"              # EnViT5 qua proxy
