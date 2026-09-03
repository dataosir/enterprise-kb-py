# F10 · Web UI

## 1. 背景与目标

提供零前端工程的浏览器界面：聊天、上传、文档列表、RAG 调参、健康状态，降低开源用户上手成本。

## 2. 用户故事 / 场景

- 作为用户，我打开 `http://localhost:8081` 即可问答，无需 curl。
- 作为调参者，我在侧栏改 Top-K、预览检索、重建索引。
- 作为运维，顶栏显示 Redis/ES/向量库/存储连接状态。

## 3. 功能范围

**In**

- 聊天主区域（问题输入、回答、引用来源）
- 侧栏：文档列表、上传、RAG 参数三栏面板
- 参数：应用 / 重建索引 / 同步 ES / 预览检索 / 恢复默认
- 文档状态：`PROCESSING` / `FAILED` 展示与 job 轮询
- 顶栏健康信息聚合
- 静态资源 `static/index.html`（单页，无构建链）

**Out**

- 响应式移动端优化
- 暗黑模式 / 国际化
- 完整 SSE 流式打字机（✅ EventSource + 轻量 Markdown）

## 4. 主流程与边界

1. 页面加载 → `GET /api/health` + `/api/documents` + `/api/settings/rag`。
2. 发送问题 → `POST /api/chat`。
3. 调参 → `PUT /api/settings/rag` → 可选 preview sources。
4. 上传 → `POST /api/documents/upload` → 轮询 job 或刷新列表。

**边界**：纯静态 HTML，无 SSR；CORS 默认同源。

## 5. 关键配置键

无 UI 专属配置；端口由 `PORT` 环境变量控制。

## 6. 代码锚点

- `static/index.html` — 全部 UI 逻辑
- `app/main.py` — `StaticFiles` 挂载

## 7. 验收标准

- [ ] 浏览器可完成：提问 → 得回答 → 见 sources
- [ ] 侧栏显示 6 篇示例文档（3 基础 + 3 hard 混淆集）
- [ ] 修改 topK 应用后预览 sources 条数变化
- [ ] 上传 md 文件后列表新增一项
- [ ] ES/Redis 配置后顶栏状态正确

## 8. 已知缺口 / 待迭代

- a11y 无障碍
- 引用片段展开预览（F02 文档预览）
- System Prompt 文本框无语法高亮
