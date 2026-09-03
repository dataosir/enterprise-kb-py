# RAG 评测体系：切分规则、指标定义与落地规划

> 目标读者：负责调参、验收与面试陈述的开发者。  
> 本文档回答三个核心问题：**切分规则是什么？切分好不好怎么量化？整个系统怎么量化？**

---

## 1. 评测金字塔（先搞清楚量什么）

RAG 质量不能只看「回答像不像」，要分层评测。由下往上，上层依赖下层：

```
┌─────────────────────────────────────────────────────────┐
│  L4 端到端业务指标   用户满意度、工单解决率、采纳率      │
├─────────────────────────────────────────────────────────┤
│  L3 生成质量         Faithfulness、Answer Relevancy      │
├─────────────────────────────────────────────────────────┤
│  L2 检索质量         Hit@K、MRR、Context Recall          │
├─────────────────────────────────────────────────────────┤
│  L1 切分质量         块大小分布、语义完整度、入库效率     │
└─────────────────────────────────────────────────────────┘
```

**面试要点**：切分不好 → 检索再好也救不了；检索不好 → LLM 再强也会胡编。所以要**分层评测、分别优化**，不能只看最终答案。

---

## 2. 当前切分规则（本项目实现）

### 2.1 策略与代码位置

| 项 | 值 |
|----|-----|
| 切分器 | LangChain `RecursiveCharacterTextSplitter` |
| 实现文件 | `app/services/rag_engine.py` → `_refresh_splitter()` |
| 参数存储 | `data/rag_settings.json`（页面/API 可调） |
| 环境变量默认 | `RAG_CHUNK_SIZE=512`，`RAG_CHUNK_OVERLAP=64` |

```python
# app/services/rag_engine.py
RecursiveCharacterTextSplitter(
    chunk_size=settings.chunk_size,      # 默认 512 字符
    chunk_overlap=settings.chunk_overlap, # 默认 64 字符
)
```

### 2.2 分隔符优先级（LangChain 默认）

`RecursiveCharacterTextSplitter` 按以下顺序尝试切分，尽量保持语义单元完整：

```
\n\n  →  \n  →  。  →  ！  →  ？  →  ；  →  ，  →  空格  →  字符级硬切
```

**含义**：优先在段落、句子边界切，避免把一句话拦腰截断；实在不行才按字符硬切。

### 2.3 参数约束

| 参数 | 默认值 | 合法范围 | 何时生效 |
|------|--------|----------|----------|
| `chunk_size` | 512 | 128–4096 | **改后需重建索引** |
| `chunk_overlap` | 64 | 0–1024，且 `< chunk_size` | **改后需重建索引** |

判断逻辑：`rag_settings.needs_reindex == true` 时，页面会提示「重建索引」。

### 2.4 入库元数据

每个 chunk 携带：

| 字段 | 说明 |
|------|------|
| `doc_id` | 所属文档 UUID |
| `filename` | 原始文件名 |
| `chunk_id` | chunk UUID（向量库与 ES 关联键） |
| `source` | 文件路径 |

### 2.5 当前未实现的切分策略（规划中）

| 策略 | 适用场景 | 状态 |
|------|----------|------|
| 按标题/章节切分 | 制度手册、多级目录 | ❌ 未实现 |
| Parent-Child（小块检索、大块生成） | 需要完整上下文 | ❌ 未实现 |
| 按 Token 切分 | 多语言、对齐 LLM 窗口 | ❌ 未实现 |
| 表格/图片专用解析 | PDF 含复杂版式 | ❌ 未实现 |

---

## 3. 如何量化「切分效果好不好」

切分质量分两类：**内在指标**（不看检索，只看块本身）和**外在指标**（通过检索命中率反推）。

### 3.1 内在指标（Chunk 本身）

| 指标 | 计算方式 | 好的表现 | 差的信号 |
|------|----------|----------|----------|
| **平均块长** | `sum(len(chunk)) / chunk_count` | 接近 `chunk_size`（如 480–512） | 大量 <100 或 >chunk_size 的异常块 |
| **块长标准差** | 块长分布离散程度 | 较小（切分均匀） | 极大值与极小值悬殊 |
| **空块率** | `空块数 / 总块数` | 0% | >0%，说明解析或切分有 bug |
| **单文档块数** | `chunks_per_doc` | 与文档长度成正比 | 超长文档块数爆炸（chunk 太小）或只有 1 块（chunk 太大） |
| **边界质量** | 抽样检查首尾是否在句末 | 多数以 `。！？\n` 结尾 | 频繁半句话开头/结尾 |
| **重叠覆盖率** | `overlap / chunk_size` | 10%–20%（如 64/512≈12.5%） | 0%（上下文断裂）或 >30%（冗余、索引膨胀） |
| **入库耗时** | `ingest_seconds` | 可接受范围内 | 块数翻倍导致 embed 时间线性增长 |

