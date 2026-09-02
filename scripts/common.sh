#!/usr/bin/env bash
# Shared helpers for start/package scripts.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"
PORT="${PORT:-8081}"

info()  { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }

require_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    error "未找到 python3，请先安装 Python 3.10+"
    exit 1
  fi
}

ensure_venv() {
  require_python
  if [[ ! -x "${PYTHON}" ]]; then
    info "创建虚拟环境..."
    python3 -m venv "${VENV_DIR}"
  fi
}

ensure_env_file() {
  if [[ ! -f "${ROOT_DIR}/.env" ]]; then
    info "复制 .env.example → .env"
    cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
    warn "请编辑 .env 填入 API Key（DeepSeek 或 Ollama）"
  fi
}

ensure_dependencies() {
  local marker="${VENV_DIR}/.deps-installed"
  if [[ ! -f "${marker}" ]]; then
    info "安装 Python 依赖（首次较慢）..."
    "${PIP}" install -r "${ROOT_DIR}/requirements.txt"
    touch "${marker}"
  fi
}

ensure_data_dirs() {
  mkdir -p "${ROOT_DIR}/data/chroma" "${ROOT_DIR}/data/uploads"
}
