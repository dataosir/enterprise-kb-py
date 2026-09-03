#!/usr/bin/env bash
# 在 NAS / 服务器上执行（需能访问 kb-postgres 容器）
# 用法: ./scripts/reset-pg-password.sh
# 或:   POSTGRES_PASSWORD=你的密码 ./scripts/reset-pg-password.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

CONTAINER="${PG_CONTAINER:-kb-postgres}"
USER="${POSTGRES_USER:-kb}"
DB="${POSTGRES_DB:-enterprise_kb}"
NEW_PASSWORD="${POSTGRES_PASSWORD:-changeme_pg_password}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "错误: 未找到运行中的容器 $CONTAINER"
  echo "请在 NAS 上确认: docker ps | grep postgres"
  exit 1
fi

echo "重置 PostgreSQL 用户 $USER 的密码（容器 $CONTAINER）..."
docker exec -i "$CONTAINER" psql -U "$USER" -d "$DB" -v ON_ERROR_STOP=1 \
  -c "ALTER USER ${USER} WITH PASSWORD '${NEW_PASSWORD}';"

echo "完成。连接串示例:"
echo "postgresql://${USER}:${NEW_PASSWORD}@<MIDDLEWARE_HOST>:${POSTGRES_HOST_PORT:-5433}/${DB}"
