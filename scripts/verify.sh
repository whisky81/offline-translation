#!/usr/bin/env bash
# Kiem tra may chu chay dung: Web UI, REST API, cac cap ngon ngu, CORS, toc do.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/scripts/_config.sh"
BASE="$LT_API_URL"

G=$'\e[32m'; R=$'\e[31m'; Y=$'\e[33m'; B=$'\e[1m'; N=$'\e[0m'
pass=0; failn=0
ok()   { echo "  ${G}PASS${N} $*"; pass=$((pass+1)); }
bad()  { echo "  ${R}FAIL${N} $*"; failn=$((failn+1)); }

echo "${B}=== Kiem tra LibreTranslate tai $BASE ===${N}"
echo

echo "[1] Ket noi"
if curl -sf --max-time 5 "$BASE/languages" >/dev/null; then
  ok "May chu phan hoi"
else
  bad "Khong ket noi duoc. Xem: ./scripts/ltctl status"
  exit 1
fi

echo
echo "[2] Giao dien va be mat mang"
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$LT_WEB_URL/")
[ "$code" = "200" ] && ok "UI tieng Viet -> 200" || bad "UI tieng Viet -> $code"
code=$(curl -sL -o /dev/null -w '%{http_code}' --max-time 10 "$LT_WEB_URL/docs/")
[ "$code" = "200" ] && ok "Swagger -> 200" || bad "Swagger -> $code"
if ss -ltn 2>/dev/null | grep -qE '127\.0\.0\.1:'"$LT_WEB_PORT"'\b'; then
  ok "chi lang nghe tren loopback 127.0.0.1:$LT_WEB_PORT"
else
  bad "cong $LT_WEB_PORT khong lang nghe tren loopback"
fi
extra=$(ss -ltn 2>/dev/null | grep -cE '0\.0\.0\.0:(5000|5001|8000)\b' || true)
[ "${extra:-0}" = "0" ] && ok "khong co cong nao mo ra moi giao dien" \
                        || bad "co cong mo ra 0.0.0.0"
acao=$(curl -s -D- -o /dev/null --max-time 8 -H 'Origin: https://la.example' "$BASE/languages" \
       | grep -ci '^access-control-allow-origin' || true)
[ "${acao:-0}" = "0" ] && ok "khong mo CORS cho origin la" \
                       || bad "CORS mo cho moi origin — trang web bat ky dung duoc may chu nay"

echo
echo "[3] Ngon ngu da tai"
LANGS=$(curl -sf --max-time 10 "$BASE/languages")
codes=$(echo "$LANGS" | jq -r '.[].code' | sort | tr '\n' ' ')
echo "      co: $codes"
for c in en vi zh-Hans ja ko; do
  echo "$codes" | grep -qw "$c" && ok "co '$c'" || bad "thieu '$c'"
done
echo "      (gui request dung 'zh' cung duoc, may chu tu quy ve 'zh-Hans')"

echo
echo "[4] Dich thu (REST API)"
try() { # src tgt text
  local s=$1 t=$2 q=$3 out
  out=$(jq -n --arg q "$q" --arg s "$s" --arg t "$t" '{q:$q,source:$s,target:$t,format:"text"}' \
        | curl -sf --max-time 120 -X POST "$BASE/translate" \
            -H 'Content-Type: application/json' --data @- | jq -r '.translatedText // empty')
  if [ -n "$out" ]; then ok "$s -> $t : \"$q\"  =>  \"$out\""
  else bad "$s -> $t that bai"; fi
}
try en vi "Good morning, how are you today?"
try vi en "Hôm nay trời đẹp quá."
try en ja "The server is running locally."
try en ko "Translation without internet."
try en zh "Local translation server."
echo "      (cap khong co model truc tiep se tu dich bac cau qua tieng Anh)"
try vi ja "Tôi đang học lập trình."

echo
echo "[5] Tu nhan dien ngon ngu"
det=$(jq -n '{q:"Xin chào, rất vui được gặp bạn"}' \
      | curl -sf --max-time 30 -X POST "$BASE/detect" \
          -H 'Content-Type: application/json' --data @- | jq -r '.[0].language // empty')
[ "$det" = "vi" ] && ok "/detect nhan ra 'vi'" || bad "/detect tra ve '${det:-rong}'"

auto=$(jq -n '{q:"Xin chào thế giới", source:"auto", target:"en", format:"text"}' \
      | curl -sf --max-time 60 -X POST "$BASE/translate" \
          -H 'Content-Type: application/json' --data @- | jq -r '.translatedText // empty')
[ -n "$auto" ] && ok "source:auto hoat dong => \"$auto\"" || bad "source:auto that bai"

echo
echo "[6] Dich hang loat (batch) - huu ich cho app"
batch=$(jq -n '{q:["one","two","three"], source:"en", target:"vi", format:"text"}' \
      | curl -sf --max-time 60 -X POST "$BASE/translate" \
          -H 'Content-Type: application/json' --data @- | jq -r '.translatedText | join(" | ")')
[ -n "$batch" ] && ok "mang 3 chuoi => $batch" || bad "batch that bai"

echo
echo "[7] Dich file"
fmts=$(curl -sf --max-time 10 "$BASE/frontend/settings" | jq -r '.supportedFilesFormat | join(" ")')
[ -n "$fmts" ] && ok "POST /translate_file ho tro: $fmts" || bad "dich file dang tat"

echo
echo "[8] Be mat tan cong"
hdr=$(curl -s -D- -o /dev/null --max-time 10 "$BASE/languages")
if echo "$hdr" | grep -qi '^access-control-allow-origin'; then
  fail_msg=$(echo "$hdr" | grep -i '^access-control-allow-origin' | tr -d '\r')
  bad "van gui CORS: $fail_msg"
else
  ok "khong gui header CORS (trang web ngoai khong dung duoc may chu nay)"
fi
csp=$(curl -sI --max-time 10 "$LT_WEB_URL/" | grep -ci '^content-security-policy' || true)
[ "${csp:-0}" = "1" ] && ok "UI co Content-Security-Policy" || bad "UI thieu Content-Security-Policy"

echo "[9] Do tre"
t0=$(date +%s%N)
jq -n '{q:"This is a short latency probe sentence.",source:"en",target:"vi",format:"text"}' \
  | curl -sf --max-time 60 -X POST "$BASE/translate" \
      -H 'Content-Type: application/json' --data @- >/dev/null
t1=$(date +%s%N)
echo "      1 cau ngan: $(( (t1-t0)/1000000 )) ms"

echo
echo "[10] Tai nguyen container"
. "$PROJECT_DIR/scripts/_docker-env.sh" 2>/dev/null || true
docker stats --no-stream \
  --format '      RAM {{.MemUsage}}  |  CPU {{.CPUPerc}}' libretranslate 2>/dev/null \
  || echo "      (khong doc duoc docker stats)"

echo
echo "${B}=== $pass dat / $failn loi ===${N}"
[ "$failn" -eq 0 ] && echo "${G}Tat ca on. UI tieng Viet: $LT_WEB_URL/${N}" || echo "${Y}Co loi, xem: ./scripts/ltctl logs -n 200${N}"
exit $([ "$failn" -eq 0 ] && echo 0 || echo 1)
