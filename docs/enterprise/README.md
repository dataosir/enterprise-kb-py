# 企业层（enterprise/）

从 Demo 到企业级知识库的方案、部署与质量评估。

| 文件 | 内容 |
|---|---|
| [`ENTERPRISE_PLAN.md`](ENTERPRISE_PLAN.md) | 分阶段演进（混合检索、Redis、pgvector、鉴权、RAGAS） |
| [`MIDDLEWARE_SETUP.md`](MIDDLEWARE_SETUP.md) | Redis / Elasticsearch / PostgreSQL / MinIO 部署指南 |
| [`RAG_EVALUATION.md`](RAG_EVALUATION.md) | 切分规则量化、Hit@K、RAGAS 指标与面试要点 |

**凭据说明：** 账号密码仅在本地 `.env` 配置，文档不记录真实密码。模板见 [`.env.example`](../../.env.example)。
