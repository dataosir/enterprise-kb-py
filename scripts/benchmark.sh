#!/usr/bin/env bash
# 一键运行 RAG 调参对比（chunk_size / top_k）

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "${ROOT_DIR}/scripts/common.sh"

ensure_venv
ensure_dependencies

cd "${ROOT_DIR}"
exec "${PYTHON}" scripts/benchmark_rag_params.py "$@"
