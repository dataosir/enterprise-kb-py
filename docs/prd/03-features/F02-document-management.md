# F02 · 文档管理

## 1. 背景与目标

提供文档元数据的 CRUD 与状态可见性，使用户知道知识库里有什么、处理是否完成，并支持删除过时文档。

## 2. 用户故事 / 场景

- 作为用户，我在侧栏看到所有已入库文档及片段数。
- 作为管理员，我删除过期制度，向量与 ES 索引同步清除。
- 作为运维，我通过 health 接口统计 `documents` / `ready_documents`。

## 3. 功能范围

**In**

- 文档列表（id、filename、chunkCount、status、createdAt）
- 按 doc_id 删除（向量 + ES + 元数据 + 存储文件）
- 健康检查中的文档统计
- Web UI 侧栏列表与 `PROCESSING` / `FAILED` 状态展示

**Out**

- 文档版本管理
- 批量导入/导出
- 文档级权限（见 F14）

## 4. 主流程与边界

1. `GET /api/documents` → SQLite 查询全量记录。
2. `DELETE /api/documents/{id}` → 删向量 → 删 ES → 删存储 → 删 SQLite。
3. 删除不存在的 id 返回 404。

**边界**：删除进行中（`PROCESSING`）的文档可能导致 Worker 完成后写回残留，需人工确认。

## 5. 关键配置键

无独立配置；依赖 F08/F09 后端类型。

## 6. 代码锚点

- `app/store/document_store.py` — SQLite CRUD
- `app/main.py` — `GET/DELETE /api/documents`
- `static/index.html` — 侧栏文档列表

## 7. 验收标准

- [ ] `curl /api/documents` 返回 JSON 数组含 3 篇示例（首次启动后）
- [ ] `DELETE` 后列表减少，再问相关问题无该文档来源
- [ ] `GET /api/health` 的 `documents` 与列表长度一致

## 8. 已知缺口 / 待迭代

- 无分页（文档量大时性能未优化）
- 无搜索/过滤（按文件名、状态）
- 无文档预览（仅问答间接引用）
