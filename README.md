# 企业知识库问答 Agent (Python 版)

> **面试学习专用** — FastAPI + LangChain + Chroma  
> Java 版见 `../enterprise-kb/`，两个项目 API 对齐，方便对照学习。

## 为什么单独起一个 Python 项目？

| 维度 | Java (`enterprise-kb`) | Python (`enterprise-kb-py`) |
|------|------------------------|------------------------------|
| 面试叙事 | 「企业级落地、Spring 生态整合」 | 「RAG/Agent 原理、快速实验」 |
| 生态 | Spring AI，资料相对少 | LangChain/LangGraph，教程和案例最多 |
| 迭代速度 | 编译 + 配置重 | 改几行就能跑，适合调参 |
| 简历定位 | 主项目，写进工作经历 | 学习项目，体现技术广度 |

**建议分工**：Python 用来**快速学透 RAG 链路**（2 周内把混合检索、Rerank、LangGraph 跑通），Java 用来**包装成可讲的生产项目**（Redis 会话、SSE、PGVector、监控）。

## 功能

- 文档上传（PDF / Word / Markdown）
- Chroma 向量检索 + RAG 问答
- 引用来源返回
- SSE 流式输出
- 启动自动加载 `sample-docs/`

## 快速开始

```bash
cd enterprise-kb-py
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY（或 export DEEPSEEK_API_KEY=sk-xxx）

uvicorn app.main:app --reload --port 8081
```

浏览器打开 http://localhost:8081（端口 8081 避免和 Java 版冲突）

### DeepSeek 配置（推荐）

DeepSeek 只提供对话 API，**Embedding 默认用本地 BGE 中文模型**（免费，首次启动会下载）：

```bash
# .env 中配置
DEEPSEEK_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_CHAT_MODEL=deepseek-chat
EMBEDDING_PROVIDER=local
HF_ENDPOINT=https://hf-mirror.com   # 国内下载模型用
```

面试话术：「对话走 DeepSeek，向量检索用本地 BGE，避免 Embedding API 成本和网络依赖。」

## API（与 Java 版一致）

```bash
curl http://localhost:8081/api/health
curl -X POST http://localhost:8081/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"退款多久到账？"}'
curl "http://localhost:8081/api/chat/sources?question=远程办公考勤"
```

## 2 周学习路线（Python 主攻）

```
Week 1（Python）                    Week 2（Python → Java 迁移）
──────────────                      ────────────────────────────
✅ 跑通 RAG 基础                     → BM25 + 向量混合检索 (3.3)
✅ 调 chunk / topK                  → Cross-Encoder Rerank (3.4)
→ Query 改写 HyDE (3.5)            → LangGraph 多步检索 (2.3)
→ RAGAS 评估 (3.6)                 → 把验证过的方案迁回 Java 版
```

## 面试怎么说

> 「我先用 Python + LangChain 快速验证了 RAG 链路（切分策略、混合检索、Rerank），  
> 确认方案可行后，用 Spring AI 做了企业级落地，接入了 Redis 会话和 PGVector。」

这样既体现了 **AI 工程能力**，又保留了 **Java 后端** 的核心优势。
