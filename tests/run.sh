#!/usr/bin/env bash
# Chay toan bo test.
#   ./tests/run.sh            tat ca
#   ./tests/run.sh api        chi test API + Web UI (can may chu dang chay)
#   ./tests/run.sh setup      chi test cau hinh (khong can may chu)
#   ./tests/run.sh edge       chi test ca xau / ca bien
#   ./tests/run.sh web        chi test UI tieng Viet + proxy
#   ./tests/run.sh engine     chi test engine EnViT5
#   ./tests/run.sh ext        chi test extension Brave
#   ./tests/run.sh pdf        chi test trinh doc PDF (chay Brave that)
#   ./tests/run.sh tts        chi test may doc (may chu + ma nguon)
#   ./tests/run.sh ttsui      chi test doc thanh tieng trong trinh duyet that
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

B=$'\e[1m'; N=$'\e[0m'
which=${1:-all}
rc=0

run() {
  echo "${B}=== $1 ===${N}"
  python3 -m unittest "$2" -v 2>&1 | tail -n +1
  [ "${PIPESTATUS[0]}" -eq 0 ] || rc=1
  echo
}

case "$which" in
  api)   run "API + Web UI" tests.test_api ;;
  setup) run "Cau hinh project" tests.test_setup ;;
  edge)  run "Ca xau va ca bien" tests.test_edge_cases ;;
  web)   run "UI tieng Viet + proxy" tests.test_web ;;
  engine) run "Engine EnViT5" tests.test_engine ;;
  ext)   run "Extension Brave" tests.test_extension ;;
  pdf)   run "Trinh doc PDF" tests.test_pdf_viewer ;;
  tts)   run "May doc Piper" tests.test_tts ;;
  ttsui) run "Doc thanh tieng trong trinh duyet" tests.test_tts_browser ;;
  all)
    run "Cau hinh project" tests.test_setup
    run "API + Web UI"     tests.test_api
    run "UI tieng Viet"    tests.test_web
    run "Engine EnViT5"    tests.test_engine
    run "Ca xau / ca bien" tests.test_edge_cases
    run "May doc Piper"    tests.test_tts
    run "Extension Brave"  tests.test_extension
    run "Trinh doc PDF"    tests.test_pdf_viewer
    run "Doc thanh tieng"  tests.test_tts_browser ;;
  *) echo "Dung: $0 [all|api|setup|edge|web|engine|ext|pdf|tts|ttsui]"; exit 1 ;;
esac

if [ "$rc" -eq 0 ]; then echo "${B}Tat ca test dat.${N}"; else echo "${B}Co test that bai.${N}"; fi
exit $rc
