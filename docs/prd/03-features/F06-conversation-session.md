# F06 · 会话持久化

## 1. 背景与目标

多轮问答需要携带历史上下文；进程内存会话在重启后丢失。Redis 持久化支持重启恢复与多实例共享（未来扩展）。

## 2. 用户故事 / 场景

- 作为用户，我追问「那远程办公呢？」，系统理解上一轮话题。
- 作为运维，服务重启后用户刷新页面，历史对话仍在（Redis 模式）。
- 作为 Demo 用户，未配置 Redis 时自动用内存，零配置可用。

## 3. 功能范围

**In**

- 创建会话：`POST /api/chat/conversation`
- 获取历史：`GET /api/conversations/{id}`
- 清空会话：`DELETE /api/conversations/{id}`
- 存储后端：Memory / Redis（`CONVERSATION_STORE=auto`）
- TTL 默认 7 天（Redis）
- Key 格式：`conv:{tenant}:{conv_id}`（tenant 默认 `default`）

**Out**

- 会话列表 / 搜索
- 跨设备会话同步 UI
- 会话导出

## 4. 主流程与边界

1. 问答时 `RagEngine` 从 store 读取最近 `historyTurns` 轮。
2. 生成后 append user + assistant 消息。
3. Redis 不可用时 `auto` 回退 Memory。

**边界**：内存模式下多 Worker 不共享会话；仅单实例 Demo 适用。

## 5. 关键配置键

| 键 | 默认 | 用途 |
|---|---|---|
| `REDIS_URL` | — | Redis 连接 |
| `CONVERSATION_STORE` | auto | memory / redis / auto |
| `CONVERSATION_TTL_SECONDS` | 604800 | 7 天 TTL |

## 6. 代码锚点

- `app/store/conversation_store.py` — Memory / Redis 实现
- `app/store/redis_client.py` — 连接与状态
- `app/services/rag_engine.py` — `_format_history()`
- `app/main.py` — conversation 路由

## 7. 验收标准

- [ ] 同一 conversationId 连续两轮问答，第二轮可引用第一轮
- [ ] Redis 模式下重启 API 后 `GET /api/conversations/{id}` 仍有历史
- [ ] 未配置 Redis 时 health 显示 `conversationStore: memory`
- [ ] `DELETE` 后历史为空

## 8. 已知缺口 / 待迭代

- 前端无「新建会话」明显入口（API 已有）
- 无会话 token 用量统计
- 多租户 tenant 未在 API 层暴露（F14）