**实操**：改 `chunk_size` 后对比 `total_chunks` 和 `ingest_seconds`（`make benchmark` 已输出）。

### 3.2 外在指标（通过检索反推切分质量）

**核心思路**：同一批问题、同一 embedding 模型，只变 `chunk_size` / `chunk_overlap`，看检索命中率变化。

| 指标 | 定义 | 本项目实现 |
|------|------|------------|
| **Hit@1** | Top-1 结果是否来自期望文档 | ✅ `scripts/benchmark_rag_params.py` |
| **Hit@K** | Top-K 内是否包含期望文档 | ✅ 同上 |
| **avg_top_score** | Top-1 向量距离（L2，越小越相似） | ✅ 同上 |
| **avg_context_chars** | Top-K 拼接后字符数 | ✅ 同上（与 `max_context_chars` 预算相关） |

**解读示例**（sample-docs **40 条**用例，含 `confusion` hard 子集）：

```
chunk=256  hit@1=60%  hit@k=80%  chunks=42   ← 块细，召回高但噪声多
chunk=512  hit@1=80%  hit@k=100% chunks=21   ← 平衡点（通常推荐起点）
chunk=768  hit@1=60%  hit@k=80%  chunks=14   ← 块粗，可能跨主题稀释语义
```

> 具体数值以你本地 `make benchmark` 结果为准；文档类型不同，最优 chunk 不同。

### 3.3 切分调参决策树

```
检索命中率低？
├── 换 chunk_size 后 hit@k 明显提升 → 切分是瓶颈，继续调 size/overlap
├── 换 chunk_size 几乎不变 → 瓶颈在 embedding / 检索模式 / 问题表述
│   ├── 专有名词、编号检不到 → 开 hybrid（ES BM25）
│   ├── Top-K 有对的但排序靠后 → 开 rerank
│   └── 语义相近文档互相干扰 → 调 score_threshold 或 MMR
└── 答案对了但引用片段断章取义 → 考虑 parent-child 或按标题切分（待实现）
```

### 3.4 快速跑切分对比

```bash
# 默认网格：chunk_size=256,512,768 × top_k=2,4,6，overlap=64
make benchmark

# 自定义
./scripts/benchmark.sh --chunk-sizes 400,512,600 --top-k 4,6 --verbose

# 结果
# → 终端表格
# → data/benchmark/benchmark_rag_params.csv
```

评测用例：`scripts/benchmark_cases.json`（**40 条**，含 `question` + `expected_filename` + `tags` + `difficulty`）。

---

## 4. 检索层指标（命中率相关）

### 4.1 指标定义

| 指标 | 公式 / 含义 | 需要标注 | 本项目 |
|------|-------------|----------|--------|
| **Hit@K** | 期望文档出现在 Top-K 的比例 | `expected_filename` 或 `expected_chunk_id` | ✅ |
| **MRR** | 第一个正确结果的排名倒数均值 `1/rank` | 同上 | ✅ benchmark + baseline |
| **Recall@K** | 应召回的 chunk 中，Top-K 覆盖比例 | `expected_chunk_ids[]` | ❌ 待加 |
| **Precision@K** | Top-K 中相关 chunk 占比 | 相关性标注 | ❌ 待加 |
| **NDCG@K** | 考虑排名位置的加权相关性 | 多级相关性标注 | ❌ 待加 |

**面试区分**：

- **Hit@K（文档级）**：只要 Top-K 里出现正确**文件**就算命中——本项目 benchmark 用这个，适合 FAQ/制度库。
- **Recall@K（片段级）**：需要 chunk 级标注——更精细，适合长文档多段相关。
- **MRR**：关心「第一个正确结果排第几」——适合只展示 1–2 条引用的产品。

### 4.2 检索模式对指标的影响

| 模式 | 擅长 | 建议观测 |
|------|------|----------|
| `vector` | 语义相似、口语化问法 | hit@k、avg_top_score |
| `hybrid`（向量 + ES BM25） | 专有名词、编号、条款号 | 对比 vector-only 的 hit@1 |
| `rerank` | 精排，提升 Top-1 | hit@1 提升，延迟增加 |
| `mmr` | 去重，多样性 | 上下文重复率下降 |

**互斥约束**（当前代码）：MMR 与 Rerank 不能同开；Hybrid 与 MMR 不能同开。

### 4.3 在线预览（不调 LLM）

