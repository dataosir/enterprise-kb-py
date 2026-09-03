# F12 · RAG 评测体系（分层指标 + 闭环）

> **专题定位**：衡量系统好坏的统一契约——覆盖面试陈述（分层指标 + 调参闭环）与生产搭架子（基线门禁 + 可观测 + 反馈回流）。  
> 指标定义与话术：[`../../enterprise/RAG_EVALUATION.md`](../../enterprise/RAG_EVALUATION.md)  
> 技术实现：[`../../tech/EVALUATION.md`](../../tech/EVALUATION.md)

## 1. 背景与目标

RAG 质量不能只看最终答案。需要 **L1→L4 分层评测**，每层有量化指标、离线脚本与（生产侧）埋点，形成可回归、可门禁、可回流的闭环。

**面试级目标**：能系统讲清「切分 → 检索 → 生成 → 业务」各层量什么、怎么调、怎么证明没退化。  
**生产级目标**：PR 触发 CI 门禁；线上有延迟/成本埋点；用户差评可回流到 benchmark 用例集。

## 2. 用户故事 / 场景

- 作为调参者，我跑 `make analyze-chunks` 看空块率与边界质量，再跑 `make benchmark` 对比 chunk/top_k/检索模式。
- 作为检索优化者，我用 `--modes vector,hybrid,rerank,hybrid_rerank,mmr` 证明 hybrid/rerank 对 keyword 类问题的收益。
- 作为面试准备者，我结合四层金字塔与 `benchmark_cases.json`（≥20 条）说明分层评测与 MRR 含义。
- 作为 CI 维护者，我跑 `make eval-smoke`，低于 `baseline.json` 则 PR 失败。
- 作为线上运维，我通过 `/metrics` 看检索/生成延迟分位数与 Token 估算。
- 作为产品迭代者，用户点踩后，我执行 `make export-bad-cases` 将差评回流为 benchmark 用例。

## 3. 功能范围

### 3.1 In — 四层指标

| 层级 | 指标 | 工具 / 端点 | 是否需 LLM |
|------|------|-------------|------------|
| **L1 切分** | 空块率、块长分布、边界质量、chunks_per_doc | `analyze_chunks.py` | ❌ |
| **L2 检索** | Hit@1、Hit@K、MRR、retrieval_ms、by_tag | `benchmark_rag_params.py` | ❌ |
| **L3 生成** | faithfulness、answer_relevancy、generation_ms | `eval_ragas.py` | ✅ |
| **L4 业务** | 反馈率、采纳率（引用点击）、差评回流 | `/api/feedback` + `export_bad_cases.py` | ❌ |

### 3.2 In — L2 检索模式（全路径 benchmark）

| 模式 | 说明 | 与生产对齐 |
|------|------|------------|
| `vector` | 纯向量 Top-K | `retrieve_sources()` 默认路径 |
| `hybrid` | 向量 + BM25 RRF 融合 | `retrievalMode=hybrid` |
| `mmr` | 最大边际相关性去重 | `useMmr=true`（与 hybrid 互斥） |
| `rerank` | 向量召回 + Cross-Encoder 精排 | `useRerank=true` |
| `hybrid_rerank` | hybrid 融合后再 rerank | hybrid + rerank |

**互斥**（单次运行配置，与 F04/F05 一致）：`mmr` 模式不与 `hybrid`/`hybrid_rerank` 同时启用；benchmark 可对各模式**分别**跑一轮对比。

### 3.3 In — 基线门禁与 CI

- `data/eval/baseline.json`：L1/L2（可选 L3）阈值
- `scripts/check_eval_baseline.py`：对比报告，不达标 exit 1
- `scripts/eval_smoke.sh` / `make eval-smoke`：L1 → L2 → 基线
- `.github/workflows/eval.yml`：PR / main 自动冒烟

### 3.4 In — 可观测（生产搭架子）

- `GET /metrics`：Prometheus 文本格式
- **`GET /eval-dashboard.html`**：评测看板（L1–L4 指标卡片 + 指标影响思维导图 + 基线门禁状态）
- **`GET /api/eval/dashboard`**：看板 JSON 数据源（聚合离线报告 + 运行时 metrics）
- 埋点：`rag_retrieval_seconds`、`rag_generation_seconds`、`rag_chat_total`、`rag_tokens_estimated`
- `POST /api/feedback`：thumbs up/down + 可选 question/answer
- `scripts/export_bad_cases.py`：差评 → `data/eval/bad_cases_candidates.json`

