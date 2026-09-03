# 企业知识库 RAG 学习指南

本文按「先懂概念 → 再跟代码 → 动手实验 → 进阶方向」整理，帮你把本项目的知识库搭建流程串起来。

相关文档：

- [README.md](../../README.md) — 快速开始与配置
- [ARCHITECTURE.md](../tech/ARCHITECTURE.md) — 分层架构与设计决策
- [文档中心](../README.md) — 全部分层文档入口

---

## 一、先建立心智模型：RAG 是什么？

**RAG（Retrieval-Augmented Generation）= 检索增强生成**

传统 LLM 只靠训练数据回答，容易「瞎编」。RAG 的做法是：

```
你的文档 → 切成小段 → 转成向量 → 存入向量库
                                    ↓
用户提问 → 转成向量 → 找最相关的片段 → 拼进 Prompt → LLM 基于上下文回答
```

本项目的完整链路可以概括为 **两条线**：

| 阶段 | 做什么 | 对应 API |
|------|--------|----------|
| **入库（Indexing）** | 加载 → 切分 → 向量化 → 存储 | `POST /api/documents/upload` |
| **问答（Query）** | 检索 → 拼上下文 → LLM 生成 | `POST /api/chat` |

---

## 二、系统架构：谁负责什么？

```
Web UI (static/)
    ↓ HTTP
API 层 (main.py)          ← 路由、参数校验、文件上传
    ↓
RagEngine (rag_engine.py) ← 核心：入库 / 检索 / 对话
    ├── Chroma 向量库       ← 存 embedding，做相似度搜索
    ├── BGE / OpenAI       ← 文本 → 向量
    ├── DeepSeek / Ollama  ← 根据上下文生成回答
    └── DocumentStore      ← SQLite 记文档元数据（文件名、chunk 数等）
```

**设计要点：**

- **Chroma** 存向量（语义检索）
- **SQLite** 存元数据（列表、删除、统计）
- 两者通过 `doc_id` 关联，删除文档时两边一起删

---

## 三、核心代码精读（按执行顺序）

### 1. 启动时发生了什么？

```25:29:app/main.py
@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = get_rag_engine()
    bootstrap_sample_docs(engine)
    yield
```

启动流程：

1. 创建 `RagEngine`（加载 BGE 模型、连接 Chroma、初始化 LLM）
2. `bootstrap_sample_docs`：若 SQLite 为空，自动加载 `sample-docs/` 下 3 篇示例文档

```12:16:app/services/bootstrap.py
def bootstrap_sample_docs(engine: RagEngine) -> int:
    """首次启动时加载示例文档，避免重复入库。"""
    if engine.doc_store.count() > 0:
        logger.info("Document store not empty, skipping sample docs bootstrap")
        return 0
```

`make reset` 清空 `data/` 后重启，会重新加载示例文档。

---

### 2. 文档入库：`ingest_file`（最重要）

```89:139:app/services/rag_engine.py
    def ingest_file(
        self,
        file_path: Path,
        filename: str,
        ...
    ) -> int:
        ...
            docs = self._load_documents(file_path, filename)
            for doc in docs:
                doc.metadata["doc_id"] = doc_id
                doc.metadata["filename"] = filename

            chunks = self.splitter.split_documents(docs)
            ...
            self.vectorstore.add_documents(chunks)

            if persist_metadata:
                self.doc_store.add(
                    DocumentRecord(...)
                )
```

**四步流水线：**

```
① Loader 加载原文
   PDF  → PyPDFLoader
   Word → Docx2txtLoader
   MD/TXT → TextLoader

② Splitter 切分
   RecursiveCharacterTextSplitter
   chunk_size=512, chunk_overlap=64

③ Embedding 向量化
   本地 BGE-small-zh 或 OpenAI Embedding

④ 写入
   Chroma.add_documents(chunks)   → 向量索引
   DocumentStore.add(record)      → 元数据
```

