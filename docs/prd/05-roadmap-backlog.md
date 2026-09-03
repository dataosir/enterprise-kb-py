# 05 · 路线图与 Backlog

> 已实现能力以 F01–F13 为准；本文件跟踪 **未完成** 与 **下一迭代** 优先级。  
> 技术细节见 [`../enterprise/ENTERPRISE_PLAN.md`](../enterprise/ENTERPRISE_PLAN.md)。

---

## 1. 阶段完成度

| Phase | 主题 | PRD | 状态 |
|---|---|---|---|
| 1 | RAG 基础闭环 | F01–F03, F10–F11 | ✅ 完成 |
| 2a | 检索/生成调参 + Rerank | F04 | ✅ 完成 |
| 2b | BM25 混合检索 | F05 | ✅ 完成 |
| 3 | Redis 会话 + 异步入库 | F06–F07 | ✅ 完成 |
| 4 | pgvector + MinIO | F08–F09 | ✅ 完成 |
| 5 | 认证鉴权 + 多租户 | F14 | 🟡 部分完成（中间件 + 审计） |
| 6 | 可观测 + RAGAS | F12 扩展, F13 扩展 | 🟡 部分完成 |

**Phase 6 已交付**：`GET /metrics`、评测看板（`eval-dashboard.html`）、中间件导图、`make eval-smoke` + `.github/workflows/eval.yml`、`make test`、`L3 eval_ragas.py` 脚手架、用户反馈回流、引用点击埋点、Grafana 模板。  
**Phase 6 待补**：structlog / OpenTelemetry、`POST /api/eval/run`、RAGAS 定期 CI（需 Secret）。

---

## 2. 高优先级 Backlog

| 优先级 | 项 | 关联 | 说明 |
|---|---|---|---|
| P0 | SSE 流式接入 Web UI | F10 | ✅ EventSource + 轻量 Markdown |
| P1 | F14 认证与多租户 | F14 | 🟡 中间件 + 审计日志（租户隔离待补） |
| P1 | Hard benchmark 扩充 | F12 | ✅ 40 条用例 + 6 篇 sample-docs（含混淆集） |
| P1 | pytest API 冒烟 | — | ✅ `make test` |
| P2 | RAGAS 纳入 CI | F12 | 🟡 独立 workflow `eval-ragas.yml` |
| P2 | Chunk Recall@K | F12 | 🟡 `expected_chunk_substrings` |
| P2 | Query 改写 / HyDE | F03, F05 | ❌ 提升召回 |
| P2 | 外置 Grafana 模板 | F13 | 🟡 `grafana/dashboard.json` |
| P2 | by_tag / 历史趋势看板 | F12 | 🟡 eval-dashboard 已展示 |
| P2 | 引用采纳率埋点 | F12 | 🟡 `POST /api/metrics/citation` |
| P3 | 智能切分（按标题） | F01 | 企业文档结构感知 |
| P3 | Windows `package.bat` | F11 | 打包对称 |
| P3 | Embedding 模型 UI 切换 | F04, F08 | 换模型需重建提示 |

---

## 3. 功能号 → 迭代建议

| 迭代 | 功能号 | 交付物 |
|---|---|---|
| Sprint A | F10 | 前端 SSE + Markdown 回答渲染 |
| Sprint B | F14 | 认证中间件 + tenant 过滤 |
| Sprint C | F12, F13 | RAGAS CI job + Grafana 模板 |
| Sprint D | F05, F03 | Query 改写 + 检索对比 UI |

---

## 4. 与 Java 版迁移检查点

| 能力 | Python PRD | Java 版 | 对齐状态 |
|---|---|---|---|
| 混合检索 | F05 | ✅ | 概念对齐 |
| Redis 会话 | F06 | ✅ | 概念对齐 |
| pgvector | F08 | ✅ | 表结构待文档化 |
| 认证多租户 | F14 | ✅ | Python 未实现 |
| RAGAS | F12 | 部分 | 规划对齐 |

---

## 5. 维护说明

1. 完成 Backlog 项后，更新对应 Fxx 的「已知缺口」并在此表标记 ✅。
2. 大版本规划变更先改 [`../enterprise/ENTERPRISE_PLAN.md`](../enterprise/ENTERPRISE_PLAN.md)，再摘要到本文件。
3. 不删除已交付 Phase 记录，仅更新状态列。
