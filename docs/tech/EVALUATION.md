# 评测技术设计（EVALUATION）

> **专题**：衡量系统好坏的技术实现。指标定义与面试话术见 [`../enterprise/RAG_EVALUATION.md`](../enterprise/RAG_EVALUATION.md)；产品需求见 [`../prd/03-features/F12-evaluation.md`](../prd/03-features/F12-evaluation.md)。

---

## 1. 评测金字塔与工具映射

```
L1 切分质量  →  scripts/analyze_chunks.py
L2 检索质量  →  scripts/benchmark_rag_params.py  （vector / hybrid / mmr / rerank / hybrid_rerank）
L3 生成质量  →  scripts/eval_ragas.py
L4 业务指标  →  POST /api/feedback  +  scripts/export_bad_cases.py
运维可观测    →  GET /metrics  （Prometheus 文本）
评测看板      →  GET /eval-dashboard.html  +  GET /api/eval/dashboard
门禁          →  scripts/check_eval_baseline.py  +  make eval-smoke  +  CI
```

### 1.1 面试级 vs 生产级

| 能力 | 面试级 | 生产级 | 状态 |
|------|--------|--------|------|
| L1 空块率/边界 | `make analyze-chunks` | CI 门禁 | ✅ |
| L2 Hit@K + MRR | `make benchmark` | baseline.json | ✅ |
| L2 全路径检索 | `--modes vector,hybrid,rerank,...` | 对齐 `retrieve_sources()` | ✅ |
| 20+ 用例 + tags | `benchmark_cases.json`（**40 条** / 6 篇文档） | PR 回归 | ✅ |
| L3 RAGAS | `eval_ragas.py --run --ragas` | 可选 L3 基线 | 脚手架 |
| 延迟埋点 | benchmark `retrieval_ms` | `/metrics` P50/P95 | ✅ |
| 成本埋点 | — | `rag_tokens_estimated` | ✅ 估算 |
| 反馈回流 | — | `/api/feedback` → export | ✅ |

---

## 2. 目录与产物

```
scripts/
├── analyze_chunks.py           # L1
├── benchmark_rag_params.py     # L2（多检索模式）
├── benchmark_cases.json        # ≥20 条用例
├── eval_ragas.py               # L3
├── check_eval_baseline.py      # 基线门禁
├── eval_smoke.sh               # CI 冒烟
└── export_bad_cases.py         # L4 差评回流

app/observability/
└── metrics.py                  # Prometheus 埋点

data/
├── benchmark/
│   ├── benchmark_rag_params.csv
│   └── benchmark_rag_params.json
└── eval/
    ├── chunk_analysis.json     # L1 报告
    ├── baseline.json           # 门禁阈值
    ├── eval_report.json        # L3 报告
    └── feedback.jsonl          # L4 用户反馈
```

---

## 3. L1：切分分析

与前一版一致，见 `analyze_chunks.py`。

```bash
make analyze-chunks
./.venv/bin/python scripts/analyze_chunks.py --chunk-size 1472 --chunk-overlap 256 --verbose
```

门禁字段：`summary.empty_chunk_rate`、`summary.boundary_good_rate`。

---

## 4. L2：检索 benchmark（全路径）

### 4.1 检索模式与生产对齐

| benchmark mode | 实现 | 生产设置 |
|----------------|------|----------|
| `vector` | `similarity_search_with_score(k=fetch_k)[:top_k]` | 默认 |
| `hybrid` | vector + BM25 → RRF → top_k | `retrievalMode=hybrid` |
| `mmr` | `max_marginal_relevance_search` | `useMmr=true` |
| `rerank` | vector fetch_k → CrossEncoder → top_k | `useRerank=true` |
| `hybrid_rerank` | hybrid fuse → rerank → top_k | hybrid + rerank |

**互斥**（单次检索配置）：`mmr` 与 `hybrid`/`hybrid_rerank` 不能同时用于同一次 `retrieve_sources()`；benchmark 的 `--modes` 可列出全部模式，各自独立评测。

### 4.2 指标

| 指标 | 公式 |
|------|------|
| Hit@1 | Top-1 `metadata.filename` == `expected_filename` |
| Hit@K | Top-K 内任一 filename 匹配 |
| MRR | `mean(1/first_hit_rank)`，未命中为 0 |
| retrieval_ms | 单题检索耗时 |
| by_tag | 按 case `tags` 分组 hit@1 / hit@k / mrr |