**为什么要切分？**  
LLM 上下文有限，整篇文档无法一次塞入。切成 512 字左右的片段，检索时只取最相关的几块。

**`chunk_overlap=64` 的作用：**  
相邻 chunk 有 64 字重叠，避免句子在边界被截断导致语义断裂。

---

### 3. 问答检索：`chat`

```186:197:app/services/rag_engine.py
    def chat(self, question: str, conversation_id: str) -> tuple[str, list[RetrievedChunk]]:
        sources = self.retrieve_sources(question)
        context = "\n\n".join(f"[{s.filename}] {s.content}" for s in sources)
        history = self._format_history(conversation_id)

        chain = self._prompt | self.llm
        answer = chain.invoke(
            {"context": context or "（无相关上下文）", "history": history, "question": question}
        ).content
```

**五步：**

```
① similarity_search_with_score(question, k=TOP_K)  → 取 top 4 相关 chunk
② 拼接完整 chunk 内容作为 context（不是 snippet）
③ 取最近 3 轮对话作为 history
④ 填入 Prompt 模板，调用 LLM
⑤ 返回答案 + sources（引用来源）
```

**Prompt 模板：**

```78:87:app/services/rag_engine.py
        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是企业内部知识库助手。仅根据提供的上下文回答，"
                    "不知道就说不知道。回答简洁，并在末尾列出引用文档名。",
                ),
                ("human", "上下文:\n{context}\n\n历史:\n{history}\n\n问题: {question}"),
            ]
        )
```

System 约束「只根据上下文回答」，是减少幻觉的关键。

> **注意：** `snippet`（200 字截断）仅用于 API 预览展示；LLM 实际使用的是完整 `content`。

---

### 4. 可调参数（`.env`）

| 参数 | 默认值 | 影响 |
|------|--------|------|
| `RAG_CHUNK_SIZE` | 512 | chunk 越大，单段信息越完整，但检索粒度变粗 |
| `RAG_CHUNK_OVERLAP` | 64 | 重叠越多，边界信息保留越好，但存储量增加 |
| `RAG_TOP_K` | 4 | 检索片段数，越多上下文越丰富，但可能引入噪声 |
| `EMBEDDING_PROVIDER` | local | `local`=BGE 免费；`openai`=需 API Key |
| `LOCAL_EMBEDDING_MODEL` | BAAI/bge-small-zh-v1.5 | 中文 embedding 模型 |

这些参数是 RAG 调优的**第一战场**，建议边改边测。

---

## 四、动手学习路线（建议顺序）

### Step 0：跑起来

```bash
./start.sh
# 浏览器打开 http://localhost:8081
# 问：「退款多久到账？」
```

Windows 用户：`start.bat`

### Step 1：观察入库结果

```bash
curl http://localhost:8081/api/health
# {"documents":3, "ready_documents":3}

curl http://localhost:8081/api/documents
# 看每篇文档的 chunkCount
```

打开 `sample-docs/refund-policy.md`，对照 chunk 数量，理解切分效果。

### Step 2：只看检索，不看生成

```bash
curl "http://localhost:8081/api/chat/sources?question=退款多久到账"
```

返回 `filename`、`snippet`、`score`。  
**score 越小通常表示越相似**（Chroma 默认用 L2 距离）。

试着换问题：

- 「远程办公考勤怎么算？」→ 应命中 `remote-work-policy.md`
- 「VPN 连不上怎么办？」→ 应命中 `it-faq.md`

### Step 3：完整问答

```bash
curl -X POST http://localhost:8081/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"购买后几天内可以全额退款？"}'
```

看 `answer` 和 `sources`，确认答案来自文档而非编造。

### Step 4：上传自己的文档

在 Web UI 上传一份 `.md` 或 `.pdf`，再问相关问题，走一遍完整入库链路。

### Step 5：调参实验

**方式 A — 自动对比脚本（推荐）**

在 `sample-docs` 上批量测试多组 `chunk_size` / `top_k`，输出命中率表格，**不调用 LLM、不污染生产向量库**：

