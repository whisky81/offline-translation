# Nguon chung cho moi script trong project. Source, khong chay truc tiep.
#
# Co lap hoan toan khoi Docker Desktop:
#   DOCKER_HOST   -> ep noi thang toi Docker Engine he thong, bo qua context
#   DOCKER_CONFIG -> dung docker-config/ cua project thay vi ~/.docker
#                    (tranh credsStore=desktop va cac hook plugin cua Desktop)
#   DOCKER_CONTEXT bi unset vi neu dat cung DOCKER_HOST se xung dot
#
# Ghi de duoc bang LT_DOCKER_HOST / LT_DOCKER_CONFIG neu can.

_LT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DOCKER_HOST="${LT_DOCKER_HOST:-unix:///var/run/docker.sock}"
export DOCKER_CONFIG="${LT_DOCKER_CONFIG:-$_LT_ROOT/docker-config}"
unset DOCKER_CONTEXT

# Tro thang toi binary cua docker-ce, khong dung ban cua Docker Desktop o
# /usr/lib/docker/cli-plugins. Symlink duoc tao tai cho vi duong dan he thong
# khac nhau giua cac may — commit chung se thanh symlink chet khi clone.
_lt_link_plugins() {
  local dir="$DOCKER_CONFIG/cli-plugins" src
  mkdir -p "$dir" 2>/dev/null || return 0
  local plug
  for plug in compose buildx; do
    [ -e "$dir/docker-$plug" ] && continue
    for src in /usr/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins \
               /usr/local/lib/docker/cli-plugins; do
      if [ -x "$src/docker-$plug" ]; then
        ln -sfn "$src/docker-$plug" "$dir/docker-$plug"
        break
      fi
    done
  done
}
_lt_link_plugins

# Goi compose dung project dir, de .env luon duoc doc.
lt_compose() { docker compose --project-directory "$_LT_ROOT" "$@"; }
