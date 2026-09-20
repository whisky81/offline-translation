#!/usr/bin/env bash
# Toan bo REST API, bang curl.
#
# Stack chi cong bo MOT cong ra host (nginx tren loopback). LibreTranslate
# khong con cong 5000 rieng — moi thu di qua :5001 voi tien to /api, /api2, /api3.
WEB=${LT_WEB_URL:-http://127.0.0.1:5001}
BASE=${LT_URL:-$WEB/api}      # LibreTranslate
TTS=${LT_TTS_URL:-$WEB/api3}  # may doc Piper

echo "### 1. Danh sach ngon ngu"
curl -s "$BASE/languages" | jq -r '.[] | "\(.code)  \(.name)"'

echo; echo "### 2. Dich 1 doan"
curl -s -X POST "$BASE/translate" \
  -H 'Content-Type: application/json' \
  -d '{"q":"The quick brown fox jumps over the lazy dog.","source":"en","target":"vi","format":"text"}' \
  | jq

echo; echo "### 3. Dich nhieu doan cung luc (batch)"
curl -s -X POST "$BASE/translate" \
  -H 'Content-Type: application/json' \
  -d '{"q":["Good morning","Good night","See you later"],"source":"en","target":"vi","format":"text"}' \
  | jq

echo; echo "### 4. Tu nhan dien ngon ngu nguon"
curl -s -X POST "$BASE/translate" \
  -H 'Content-Type: application/json' \
  -d '{"q":"こんにちは、世界","source":"auto","target":"vi","format":"text"}' \
  | jq

echo; echo "### 5. Chi nhan dien ngon ngu"
curl -s -X POST "$BASE/detect" \
  -H 'Content-Type: application/json' \
  -d '{"q":"Đây là một câu tiếng Việt."}' | jq

echo; echo "### 6. Dich HTML (giu nguyen the)"
curl -s -X POST "$BASE/translate" \
  -H 'Content-Type: application/json' \
  -d '{"q":"<p>Hello <b>world</b></p>","source":"en","target":"vi","format":"html"}' \
  | jq -r '.translatedText'

echo; echo "### 7. Dich file (docx/odt/pptx/xlsx/txt/html)"
echo 'Hello from a plain text file. This will be translated.' > /tmp/lt-demo.txt
curl -s -X POST "$BASE/translate_file" \
  -F "file=@/tmp/lt-demo.txt" -F "source=en" -F "target=vi" | jq
echo "-> tai file ket qua tu 'translatedFileUrl' o tren"

echo; echo "### 8. Cac cap dich duoc tu tieng Viet"
curl -s "$BASE/languages" | jq -r '.[] | select(.code=="vi") | .targets | join(", ")'

echo; echo "### 9. Giong doc dang co"
curl -s "$TTS/voices" | jq -r '.[] | "\(.id)  [\(.lang)]  \(.quality)"'

echo; echo "### 10. Doc thanh tieng -> tep WAV"
# Phan hoi la AM THANH chu khong phai JSON. Thong tin phu nam o header X-*.
curl -s -D /tmp/lt-speak-headers.txt -o /tmp/lt-speak.wav -X POST "$TTS/speak" \
  -H 'Content-Type: application/json' \
  -d '{"q":"Xin chào, đây là máy đọc chạy trên chính máy bạn.","lang":"vi","speed":1.0}'
grep -i '^x-' /tmp/lt-speak-headers.txt | tr -d '\r'
echo "-> /tmp/lt-speak.wav  (nghe thu: aplay /tmp/lt-speak.wav)"

echo; echo "### 11. Doc tieng Anh, cham lai mot chut"
curl -s -o /tmp/lt-speak-en.wav -X POST "$TTS/speak" \
  -H 'Content-Type: application/json' \
  -d '{"q":"This reader runs entirely offline.","lang":"en","speed":0.85}'
echo "-> /tmp/lt-speak-en.wav"