```bash
make benchmark
# 或
./scripts/benchmark.sh --verbose

# 自定义参数网格
./scripts/benchmark.sh --chunk-sizes 256,512 --top-k-values 3,4,5 --verbose
```

结果写入 `data/benchmark/benchmark_rag_params.csv` 与 `.json`。指标说明：

| 指标 | 含义 |
|------|------|
| `hit@1` | Top1 检索结果是否来自期望文档 |
| `hit@k` | Top-K 内是否包含期望文档 |
| `avg_score` | Top1 相似度分数（L2，越小越相似） |
| `ctx_chars` | Top-K 拼接后的上下文字符数 |

**方式 B — 手动改 .env 验证问答**

```bash
# .env 中修改
RAG_CHUNK_SIZE=256
RAG_TOP_K=6
```

`make reset && make dev` 后重新入库，对比检索质量和回答变化。

---

## 五、关键概念速查

| 概念 | 本项目实现 | 一句话理解 |
|------|-----------|-----------|
| **Document** | LangChain `Document` | 一篇文档 + metadata |
| **Chunk** | `split_documents` 产物 | 检索的最小单位 |
| **Embedding** | BGE / OpenAI | 文本 → 高维向量，语义相近的文本向量距离近 |
| **Vector Store** | Chroma | 存向量，支持相似度搜索 |
| **Top-K** | `similarity_search(k=4)` | 取最相关的 K 个 chunk |
| **Prompt** | `ChatPromptTemplate` | 把 context + history + question 交给 LLM |
| **Metadata** | SQLite `documents` 表 | 文档列表、删除、统计，不参与语义检索 |

---

## 六、数据存在哪？

```
data/
├── chroma/          # 向量索引（Chroma 自动生成）
├── uploads/         # 用户上传的原始文件
├── benchmark/       # 调参脚本输出（make benchmark）
└── metadata.db      # SQLite 文档元数据
```

`make reset` 会清空整个 `data/`，下次启动重新 bootstrap。

---

## 七、文件阅读顺序（建议）

想深入代码，按这个顺序读：

```
1. app/config.py               → 所有配置入口
2. app/models/domain.py        → 数据结构
3. app/services/rag_engine.py  → 核心逻辑（重点）
4. app/store/document_store.py → 元数据持久化
5. app/main.py                 → API 如何调用 RagEngine
6. app/services/bootstrap.py   → 启动加载逻辑
7. static/index.html           → 前端如何调 API
```

**核心文件只有一个：`app/services/rag_engine.py`**，约 260 行，涵盖 RAG 全链路。

---

## 八、当前局限 & 进阶方向

| 现状 | 进阶方向 | 学习价值 |
|------|----------|----------|
| 纯向量检索 | BM25 + 向量混合检索 | 关键词 + 语义互补 |
| 无 Rerank | Cross-Encoder 重排序 | 提升 top-K 精度 |
| 无 Query 改写 | HyDE / 多查询扩展 | 提升召回率 |
| 内存会话 | Redis 持久化 | 生产级会话管理 |
| 无评估 | RAGAS 指标 | 量化回答质量 |

README 中的学习路线：

```
Week 1 ✅ RAG 基础闭环、调 chunk/topK
Week 2 → BM25 混合检索、Cross-Encoder Rerank
Week 3 → Query 改写、LangGraph 多步检索
Week 4 → RAGAS 评估、迁回 Java 版
```

---

## 九、一句话总结

> **知识库搭建 = 把文档切成 chunk → 向量化存进 Chroma → 用户提问时检索相关 chunk → 拼进 Prompt 让 LLM 回答。**

本项目的价值在于：用约 260 行核心代码把这条链路跑通，参数可调、API 可测、示例文档可对照。建议先跑通 Step 0–5，再读 `rag_engine.py`，最后动手改 `RAG_CHUNK_SIZE` / `RAG_TOP_K` 观察效果。
