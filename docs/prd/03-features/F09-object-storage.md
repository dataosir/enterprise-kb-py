# F09 · 对象存储（本地 / MinIO S3）

## 1. 背景与目标

上传的原始文件需要可靠存储；单机 `data/uploads/` 适合 Demo，MinIO/S3 适合多实例与 NAS 部署。抽象层统一上传、下载、删除路径。

## 2. 用户故事 / 场景

- 作为 Demo 用户，文件存在本地 `data/uploads/{doc_id}/`。
- 作为企业用户，文件存入 MinIO bucket，API 多实例共享。
- 作为入库 Worker，从 S3 下载到临时目录处理，完成后清理。

## 3. 功能范围

**In**

- 后端：`local`（默认）/ `s3`
- 操作：`save`, `get_local_path`, `delete`, `exists`
- S3 兼容 MinIO（`S3_ENDPOINT`）
- 健康检查 `storageBackend` / `s3Status`

**Out**

- 预签名 URL 直传浏览器
- 版本控制与生命周期策略
- 加密 at-rest 配置

## 4. 主流程与边界

1. 上传 → `object_storage.save(doc_id, filename, bytes)`。
2. 入库时 `get_local_path`：local 直接读；s3 下载到 temp。
3. 删除文档 → `delete(doc_id)` 清除前缀下所有对象。

**边界**：S3 凭证错误时上传失败 500；需在 health 中可见 `s3Status`。

## 5. 关键配置键

| 键 | 默认 | 用途 |
|---|---|---|
| `STORAGE_BACKEND` | local | local / s3 |
| `S3_ENDPOINT` | — | MinIO 地址 |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | — | 凭据 |
| `S3_BUCKET` | enterprise-kb | 桶名 |

## 6. 代码锚点

- `app/store/object_storage/` — local, s3, factory
- `app/main.py` — 上传保存逻辑
- `app/services/rag_engine.py` — 重建索引时取文件路径

## 7. 验收标准

- [ ] 默认 `storageBackend: local`，上传后可 `data/uploads` 找到文件
- [ ] 配置 S3 后 health `s3Status: connected`
- [ ] S3 模式下上传+入库+问答全链路通过
- [ ] 删除文档后存储中文件消失

## 8. 已知缺口 / 待迭代

- 无存储用量统计 API
- 大文件未做分片上传
- bucket 自动创建依赖部署脚本（非应用内）
