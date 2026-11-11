#!/bin/sh
set -eu
cd "$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
docker compose version >/dev/null
case "${1:-start}" in
  start)
    if [ ! -f .env ]; then
      (umask 077; cp deploy/demo.env.example .env)
      printf '%s\n' '已创建 .env，默认仅本机 http://localhost:8769。服务器地址设置见 docs/deployment/package.md。'
    fi
    docker compose config --quiet
    docker compose up -d --build --wait --wait-timeout 180
    docker compose ps
    ;;
  password)
    docker compose run --rm --no-deps flow node /app/set_password.mjs
    docker compose restart flow
    ;;
  stop) docker compose stop ;;
  status) docker compose ps ;;
  logs) docker compose logs --tail 60 ;;
  *) printf '%s\n' '用法：sh deploy.sh [start|password|stop|status|logs]'; exit 2 ;;
esac