```bash
# 查看某问题的检索结果与分数
curl "http://127.0.0.1:8081/api/chat/sources?q=退款多久到账"
```

用于人工 spot-check，不计入自动化指标。

---

## 5. 生成层与端到端指标（RAGAS）

检索命中 ≠ 回答正确。需要 LLM 参与评测。

### 5.1 RAGAS 四维指标

| 指标 | 衡量什么 | 低分说明 | 优化方向 |
|------|----------|----------|----------|
| **Context Precision** | 检索片段是否都相关 | 噪声多 | 降 top_k、开 rerank、调 threshold |
| **Context Recall** | 是否检全回答问题所需信息 | 漏检 | 增大 fetch_k、multi-query、hybrid |
| **Faithfulness** | 答案是否忠于检索内容 | 幻觉 | 降 temperature、加强 system prompt |
| **Answer Relevancy** | 答案是否切题 | 答非所问 | query 改写、多轮历史 |

**目标参考**（企业制度/FAQ 场景，来自 `ENTERPRISE_PLAN.md`）：

- 语义问答：`faithfulness > 0.8`
- 精确关键词（工单号、条款号）：混合检索 `hit@1` 优于纯向量

### 5.2 评测用例扩展格式（规划）

当前 `benchmark_cases.json` 只有检索字段，RAGAS 需扩展：

```json
{
  "question": "退款多久到账？",
  "expected_filename": "refund-policy.md",
  "expected_answer": "购买后 7 日内可申请全额退款，审核通过后 3-5 个工作日原路退回。",
  "tags": ["faq", "refund"],
  "difficulty": "easy"
}
```

| 字段 | 用途 |
|------|------|
| `expected_filename` | 检索 Hit@K |
| `expected_answer` | RAGAS context_recall、answer 对比 |
| `tags` | 分场景统计（FAQ / 制度 / IT） |

---

## 6. 系统与运维指标

| 类别 | 指标 | 说明 | 状态 |
|------|------|------|------|
| **延迟** | `retrieval_ms` | 检索耗时 | ✅ benchmark + `/metrics` |
| | `llm_ms` / `generation_ms` | 生成耗时 | ✅ `/metrics` |
| | `ingest_seconds` | 单文档入库 | ✅ benchmark 有 |
| **成本** | Token 用量（估算） | `rag_tokens_estimated` | ✅ `/metrics` |
| **可用性** | `pg_status` / `redis_status` / `es_status` / `s3_status` | 中间件连通 | ✅ `/api/health` |
| **缓存** | 语义缓存命中率 | Redis | ❌ |

---

## 7. 现有工具链一览

| 工具 | 命令 | 测什么 | 不测什么 |
|------|------|--------|----------|
| `benchmark_rag_params.py` | `make benchmark` | chunk/top_k 网格、hit@1、hit@k、mrr、多检索模式 | LLM |
| `check_eval_baseline.py` | `make eval-check` | 对比 baseline.json 门禁 | — |
| `eval_smoke.sh` | `make eval-smoke` | L1+L2+基线（CI 同款） | LLM |
| `eval_ragas.py` | `make eval-ragas` / `--run --ragas` | faithfulness、answer_relevancy | 需 API Key + ragas |
| `export_bad_cases.py` | `make export-bad-cases` | 差评回流候选用例 | — |
| `benchmark_cases.json` | 编辑用例 | ≥20 条检索期望（含 tags） | — |
| `/metrics` | curl | Prometheus 延迟/Token/反馈计数 | 无质量分 |
| `/api/chat/sources` | curl / 页面 | 单次检索预览 | 无批量统计 |
| `/api/health` | curl | 基础设施状态 | 无质量分数 |

---

## 8. 落地规划（Phase 6 评测闭环）

### 8.1 里程碑

| 阶段 | 周期 | 交付物 | 验收标准 |
|------|------|--------|----------|
| **P0 检索基准** | 已完成 | `benchmark_rag_params.py` + 5 用例 | 能对比 chunk/top_k |
| **P1 用例扩充** | 3 天 | 20–50 条真实问答 + `tags` | 覆盖 FAQ/制度/IT 三类 |
| **P2 检索增强评测** | 1 周 | benchmark 支持 hybrid/rerank 模式 | 能证明 hybrid 对编号类 hit@1 提升 |
| **P3 切分分析脚本** | 3 天 | `scripts/analyze_chunks.py` | 输出块长分布、边界质量报告 |
| **P4 RAGAS 集成** | 1 周 | `scripts/eval_ragas.py` → `eval_report.json` | faithfulness / answer_relevancy 可回归 |
| **P5 埋点与看板** | 1 周 | structlog + `/metrics` + Grafana | P99 延迟、每日命中率趋势 |
| **P6 CI 门禁** | 2 天 | PR 触发 `make eval-smoke`，低于基线告警 | ✅ `.github/workflows/eval.yml` |