### 4.3 隔离策略

| 组件 | 隔离 |
|------|------|
| Chroma | `data/benchmark/c{size}_o{overlap}_k{topk}_{mode}/` |
| ES | 索引 `benchmark_rag_chunks`（`ES_INDEX_PREFIX=benchmark_rag`） |

### 4.4 命令

```bash
# 默认 vector
make benchmark

# 全路径对比（rerank 需下载 Cross-Encoder，CI smoke 不跑）
make benchmark -- --modes vector,hybrid,rerank,mmr,hybrid_rerank --chunk-sizes 512 --top-k-values 4

# smoke 网格（CI 同款）
./scripts/eval_smoke.sh
```

### 4.5 Hard 混淆集（40 题 / 6 篇文档）

`sample-docs/` 除 3 篇基础政策外，新增 3 篇 **故意混淆** 文档：

| 文档 | 与谁混淆 | 典型考点 |
|------|----------|----------|
| `benefits-policy.md` | `refund-policy.md` | 「到账工作日」：产品 5~10 vs 差旅 7~15 |
| `security-policy.md` | `it-faq.md` | P0 响应 30min vs 15min；OpenVPN vs AnyConnect |
| `procurement-policy.md` | `it-faq.md` | ECS 采购通道 vs IT 自助申请 |

用例标签 `confusion`（≥10 条）专用于对比 vector / hybrid / rerank。推荐命令：

```bash
./.venv/bin/python scripts/benchmark_rag_params.py \
  --modes vector,hybrid,rerank \
  --chunk-sizes 512 \
  --top-k-values 4 \
  --verbose
```

查看 `by_tag.confusion` 与全量 `mrr`；hard 子集上 hybrid/rerank 应不低于 vector。

**实测（2026-09）**：vector hit@1=88% → hybrid/rerank hit@1=92%；MRR 0.92 → 0.96。

---

## 5. 基线门禁

### 5.1 baseline.json 结构

```json
{
  "updated_at": "2026-09-03",
  "l1_chunk": {
    "chunk_size": 512,
    "chunk_overlap": 64,
    "max_empty_chunk_rate": 0.0,
    "min_boundary_good_rate": 0.1
  },
  "l2_retrieval": {
    "config": {
      "retrieval_mode": "vector",
      "chunk_size": 512,
      "chunk_overlap": 64,
      "top_k": 4
    },
    "min_hit_at_1_rate": 0.8,
    "min_hit_at_k_rate": 1.0,
    "min_mrr": 0.8,
    "max_avg_retrieval_ms": 10000,
    "max_p95_retrieval_ms": 20000
  },
  "l3_generation": {
    "enabled": false,
    "min_faithfulness": 0.8,
    "min_answer_relevancy": 0.7
  }
}
```

### 5.2 流程

```bash
make eval-smoke          # L1 → L2 smoke → check
make eval-check          # 仅对比
./.venv/bin/python scripts/check_eval_baseline.py --update-baseline
```

L3 检查：`--l3-report data/eval/eval_report.json`（可选，默认 `l3_generation.enabled=false`）。

---

## 6. L3：RAGAS

```bash
make eval-ragas                                    # dry-run
pip install -r requirements-eval.txt
./.venv/bin/python scripts/eval_ragas.py --run --ragas  # 需 OPENAI_API_KEY
```

用例需 `expected_answer`；当前 **40 条**用例中约 **70%** 已标注（含 hard 混淆集）。

---

## 7. L4：反馈与回流

### 7.1 反馈 API

```http
POST /api/feedback
Content-Type: application/json

{
  "rating": "down",
  "question": "退款多久到账？",
  "answer": "...",
  "conversationId": "optional-uuid",
  "comment": "引用片段不对"
}
```

写入 `data/eval/feedback.jsonl`（追加，一行一条 JSON）。

### 7.2 差评回流

```bash
make export-bad-cases
# → data/eval/bad_cases_candidates.json
```

人工审核后合并到 `scripts/benchmark_cases.json`，再跑 `make eval-smoke` 回归。

---

## 8. 评测看板（HTML）

### 8.1 入口

