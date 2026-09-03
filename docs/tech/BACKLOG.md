# 待办与缺口专题（Backlog）

> 与代码严格对齐的缺口清单。状态随实现更新；完成项在 PR 中同步改本文件与 `docs/prd/05-roadmap-backlog.md`。

**图例**：✅ 已落地 · 🟡 部分 · ❌ 未开始

---

## 1. 总览矩阵

| 领域 | 面试价值 | 生产价值 | 状态 | 入口 |
|------|----------|----------|------|------|
| L1–L4 分层评测 | ⭐⭐⭐ | ⭐⭐⭐ | ✅ | `make eval-smoke` |
| Hard benchmark 40 题 | ⭐⭐⭐ | ⭐⭐ | ✅ | `scripts/benchmark_cases.json` |
| 基线 CI 门禁 | ⭐⭐ | ⭐⭐⭐ | ✅ | `.github/workflows/eval.yml` |
| 评测 / 中间件 HTML 看板 | ⭐⭐⭐ | ⭐⭐ | ✅ | `eval-dashboard.html` |
| **pytest API 冒烟** | ⭐⭐ | ⭐⭐⭐ | 🟡 | `tests/` |
| **SSE + Markdown 前端** | ⭐⭐ | ⭐⭐⭐ | 🟡 | `static/index.html` |
| **F14 认证 + 审计** | ⭐⭐⭐ | ⭐⭐⭐ | 🟡 | `app/middleware/auth.py` |
| **Chunk Recall@K** | ⭐⭐⭐ | ⭐⭐ | 🟡 | `benchmark_rag_params.py` |
| **by_tag / 历史趋势看板** | ⭐⭐ | ⭐⭐ | 🟡 | `eval-dashboard.html` |
| **引用采纳率埋点** | ⭐ | ⭐⭐⭐ | 🟡 | `POST /api/metrics/citation` |
| **Grafana 外置大盘** | ⭐ | ⭐⭐⭐ | 🟡 | `grafana/dashboard.json` |
| RAGAS 进 CI | ⭐⭐ | ⭐⭐ | 🟡 | `.github/workflows/eval-ragas.yml` |
| Query 改写 / HyDE | ⭐⭐⭐ | ⭐⭐ | ❌ | — |
| 智能切分 / Parent-Child | ⭐⭐ | ⭐⭐ | ❌ | F01 |
| 增量入库（同 doc 覆盖） | ⭐ | ⭐⭐⭐ | ❌ | F01 |
| 语义缓存（Redis） | ⭐ | ⭐⭐ | ❌ | — |
| structlog / OpenTelemetry | ⭐ | ⭐⭐⭐ | ❌ | — |
| `POST /api/eval/run` | ⭐ | ⭐⭐ | ❌ | — |
| score_threshold benchmark 路径 | ⭐⭐ | ⭐⭐ | ❌ | F12 |
| Embedding UI 切换 | ⭐ | ⭐ | ❌ | F04 |
| Windows `package.bat` | ⭐ | ⭐ | ❌ | F11 |

---

## 2. 按 Phase 分解

### Phase 5 — 安全（F14）

| 项 | 状态 | 说明 |
|----|------|------|
| `AUTH_ENABLED` 开关 | 🟡 | 默认 `false`，与 Demo 行为一致 |
| Bearer Token 校验 | 🟡 | HMAC 简易 JWT，生产可换 OIDC |
| `tenant_id` 注入 request.state | 🟡 | 为后续数据隔离预留 |
| 租户数据隔离（向量/文档/ES） | ❌ | 需改 store 层 filter |
| RBAC admin/editor/viewer | ❌ | 仅角色字段，未强制 |
| 审计日志 append-only | 🟡 | `data/audit/audit.jsonl` |

### Phase 6 — 可观测与评测深化

| 项 | 状态 | 说明 |
|----|------|------|
| `/metrics` Prometheus | ✅ | `app/observability/metrics.py` |
| 内置评测看板 | ✅ | `GET /api/eval/dashboard` |
| L3 RAGAS 脚手架 | ✅ | `scripts/eval_ragas.py` |
| L3 RAGAS CI（需 Secret） | 🟡 | 独立 workflow，`workflow_dispatch` |
| Grafana dashboard JSON | 🟡 | `grafana/dashboard.json` |
| 评测历史 JSONL | 🟡 | `data/eval/history.jsonl` |
| structlog / OTel | ❌ | — |

### 前端体验（F10）

| 项 | 状态 | 说明 |
|----|------|------|
| SSE 流式问答 | 🟡 | API 已有，前端 EventSource |
| Markdown 渲染 | 🟡 | 轻量内联，无外部依赖 |
| 引用可点击 + 采纳埋点 | 🟡 | `rag_citation_click_total` |
| 文档预览 / 搜索 | ❌ | F02 |

### 评测指标（F12）

| 项 | 状态 | 说明 |
|----|------|------|
| Hit@1 / Hit@K / MRR | ✅ | L2 benchmark |
| by_tag 分场景 | ✅ 计算 / 🟡 看板 | `compute_by_tag()` |
| Chunk Recall@K | 🟡 | `expected_chunk_ids` 字段 |
| NDCG@K | ❌ | 需多级相关性标注 |
| confusion 子集基线 | ❌ | 可选 `baseline.json` 扩展 |

---

## 3. 推荐 Sprint 顺序

```
Sprint A（本次）  文档 BACKLOG + pytest + SSE + F14 脚手架 + Recall@K + 看板增强
Sprint B          F14 租户数据隔离 + score_threshold benchmark
Sprint C          Query 改写 + 智能切分
Sprint D          语义缓存 + OTel + POST /api/eval/run
```

---

## 4. 验收与命令

| 能力 | 验证命令 |
|------|----------|
| API 冒烟 | `make test` |
| 评测门禁 | `make eval-smoke` |
| 全路径 L2 | `./.venv/bin/python scripts/benchmark_rag_params.py --modes vector,hybrid,rerank` |
| L3 RAGAS | `./.venv/bin/python scripts/eval_ragas.py --run --ragas` |
| 认证开启 | `AUTH_ENABLED=true` + `Authorization: Bearer <token>` |
| 看板 | `open http://127.0.0.1:8081/eval-dashboard.html` |

---

## 5. 维护约定

1. 新功能落地 → 本文件状态列改为 ✅，并更新对应 Fxx PRD §8。
2. 新增缺口 → 先写本文件与 `05-roadmap-backlog.md`，再开 PRD 小节。
3. 文档中的指标数字必须来自 `data/benchmark/` 或 `make eval-smoke` 实测，禁止手写过期数据。