### 3.5 Out

- 自动写回推荐参数到 `rag_settings`
- Recall@K / NDCG（需 chunk 级标注，后续迭代）
- 外置 Grafana 配置（本项目提供内置 HTML 看板 + `/metrics` 端点）
- 完整 RAGAS CI（L3 默认不进 smoke，避免 API Key 依赖）

## 4. 用例规范（benchmark_cases.json）

### 4.1 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `question` | ✅ | 用户问题 |
| `expected_filename` | ✅ | 期望命中的文档文件名 |
| `tags` | 推荐 | 场景标签，用于 `by_tag` 分场景统计 |
| `difficulty` | 可选 | `easy` / `medium` / `hard` |
| `expected_answer` | L3 推荐 | RAGAS ground truth |

### 4.2 规模要求

- **面试级**：≥ **20 条**用例，覆盖 sample-docs 全部 3 篇文档
- 每条含 `tags`；≥ 30% 含 `expected_answer`（供 L3）
- `keyword` 类 ≥ 3 条（验证 hybrid 收益）

### 4.3 推荐 tags

| tag | 含义 | 观测重点 |
|-----|------|----------|
| `semantic` | 口语化语义问法 | vector 基线 |
| `keyword` | 专有名词、编号、版本号 | hybrid / rerank 收益 |
| `faq` | 短问答 | hit@1 敏感 |
| `policy` | 制度/流程 | 较长上下文 |
| `it` | IT 服务台 | it-faq.md |
| `refund` | 退款政策 | refund-policy.md |
| `remote` | 远程办公 | remote-work-policy.md |

### 4.4 示例

```json
{
  "question": "Cisco AnyConnect 版本要求是多少？",
  "expected_filename": "it-faq.md",
  "expected_answer": "Cisco AnyConnect 4.10 及以上版本。",
  "tags": ["keyword", "it"],
  "difficulty": "medium"
}
```

## 5. 主流程与边界

### 5.1 评测闭环（推荐工作流）

```
调参 → L1 analyze_chunks → L2 benchmark（多模式）→ L3 eval_ragas（可选）
     → eval-smoke 对比 baseline → CI 门禁 → 上线
     → /metrics 观测 → 用户反馈 → export_bad_cases → 扩充用例集
```

### 5.2 L1 切分分析

1. 加载 `sample-docs`（或 `--docs-dir`），按与生产相同的 `RecursiveCharacterTextSplitter` 切分。
2. 输出 `data/eval/chunk_analysis.json`。
3. 门禁：`empty_chunk_rate == 0`。

### 5.3 L2 检索 benchmark

1. 隔离目录 `data/benchmark/`（Chroma + ES 索引前缀 `benchmark_rag`）。
2. 对 `(chunk_size, top_k, mode)` 网格建库并评测。
3. 输出 CSV/JSON，含 `mrr`、`retrieval_ms`、`by_tag`。
4. `hybrid*` 模式 ES 不可用时回退 vector 并标记 `hybrid_fallback`。

### 5.4 L3 RAGAS（可选）

1. `--dry-run` 校验用例（无 API Key）。
2. `--run --ragas` 输出 `data/eval/eval_report.json`。
3. 目标参考：faithfulness ≥ 0.8（企业 FAQ 场景）。

### 5.5 L4 反馈回流

1. 前端/客户端 `POST /api/feedback` 记录评价。
2. 定期 `make export-bad-cases` 导出候选用例。
3. 人工审核后合并进 `benchmark_cases.json`。

**边界**

- benchmark 不写生产 `data/chroma` / `enterprise_kb_chunks`。
- rerank 模式首次运行会下载 Cross-Encoder 模型（~400MB），CI smoke 默认不跑 rerank。
- L3 不进 CI smoke（避免 OpenAI Key 与 ragas 依赖）。

## 6. 关键配置键

### 6.1 benchmark 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--chunk-sizes` | `256,512,768` | 切分网格 |
| `--top-k-values` | `2,4,6` | Top-K 网格 |
| `--modes` | `vector` | 见 §3.2 模式列表 |
| `--fetch-k` | `20` | 召回条数（hybrid/rerank/mmr） |
| `--mmr-lambda` | `0.5` | MMR 多样性权重 |
| `--cases-file` | `benchmark_cases.json` | 用例文件 |