| 地址 | 说明 |
|------|------|
| `http://127.0.0.1:8081/eval-dashboard.html` | 可视化看板（浏览器） |
| `GET /api/eval/dashboard` | JSON API（供看板或外部集成） |

主问答页 header 有「评测看板」链接。

### 8.2 看板内容

1. **基线门禁横幅**：对比 `baseline.json`，显示 PASS/FAIL
2. **闭环工作流**：调参 → L1 → L2 → L3 → 门禁 → 上线 → 反馈 → 回流
3. **L1–L4 指标卡片**：当前值 + 达标状态（绿/红）
4. **指标影响思维导图**：调参旋钮 → 分层指标 → 系统质量 / 基线门禁（可点击节点查看影响链）
5. **L2 模式对比表**：vector / hybrid / rerank 等全量 benchmark 结果
6. **运行时观测**：`/metrics` 累计值（问答数、延迟、Token、好评/差评）

### 8.3 数据源

| 数据 | 文件 / 端点 |
|------|-------------|
| L1 | `data/eval/chunk_analysis.json` |
| L2 | `data/benchmark/benchmark_rag_params.json` |
| L3 | `data/eval/eval_report.json` |
| 基线 | `data/eval/baseline.json` |
| L4 | `data/eval/feedback.jsonl` |
| 运行时 | 进程内 `METRICS`（同 `/metrics`） |

刷新看板前需先跑离线评测脚本；点击看板「刷新」或重新打开页面即可拉取最新 JSON。

### 8.4 实现

- 聚合逻辑：`app/services/eval_dashboard.py`
- 前端：`static/eval-dashboard.html`（纯 HTML/CSS/JS + SVG 思维导图，无外部依赖）

---

## 9. 可观测（/metrics）

### 9.1 暴露指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `rag_chat_total` | counter | 问答请求总数（label: stream=false/true） |
| `rag_feedback_total` | counter | 反馈数（label: rating=up/down） |
| `rag_retrieval_seconds` | histogram | 检索耗时 |
| `rag_generation_seconds` | histogram | 生成耗时 |
| `rag_tokens_estimated` | counter | 估算 Token（question+context+answer 字符/4） |

### 9.2 使用

```bash
curl -s http://127.0.0.1:8081/metrics
```

生产侧可接 Prometheus scrape + Grafana；本项目仅暴露文本端点。

### 9.3 埋点位置

- `app/services/rag_engine.py`：`chat()` / `stream_chat()` 记录 retrieval/generation 耗时
- `app/main.py`：`POST /api/feedback` 递增 `rag_feedback_total`

---

## 10. CI

`.github/workflows/eval.yml`：

1. `pip install -r requirements.txt`
2. `make eval-smoke`（L1 + L2 vector smoke + baseline）
3. 上传 `data/eval/`、`data/benchmark/` 产物

**不进 CI**：rerank（模型下载）、L3 RAGAS（API Key）。

---

## 11. 推荐闭环工作流

```
1. make analyze-chunks
2. make benchmark -- --modes vector,hybrid --chunk-sizes 512 --top-k-values 4
3. （可选）benchmark --modes rerank,hybrid_rerank
4. make eval-smoke
5. eval_ragas.py --run --ragas
6. 上线后 curl /metrics + 收集 feedback
7. make export-bad-cases → 扩充用例 → 回到 1
```

---

## 12. 依赖与环境

| 依赖 | L1 | L2 vector | L2 hybrid | L2 rerank | L3 | /metrics |
|------|----|-----------|-----------|-----------|----|----------|
| Embedding | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |
| LLM Key | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| ES | ❌ | ❌ | ✅ | ❌* | ❌ | ❌ |
| sentence-transformers (rerank) | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| ragas | ❌ | ❌ | ❌ | ❌ | 可选 | ❌ |

\* `hybrid_rerank` 需 ES。

---

## 13. 相关文档

| 文档 | 内容 |
|------|------|
| [`../enterprise/RAG_EVALUATION.md`](../enterprise/RAG_EVALUATION.md) | 指标定义、面试 Q&A |
| [`../prd/03-features/F12-evaluation.md`](../prd/03-features/F12-evaluation.md) | PRD 与验收 |
| [`../prd/03-features/F13-health-status.md`](../prd/03-features/F13-health-status.md) | `/api/health`（连通性） |
