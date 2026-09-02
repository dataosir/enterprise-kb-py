#!/usr/bin/env bash
# 一键打包：生成可分发的源码压缩包，可选构建 Docker 镜像
#
# 用法:
#   ./package.sh              # 打包源码 tar.gz
#   ./package.sh --docker     # 同时构建 Docker 镜像
#   ./package.sh --docker-only

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${ROOT_DIR}/scripts/common.sh"

PROJECT_NAME="enterprise-kb-py"
DIST_DIR="${ROOT_DIR}/dist"
STAGE_DIR=""
ARCHIVE_NAME=""
BUILD_SOURCE=true
BUILD_DOCKER=false
DOCKER_ONLY=false

usage() {
  cat <<'EOF'
企业知识库 Demo — 一键打包

用法:
  ./package.sh                打包源码（默认输出 dist/*.tar.gz）
  ./package.sh --docker       打包源码 + 构建 Docker 镜像
  ./package.sh --docker-only  仅构建 Docker 镜像

输出:
  dist/enterprise-kb-py-<版本>.tar.gz   源码包（不含 .venv / .env / data）
  dist/enterprise-kb-py-<版本>.tar      Docker 镜像（使用 --docker 时）
EOF
}

resolve_version() {
  if command -v git >/dev/null 2>&1 && git -C "${ROOT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    local tag
    tag="$(git -C "${ROOT_DIR}" describe --tags --always --dirty 2>/dev/null || true)"
    if [[ -n "${tag}" ]]; then
      echo "${tag}"
      return
    fi
  fi
  date +%Y%m%d
}

package_source() {
  local version="$1"
  ARCHIVE_NAME="${PROJECT_NAME}-${version}.tar.gz"
  STAGE_DIR="${DIST_DIR}/${PROJECT_NAME}-${version}"

  info "打包源码 → dist/${ARCHIVE_NAME}"

  rm -rf "${STAGE_DIR}"
  mkdir -p "${STAGE_DIR}" "${DIST_DIR}"

  rsync -a \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude '.env' \
    --exclude 'data' \
    --exclude 'dist' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.DS_Store' \
    --exclude '.chroma' \
    "${ROOT_DIR}/" "${STAGE_DIR}/"

  tar -czf "${DIST_DIR}/${ARCHIVE_NAME}" -C "${DIST_DIR}" "${PROJECT_NAME}-${version}"

  rm -rf "${STAGE_DIR}"

  local size
  size="$(du -h "${DIST_DIR}/${ARCHIVE_NAME}" | cut -f1)"
  info "源码包已生成: dist/${ARCHIVE_NAME} (${size})"
}

build_docker_image() {
  local version="$1"
  local image_tag="${PROJECT_NAME}:${version}"
  local image_file="${DIST_DIR}/${PROJECT_NAME}-${version}.tar"

  if ! command -v docker >/dev/null 2>&1; then
    error "未找到 docker，请先安装 Docker"
    exit 1
  fi

  mkdir -p "${DIST_DIR}"
  info "构建 Docker 镜像 → ${image_tag}"
  docker build -t "${image_tag}" -t "${PROJECT_NAME}:latest" "${ROOT_DIR}"

  info "导出镜像 → dist/$(basename "${image_file}")"
  docker save -o "${image_file}" "${image_tag}"

  local size
  size="$(du -h "${image_file}" | cut -f1)"
  info "镜像已导出: dist/$(basename "${image_file}") (${size})"
  info "加载镜像: docker load -i dist/$(basename "${image_file}")"
}

for arg in "$@"; do
  case "${arg}" in
    --docker)      BUILD_DOCKER=true ;;
    --docker-only) BUILD_DOCKER=true; BUILD_SOURCE=false; DOCKER_ONLY=true ;;
    -h|--help)     usage; exit 0 ;;
    *)
      error "未知参数: ${arg}（使用 --help 查看帮助）"
      exit 1
      ;;
  esac
done

cd "${ROOT_DIR}"
VERSION="$(resolve_version)"
info "版本: ${VERSION}"

if [[ "${BUILD_SOURCE}" == true ]]; then
  if ! command -v rsync >/dev/null 2>&1; then
    error "未找到 rsync，macOS/Linux 通常自带，请先安装"
    exit 1
  fi
  package_source "${VERSION}"
fi

if [[ "${BUILD_DOCKER}" == true ]]; then
  build_docker_image "${VERSION}"
fi

echo ""
info "打包完成"
if [[ "${BUILD_SOURCE}" == true ]]; then
  echo "  源码包: dist/${ARCHIVE_NAME}"
  echo "  解压运行: tar -xzf dist/${ARCHIVE_NAME} && cd ${PROJECT_NAME}-* && ./start.sh"
  echo "  Windows:  解压后进入目录，运行 start.bat"
fi
if [[ "${BUILD_DOCKER}" == true ]]; then
  echo "  Docker: docker compose up -d  或  docker run -p 8081:8081 --env-file .env ${PROJECT_NAME}:${VERSION}"
fi
