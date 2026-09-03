# F05 · 混合检索（BM25 + 向量）

## 1. 背景与目标

纯向量检索对专有名词、编号、精确关键词召回弱；通过 Elasticsearch BM25 与向量检索 RRF 融合，提升企业文档（制度、合同、工单号）的召回率。

## 2. 用户故事 / 场景

- 作为用户，我问含精确条款编号的问题，混合检索比纯向量更易命中。
- 作为管理员，我配置 ES 后点「同步 ES 索引」，完成历史文档双写。
- 作为开发者，ES 不可用时系统自动回退纯向量，不阻塞服务。

## 3. 功能范围

**In**

- 检索模式：`vector` / `hybrid`
- 向量 Top fetch_k + BM25 Top fetch_k
- 加权 RRF 融合（`hybridAlpha`、`rrfK`）
- 入库双写 ES（IK 中文分词）
- 全量同步：`POST /api/settings/rag/sync-es`
- 健康检查 ES 状态
- 与 Rerank / 阈值过滤链路兼容

**Out**

- 多查询扩展 / HyDE
- 学习排序（LTR）
- OpenSearch 官方客户端以外的搜索引擎

## 4. 主流程与边界

```
question
  → 向量 similarity_search (fetch_k)
  → ES BM25 search (fetch_k)
  → RRF 融合 (α·向量 + (1-α)·BM25)
  → 阈值过滤 → Rerank（可选）→ topK
```

**边界**：

- ES 未配置或索引为空 → 回退 `vector`，日志警告
- `hybrid` 与 `useMmr` 互斥（前后端校验）
- 6GB NAS：ES 堆建议 256MB，与应用 Rerank 勿同时高开

## 5. 关键配置键

| 键 | 默认 | 用途 |
|---|---|---|
| `ES_URL` | — | Elasticsearch 地址 |
| `ES_INDEX_PREFIX` | enterprise_kb | 索引前缀 |
| `RAG_RETRIEVAL_MODE` | vector | 默认模式 |
| `hybridAlpha` | 0.5 | 向量权重 α |
| `rrfK` | 60 | RRF 常数 |

## 6. 代码锚点

- `app/services/retrieval/es_store.py` — ES 索引与 BM25
- `app/services/retrieval/hybrid.py` — RRF 融合
- `app/services/rag_engine.py` — `retrieve_sources()`, `sync_es_index()`
- `app/main.py` — `POST /api/settings/rag/sync-es`

## 7. 验收标准

- [ ] 配置 ES 后 health 显示 `esStatus: connected`
- [ ] `sync-es` 返回同步 chunk 数 > 0
- [ ] `retrievalMode=hybrid` 时 sources 可能来自 ES 独有命中
- [ ] ES 宕机后问答仍可用（纯向量回退）

## 8. 已知缺口 / 待迭代

- 无 BM25 单独调试预览（与向量分开展示）
- 融合权重无自动调优
- 删除文档时 ES 与向量偶发不一致需 `sync-es` 修复