### 8.2 目录规划（待新增）

```
scripts/
├── benchmark_rag_params.py   # ✅ 已有
├── benchmark_cases.json      # ✅ 已有，待扩展 expected_answer
├── analyze_chunks.py         # ✅ 切分内在指标
├── eval_ragas.py             # ✅ L3 脚手架（可选 RAGAS）
├── check_eval_baseline.py    # ✅ 基线对比
└── eval_report.schema.json   # 报告格式（待加）

data/
├── benchmark/
│   └── benchmark_rag_params.csv
└── eval/
    ├── eval_report.json
    └── baseline.json         # ✅ CI 对比基线
```

### 8.3 推荐工作流

```
1. 新文档入库前 → analyze_chunks.py 看块分布
2. 调 chunk_size → make benchmark 看 hit@k
3. 调检索参数   → benchmark --mode hybrid 对比
4. 调 Prompt/LLM → eval_ragas.py 看 faithfulness
5. 上线前       → 全量回归，对比 baseline.json
```

---

## 9. 面试高频问答（可直接背）

### Q1：你们怎么判断 chunk_size 设多少合适？

> 我们不拍脑袋定 512，而是用 **外在指标 Hit@K** 做网格搜索：固定 embedding 和文档集，对比 256/512/768 的 hit@1、hit@k 和入库块数。512 在 sample-docs 上 hit@k 最高；生产环境会用 20–50 条真实业务问答做回归。同时也会看 **内在指标**：块长分布是否均匀、有没有半句话切分。

### Q2：Hit@K 和 Recall@K 有什么区别？

> **Hit@K** 是文档级：Top-K 里有没有出现期望的**文件**。**Recall@K** 是片段级：所有应相关的 chunk 里，有多少被 Top-K 覆盖。FAQ 场景用 Hit@K 够用；长制度文档需要 chunk 级标注才能算 Recall@K。

### Q3：切分效果好但回答还是胡编，怎么排查？

> 分层排查：先用 `/api/chat/sources` 看检索片段是否相关（Context Precision）；相关但答错 → Faithfulness 问题，调 prompt/temperature；检索片段就不相关 → 检索问题，不是切分问题。

### Q4：RAG 效果怎么量化，不能只看主观感觉？

> 三层：**检索层** Hit@K/MRR（不花钱、可 CI）；**生成层** RAGAS faithfulness + answer relevancy（调 LLM 后回归）；**业务层** 用户采纳率、工单解决率。我们项目已落地检索 benchmark，RAGAS 在 Phase 6 规划里。

### Q5：混合检索为什么能提升命中率？

> 向量检索擅长语义，BM25 擅长精确词匹配（产品名、条款号、错误码）。我们用 **加权 RRF** 融合两路结果，避免单路短板。评测上对「编号类」问题单独统计 hit@1，通常 hybrid 优于纯 vector。

### Q6：改动哪些参数需要重建索引？

> **chunk_size、chunk_overlap、embedding 模型** 必须重建——因为向量是按 chunk 算的。top_k、rerank、hybrid 等检索参数 **立即生效**，不需要重建。

---

## 10. 相关文档

| 文档 | 内容 |
|------|------|
| [ENTERPRISE_PLAN.md](./ENTERPRISE_PLAN.md) | 企业演进总方案、Phase 6 RAGAS 规划 |
| [LEARNING.md](../guides/LEARNING.md) | RAG 学习路径与代码导读 |
| [README.md](../../README.md) | 快速开始、`make benchmark` |

---

## 附录：参数速查

| 环境变量 | 默认 | 层级 |
|----------|------|------|
| `RAG_CHUNK_SIZE` | 512 | L1 切分 |
| `RAG_CHUNK_OVERLAP` | 64 | L1 切分 |
| `RAG_TOP_K` | 4 | L2 检索 |
| `RAG_FETCH_K` | 20 | L2 检索 |
| `RAG_RETRIEVAL_MODE` | vector | L2 检索 |
| `RAG_USE_RERANK` | false | L2 检索 |
| `RAG_USE_MMR` | false | L2 检索 |
| `RAG_MAX_CONTEXT_CHARS` | 4000 | L2→L3 上下文 |
| `RAG_TEMPERATURE` | 0.2 | L3 生成 |

改切分参数后执行 **重建索引**（页面按钮或 `POST /api/documents/reindex`）。
