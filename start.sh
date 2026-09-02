#!/usr/bin/env bash
# 一键启动：自动创建虚拟环境、安装依赖、启动服务
#
# 用法:
#   ./start.sh          # 开发模式（热重载）
#   ./start.sh --prod   # 生产模式（无热重载）
#   PORT=9000 ./start.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${ROOT_DIR}/scripts/common.sh"

MODE="dev"
for arg in "$@"; do
  case "${arg}" in
    --prod) MODE="prod" ;;
    -h|--help)
      cat <<'EOF'
企业知识库 Demo — 一键启动

用法:
  ./start.sh          开发模式（默认，支持热重载）
  ./start.sh --prod   生产模式
  PORT=9000 ./start.sh  指定端口（默认 8081）

环境变量:
  PORT   服务端口，默认 8081

Windows 用户请使用 start.bat
EOF
      exit 0
      ;;
    *)
      error "未知参数: ${arg}（使用 --help 查看帮助）"
      exit 1
      ;;
  esac
done

cd "${ROOT_DIR}"

info "项目目录: ${ROOT_DIR}"
ensure_venv
ensure_env_file
ensure_dependencies
ensure_data_dirs

if grep -q 'sk-your-key' "${ROOT_DIR}/.env" 2>/dev/null; then
  warn "检测到 .env 中仍为示例 API Key，问答功能可能不可用"
  warn "请编辑 .env 填入 DEEPSEEK_API_KEY，或配置 Ollama 本地模型"
fi

info "启动服务 → http://localhost:${PORT}"
info "按 Ctrl+C 停止"

if [[ "${MODE}" == "prod" ]]; then
  exec "${VENV_DIR}/bin/uvicorn" app.main:app --host 0.0.0.0 --port "${PORT}"
else
  exec "${VENV_DIR}/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port "${PORT}"
fi