### 6.2 基线阈值（baseline.json）

| 段 | 字段 | 含义 |
|----|------|------|
| `l1_chunk` | `max_empty_chunk_rate` | 空块率上限（0） |
| `l1_chunk` | `min_boundary_good_rate` | 边界良好率下限 |
| `l2_retrieval` | `min_hit_at_1_rate` / `min_hit_at_k_rate` / `min_mrr` | 检索下限 |
| `l2_retrieval` | `max_avg_retrieval_ms` / `max_p95_retrieval_ms` | 延迟上限 |
| `l3_generation` | `min_faithfulness`（可选） | L3 门禁，默认不进 smoke |

### 6.3 Makefile 入口

| 命令 | 作用 |
|------|------|
| `make analyze-chunks` | L1 |
| `make benchmark` | L2 全量/自定义 |
| `make eval-smoke` | L1+L2+基线（CI 同款） |
| `make eval-check` | 仅对比基线 |
| `make eval-ragas` | L3 dry-run |
| `make export-bad-cases` | L4 差评回流 |

## 7. 代码锚点

| 组件 | 路径 |
|------|------|
| L1 切分分析 | `scripts/analyze_chunks.py` |
| L2 检索 benchmark | `scripts/benchmark_rag_params.py` |
| L3 RAGAS | `scripts/eval_ragas.py` |
| 基线门禁 | `scripts/check_eval_baseline.py` |
| 冒烟脚本 | `scripts/eval_smoke.sh` |
| 用例集 | `scripts/benchmark_cases.json` |
| 基线文件 | `data/eval/baseline.json` |
| 可观测 | `app/observability/metrics.py` |
| 反馈 API | `app/main.py` → `POST /api/feedback` |
| 差评导出 | `scripts/export_bad_cases.py` |
| CI | `.github/workflows/eval.yml` |

## 8. 分场景验收标准

### 8.1 L1 切分（analyze_chunks）

- [ ] `make analyze-chunks` 无 API Key 可完成
- [ ] 输出 `data/eval/chunk_analysis.json`
- [ ] `empty_chunk_rate == 0`
- [ ] `--chunk-size 1472 --chunk-overlap 256` 可指定并与线上一致

### 8.2 L2 检索（benchmark）

- [ ] `make benchmark` 无 LLM API Key 可完成
- [ ] 输出含 `mrr`、`avg_retrieval_ms`、`by_tag`
- [ ] `--modes vector,hybrid,rerank,mmr,hybrid_rerank` 均可运行（rerank 本地可下载模型）
- [ ] `keyword` 标签：hybrid hit@1 ≥ vector hit@1（或相等）
- [ ] 用例 ≥ 20 条，覆盖 3 篇 sample-docs

### 8.3 基线门禁（CI）

- [ ] `make eval-smoke` 通过
- [ ] 人为降低 hit@k 后 `make eval-check` exit 1
- [ ] PR 触发 `eval.yml`

### 8.4 L3 RAGAS（脚手架）

- [ ] `make eval-ragas` dry-run 输出用例统计
- [ ] `eval_ragas.py --run` 在无 Key 时明确报错
- [ ] ≥ 30% 用例含 `expected_answer`

### 8.5 L4 可观测与反馈

- [ ] `GET /metrics` 返回 Prometheus 文本，含 `rag_chat_total`
- [ ] `POST /api/feedback` 写入 `data/eval/feedback.jsonl`
- [ ] `make export-bad-cases` 输出候选 JSON

### 8.6 面试陈述清单

- [ ] 能画出 L1→L4 金字塔与闭环流程图
- [ ] 能解释 Hit@K vs MRR vs faithfulness 各自优化什么
- [ ] 能说明哪些参数改后需重建索引（chunk/embedding）vs 立即生效（top_k/rerank/hybrid）

## 9. 已知缺口 / 待迭代

- Recall@K / NDCG（chunk 级标注）
- score_threshold 路径 benchmark
- L3 纳入 CI（需 mock LLM 或专用评测环境）
- Grafana Dashboard 模板
- 引用点击采纳率（需前端埋点）
