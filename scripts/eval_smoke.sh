#!/usr/bin/env bash
# L1 + L2 评测冒烟：切分分析 → 检索 benchmark → 基线对比
# 不调用 LLM，适合本地快速回归与 CI。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "${ROOT_DIR}/scripts/common.sh"

ensure_venv
ensure_dependencies

cd "${ROOT_DIR}"

info "L1: 切分内在指标"
"${PYTHON}" scripts/analyze_chunks.py --chunk-size 512 --chunk-overlap 64

info "L2: 检索 benchmark（smoke 网格）"
"${PYTHON}" scripts/benchmark_rag_params.py \
  --chunk-sizes 512 \
  --top-k-values 4 \
  --chunk-overlap 64 \
  --modes vector

info "基线对比"
"${PYTHON}" scripts/check_eval_baseline.py

info "评测冒烟通过"
