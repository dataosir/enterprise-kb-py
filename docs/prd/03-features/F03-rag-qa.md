# F03 · RAG 问答

## 1. 背景与目标

基于检索到的文档片段，调用 LLM 生成有据可依的回答，并返回引用来源，支持流式输出与多轮对话。

## 2. 用户故事 / 场景

- 作为员工，我问「购买后几天内可以全额退款？」，得到基于制度的回答和文档名引用。
- 作为开发者，我用 `/api/chat/sources` 单独看检索结果，不消耗 LLM Token。
- 作为用户，我开启 SSE 流式，看到打字机效果。

## 3. 功能范围

**In**

- 同步问答：`POST /api/chat`
- 流式问答：`GET /api/chat/stream`（SSE）
- 检索预览：`GET /api/chat/sources`
- 多轮对话：携带 `conversationId`，保留最近 N 轮历史
- 引用来源：返回 `RetrievedChunk`（filename、content/snippet、score）
- System Prompt 约束「仅根据上下文回答」

**Out**

- Query 改写 / HyDE（路线图）
- 多模态（图片问答）
- 答案置信度评分

## 4. 主流程与边界

```
question
  → retrieve_sources()（F04/F05 链路）
  → context_builder 截断（maxContextChars）
  → 拼接 history（historyTurns）
  → ChatPromptTemplate + LLM（temperature）
  → answer + sources
  → 写入会话存储（F06）
```

**边界**：无相关片段时 context 为「（无相关上下文）」，LLM 应回答不知道；检索阈值过高可能导致空上下文。

## 5. 关键配置键

| 键 | 默认 | 用途 |
|---|---|---|
| `OPENAI_CHAT_MODEL` | deepseek-chat | 对话模型 |
| `OPENAI_BASE_URL` | — | API 端点 |
| `temperature` | 0.2 | RagSettings |
| `historyTurns` | 3 | 历史轮数 |
| `maxContextChars` | 4000 | 上下文上限 |
| `systemPrompt` | 内置 | 约束策略 |

## 6. 代码锚点

- `app/services/rag_engine.py` — `chat()`, `retrieve_sources()`, `chat_stream()`
- `app/services/retrieval/context_builder.py` — 上下文截断
- `app/main.py` — chat 相关路由

## 7. 验收标准

- [ ] `POST /api/chat` 对 sample-docs 问题返回非空 answer 和 sources
- [ ] sources 中 filename 命中预期文档（如退款问题 → refund-policy.md）
- [ ] 同一 conversationId 第二轮可引用上一轮上下文
- [ ] `GET /api/chat/sources` 不调用 LLM 仍返回检索结果

## 8. 已知缺口 / 待迭代

- 流式接口前端未完全接入打字机（API 已有）
- 无答案与来源的 faithfulness 自动评分（见 F12）
- 无引用段落跳转定位（仅文档名）
