#!/usr/bin/env bash
# 启动 ARQ 异步入库 Worker（需已配置 REDIS_URL）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "${ROOT_DIR}/scripts/common.sh"

cd "${ROOT_DIR}"
ensure_venv

if ! grep -qE '^(REDIS_URL=.|MIDDLEWARE_HOST=.)' "${ROOT_DIR}/.env" 2>/dev/null; then
  error "未配置 Redis。请在 .env 中设置 MIDDLEWARE_HOST 或 REDIS_URL（见 .env.example）"
  exit 1
fi

info "启动异步入库 Worker（max_jobs=1，适合低内存设备）..."
exec "${ROOT_DIR}/.venv/bin/arq" app.worker.settings.WorkerSettings
