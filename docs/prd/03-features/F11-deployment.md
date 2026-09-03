# F11 · 部署与打包

## 1. 背景与目标

降低安装门槛：一条命令启动开发环境，支持 Docker 与企业中间件 compose，支持源码打包分发。

## 2. 用户故事 / 场景

- 作为新用户，我执行 `./start.sh` 自动建 venv、装依赖、启动服务。
- 作为 Windows 用户，我执行 `start.bat` 同等体验。
- 作为运维，我用 `docker compose up` 或企业版 compose 部署中间件。

## 3. 功能范围

**In**

- `start.sh` / `start.bat` — 一键启动（dev/prod）
- `package.sh` — 源码 tar.gz，可选 Docker 镜像导出
- `Makefile` — install / dev / worker / benchmark / docker-up / reset
- `Dockerfile` + `docker-compose.yml` — 应用容器
- `docker-compose.enterprise.yml` — Redis/ES/PG/MinIO 模板
- `scripts/common.sh` — 公共逻辑
- `.dockerignore` — 构建排除

**Out**

- Kubernetes Helm Chart
- 多区域 CDN 静态资源
- 自动 SSL 证书

## 4. 主流程与边界

1. `start.sh`：检测 Python → venv → pip install → 复制 `.env` → uvicorn。
2. `package.sh`：排除 `.venv`/`data`/`.git` → `dist/*.tar.gz`。
3. 企业中间件：独立 compose，与应用解耦。

**边界**：首次 BGE 模型下载需网络；国内建议 `HF_ENDPOINT` 镜像。

## 5. 关键配置键

| 键 | 默认 | 用途 |
|---|---|---|
| `PORT` | 8081 | 服务端口 |
| `HF_ENDPOINT` | — | HuggingFace 镜像 |

## 6. 代码锚点

- `start.sh`, `start.bat`, `package.sh`
- `Makefile`, `Dockerfile`, `docker-compose*.yml`
- `scripts/common.sh`, `scripts/worker.sh`

## 7. 验收标准

- [ ] 全新克隆后 `./start.sh` 可访问 :8081
- [ ] `make package` 生成 dist 压缩包，解压后可 `./start.sh`
- [ ] `make docker-up` 容器健康检查通过
- [ ] `start.bat --help` 在 Windows 可用（文档声明）

## 8. 已知缺口 / 待迭代

- 无 Windows 版 `package.bat`
- 无 GitHub Actions 自动发布
- 企业 compose 资源限制需按机器手动调
