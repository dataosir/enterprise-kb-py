# F04 · 检索与生成调参

## 1. 背景与目标

将 RAG 核心参数暴露为运行时配置，支持页面动态修改、持久化与索引重建，便于企业场景下调试检索质量与生成行为。

## 2. 用户故事 / 场景

- 作为算法工程师，我调高 Top-K 并预览检索，对比 snippet 数量与 score。
- 作为产品，我修改 System Prompt，约束回答风格与免责表述。
- 作为运维，我改 Chunk Size 后点「重建索引」，全库按新粒度重切分。

## 3. 功能范围

**In**

- 12 项参数读写（见下表）
- 持久化 `data/rag_settings.json`，重启保留
- `needsReindex` 提示（chunk 与 indexed 不一致）
- 页面三栏面板：检索 / 生成 / 索引
- MMR 与 Rerank 互斥校验

**Out**

- Embedding 模型切换 UI（仅 .env）
- A/B 实验自动对比（见 F12 benchmark）

## 4. 参数一览

| 参数 | 默认 | 生效 | 说明 |
|---|---|---|---|
| `topK` | 4 | 立即 | 最终检索片段数 |
| `fetchK` | 20 | 立即 | 初筛候选数 |
| `scoreThreshold` | null | 立即 | L2 距离上限过滤 |
| `useMmr` | false | 立即 | 最大边际相关性 |
| `mmrLambda` | 0.5 | 立即 | MMR 相关性权重 |
| `useRerank` | false | 立即 | Cross-Encoder 重排 |
| `temperature` | 0.2 | 立即 | LLM 温度 |
| `historyTurns` | 3 | 立即 | 对话历史轮数 |
| `maxContextChars` | 4000 | 立即 | 上下文字符上限 |
| `systemPrompt` | 内置 | 立即 | 系统提示词 |
| `snippetLength` | 200 | 立即 | 预览展示长度 |
| `chunkSize` / `chunkOverlap` | 512/64 | 需重建 | 切分参数 |

## 5. 主流程与边界

1. `PUT /api/settings/rag` 校验范围与互斥（MMR vs Rerank，混合 vs MMR）。
2. 立即生效项更新内存 `RagSettings` 并写 JSON。
3. Chunk 变更仅更新目标值；`indexedChunkSize` 在 `reindex` 后同步。
4. `POST /api/settings/rag/reindex` 遍历 READY 文档重新入库。

**边界**：Rerank 懒加载约 +400MB 内存，低内存设备慎用。

## 6. 代码锚点

- `app/store/rag_settings.py` — 持久化与校验
- `app/services/rag_engine.py` — `update_settings()`, `reindex_all()`
- `app/main.py` — settings / reindex API
- `static/index.html` — RAG 参数面板

## 7. 验收标准

- [ ] `GET /api/settings/rag` 返回完整 12 项
- [ ] 修改 topK 后 `sources` 返回条数变化（无需重启）
- [ ] 修改 chunkSize 后 `needsReindex=true`，重建后 `indexedChunkSize` 同步
- [ ] 同时开启 MMR + Rerank 返回 400

## 8. 已知缺口 / 待迭代

- 无参数变更审计日志
- 无「恢复上次索引参数」快照
- Rerank 模型不可在页面选择（固定 bge-reranker-base）
