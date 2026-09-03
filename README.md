# 企业知识库问答 Agent (Python 版)

> 本地可运行的 RAG Demo — FastAPI + LangChain + Chroma  
> Java 版见 `../enterprise-kb/`，两个项目 API 对齐，方便对照学习。  
> 架构说明见 [ARCHITECTURE.md](ARCHITECTURE.md)，学习指南见 [LEARNING.md](LEARNING.md)，企业级演进方案见 [docs/ENTERPRISE_PLAN.md](docs/ENTERPRISE_PLAN.md)，中间件安装见 [docs/MIDDLEWARE_SETUP.md](docs/MIDDLEWARE_SETUP.md)

## 功能

- 文档上传（PDF / Word / Markdown / TXT）
- Chroma 向量检索 + RAG 问答
- 引用来源返回
- SSE 流式输出
- 启动自动加载 `sample-docs/`（仅首次，不重复入库）
- 文档列表 / 删除 / 健康检查

## 快速开始

### 方式一：一键启动（推荐）

**macOS / Linux：**

```bash
cd enterprise-kb-py
./start.sh            # 自动创建虚拟环境、安装依赖、启动服务
# 编辑 .env 填入 DEEPSEEK_API_KEY（首次会自动从 .env.example 复制）
# → http://localhost:8081
```

**Windows（CMD / PowerShell）：**

```bat
cd enterprise-kb-py
start.bat             # 开发模式，自动创建 .venv、安装依赖
start.bat --prod      # 生产模式（无热重载）
set PORT=9000 && start.bat
```

等价命令（macOS / Linux）：`make start`

### 方式二：分步运行

```bash
cd enterprise-kb-py
make install          # 创建虚拟环境 + 安装依赖 + 复制 .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
make dev              # 启动服务 → http://localhost:8081
```

### 方式三：Docker

```bash
cp .env.example .env  # 填入 API Key
make docker-up        # 构建并启动 → http://localhost:8081
```

### 一键打包（分发 / 离线部署）

```bash
./package.sh              # 生成 dist/enterprise-kb-py-<版本>.tar.gz
./package.sh --docker     # 同时构建并导出 Docker 镜像
```

等价命令：`make package`

### 验证

```bash
# 健康检查
curl http://localhost:8081/api/health

# 问答（示例文档已自动入库）
curl -X POST http://localhost:8081/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"退款多久到账？"}'

# 检索预览
curl "http://localhost:8081/api/chat/sources?question=远程办公考勤"

# 文档列表
curl http://localhost:8081/api/documents
```

浏览器打开 http://localhost:8081 可使用 Web UI。

## 配置说明

### DeepSeek（推荐，默认）

DeepSeek 只提供对话 API，**Embedding 默认用本地 BGE 中文模型**（免费，首次启动会下载约 100MB）：

```bash
# .env
DEEPSEEK_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_CHAT_MODEL=deepseek-chat
EMBEDDING_PROVIDER=local
HF_ENDPOINT=https://hf-mirror.com   # 国内下载模型镜像
```

### Ollama（纯本地，无需 API Key）

```bash
# 先启动 Ollama 并拉取模型: ollama pull qwen2.5:7b
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_CHAT_MODEL=qwen2.5:7b
EMBEDDING_PROVIDER=local
```

### OpenAI 全家桶

```bash
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_CHAT_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

## 项目结构

```
app/
├── main.py              # API 路由
├── config.py            # 配置
├── models/              # 数据模型
├── store/               # SQLite 文档元数据
└── services/            # RAG 引擎 + 启动引导
data/                    # 运行时数据（向量库、上传文件、元数据）
sample-docs/             # 内置示例（退款政策、远程办公、IT FAQ）
static/                  # Web UI
```

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 服务状态 + 文档统计 + Redis/ES 状态 |
| `/api/documents` | GET | 文档列表 |
| `/api/documents/upload` | POST | 上传文档（大文件可异步入库） |
| `/api/documents/{id}` | DELETE | 删除文档 |
| `/api/jobs/{id}` | GET | 异步入库任务状态（需 Redis） |
| `/api/chat` | POST | 问答 |
| `/api/chat/stream` | GET | SSE 流式问答 |
| `/api/chat/sources` | GET | 检索预览 |
| `/api/chat/conversation` | POST | 创建会话 |
| `/api/conversations/{id}` | GET | 获取会话历史（Redis 持久化） |
| `/api/conversations/{id}` | DELETE | 清空会话 |

完整 API 文档：http://localhost:8081/docs

### Phase 3：Redis 会话 + 异步入库

配置 Redis 后（在 `.env` 设置 `MIDDLEWARE_HOST` 或 `REDIS_URL`，见 `.env.example`）：

```bash
# .env 示例
MIDDLEWARE_HOST=127.0.0.1

# 终端 1：API 服务
make dev

# 终端 2：异步入库 Worker（低内存设备 max_jobs=1）
make worker
```

- **会话持久化**：对话历史写入 Redis，重启不丢失（`CONVERSATION_STORE=auto`）
- **异步入库**：≥ `ASYNC_INGEST_THRESHOLD_MB`（默认 1MB）的文件后台处理，上传立即返回
- **任务查询**：`GET /api/jobs/{jobId}` 或页面自动轮询

未配置 Redis 时自动回退为内存会话 + 同步入库，Demo 仍可正常运行。

## 重置知识库

```bash
make reset    # 清空 data/ 目录
make dev      # 重启后会重新加载 sample-docs
```

## 学习路线

详细流程与核心代码解读见 [LEARNING.md](LEARNING.md)。

**调参对比（自动评测 chunk / topK）：**

```bash
make benchmark
# 或 ./scripts/benchmark.sh --verbose
# 结果 → data/benchmark/benchmark_rag_params.csv
```

```
Week 1                              Week 2
────────                            ────────
✅ RAG 基础闭环                      → BM25 + 向量混合检索 ✅
✅ 调 chunk / topK                  → Cross-Encoder Rerank ✅
✅ Redis 会话 + 异步入库             ✅ pgvector + MinIO
→ Query 改写 HyDE                   → LangGraph 多步检索
→ RAGAS 评估                        → 方案迁回 Java 版
```

## 面试怎么说

> 「我先用 Python + LangChain 快速验证了 RAG 链路（切分策略、向量检索、引用来源），  
> 确认方案可行后，用 Spring AI 做了企业级落地，接入了 Redis 会话和 PGVector。」
