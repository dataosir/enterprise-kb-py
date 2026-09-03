# F14 · 认证与多租户（规划）

## 1. 背景与目标

企业内网部署需要身份认证、租户隔离与审计。当前 Demo 无鉴权，任意访问者可上传/删除/调参。Phase 5 规划 JWT/OIDC 与 `tenant_id` 贯穿存储与检索。

> **状态：🟡 部分完成** — 认证中间件与审计已落地；租户数据隔离待补。详见 [`../../tech/BACKLOG.md`](../../tech/BACKLOG.md)。

## 2. 用户故事 / 场景

- 作为企业 IT，员工通过 SSO 登录后只能访问本部门知识库。
- 作为 SaaS 运营方，不同租户数据隔离（向量、文档、会话）。
- 作为合规，操作审计日志可追溯谁上传/删除了什么。

## 3. 功能范围（规划）

**In（目标）**

- JWT / OIDC 认证（可选 Keycloak）
- API 路由鉴权中间件
- `tenant_id` 注入：SQLite、Chroma/PG、ES index、Redis key、S3 prefix
- 角色：admin / editor / viewer
- 审计日志表

**Out**

- 完整 RBAC 管理 UI
- 计费与配额
- 公网零信任网关（仅文档建议）

## 4. 主流程与边界（设计草案）

```
Request → JWT 校验 → 解析 tenant_id + roles
    → 文档/检索/会话 API 带租户过滤
    → 审计写 append-only log
```

**边界**：与 Demo 模式共存 — `AUTH_ENABLED=false` 时保持当前无鉴权行为。

## 5. 关键配置键（规划）

| 键 | 用途 |
|---|---|
| `AUTH_ENABLED` | 是否启用 |
| `OIDC_ISSUER_URL` | IdP 地址 |
| `JWT_SECRET` | 本地 JWT 签名 |
| `DEFAULT_TENANT` | Demo 默认租户 |

## 6. 代码锚点

- `app/middleware/auth.py` — Bearer Token 中间件（`AUTH_ENABLED` 开关）
- `app/store/audit_log.py` — 审计 JSONL
- `scripts/generate_token.py` — 生成演示 Token
- 现有 `conversation_store` 已预留 `tenant` 参数

## 7. 验收标准（规划）

- [x] `AUTH_ENABLED=true` 时无 token 返回 401
- [ ] 租户 A 无法列出/检索租户 B 文档
- [x] 审计日志记录 upload/delete/settings 变更
- [x] `AUTH_ENABLED=false` 时行为与当前 Demo 一致

## 8. 已知缺口

- **租户数据隔离** — store/vector/ES 层 filter 未实现
- 与 Java 版 `enterprise-kb` 权限模型对齐表待补充
