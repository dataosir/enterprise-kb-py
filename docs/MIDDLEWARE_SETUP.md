# 企业级中间件安装指南

> 本文说明如何部署企业知识库配套的中间件栈，适用于 **飞牛 NAS**、Linux 服务器或任何支持 Docker 的环境。  
> 技术方案背景见 [ENTERPRISE_PLAN.md](./ENTERPRISE_PLAN.md)。

---

## 1. 部署概览

| 服务 | 容器名 | 默认端口 | 用途 |
|------|--------|----------|------|
| Redis 7 | `kb-redis` | **6379** | 会话持久化、限流、任务队列 |
| PostgreSQL 16 + pgvector | `kb-postgres` | **5433**（映射到容器 5432） | 生产向量库、元数据 |
| Elasticsearch 8.15 | `kb-elasticsearch` | **9200** | BM25 混合检索 |
| MinIO | `kb-minio` | **9000**（API）/ **9001**（控制台） | 对象存储 |
| IK 中文分词 | — | — | ES 中文分词插件（需手动安装） |

**Compose 文件：** 项目根目录 `docker-compose.enterprise.yml`

---

## 2. 资源建议（低内存 NAS）

飞牛等 **6GB 内存** 设备建议：

| 服务 | 内存策略 |
|------|----------|
| Elasticsearch | 堆内存 **256MB**（compose 默认） |
| Redis | 最大 **128MB**，`allkeys-lru` 淘汰 |
| PostgreSQL + MinIO | 按需，通常各 100~300MB |
| Rerank 模型（应用侧） | 默认**关闭**，开启约 +400MB |

> 宿主机 **5432** 常被系统 PostgreSQL 占用，compose 将知识库 PG 映射到 **5433**。

---

## 3. 一键部署

### 3.1 前置条件

- Docker + Docker Compose v2
- 端口未被占用：`6379`、`5433`、`9200`、`9000`、`9001`
- 有 sudo 权限（部分 NAS 需 `sudo docker`）

### 3.2 启动

```bash
# 在项目根目录
export POSTGRES_PASSWORD='your_secure_pg_password'
export MINIO_ROOT_PASSWORD='your_secure_minio_password'

docker compose -f docker-compose.enterprise.yml pull
docker compose -f docker-compose.enterprise.yml up -d
docker compose -f docker-compose.enterprise.yml ps
```

### 3.3 安装 Elasticsearch IK 中文分词（混合检索必做）

```bash
docker exec kb-elasticsearch bin/elasticsearch-plugin install -b \
  https://get.infini.cloud/elasticsearch/analysis-ik/8.15.0

docker compose -f docker-compose.enterprise.yml restart elasticsearch
```

等待约 30 秒后验证：

```bash
curl http://127.0.0.1:9200/_cluster/health?pretty
docker exec kb-elasticsearch bin/elasticsearch-plugin list
# 应输出: analysis-ik
```

---

## 4. 验证清单

将 `YOUR_HOST` 替换为你的 NAS / 服务器内网 IP 或 `127.0.0.1`：

```bash
# Redis
docker exec kb-redis redis-cli ping
# → PONG

# PostgreSQL + pgvector
docker exec kb-postgres psql -U kb -d enterprise_kb -c "SELECT extname FROM pg_extension;"
# → vector

# Elasticsearch
curl http://YOUR_HOST:9200/_cluster/health?pretty

# IK 分词测试
curl -X POST "http://YOUR_HOST:9200/_analyze" \
  -H "Content-Type: application/json" \
  -d '{"analyzer":"ik_max_word","text":"企业知识库退款政策"}'

# MinIO
curl http://YOUR_HOST:9000/minio/health/live
```

MinIO 控制台：`http://YOUR_HOST:9001`（默认用户 `kbadmin`，密码见 compose 环境变量）

---

## 5. 应用侧配置

复制 `.env.enterprise.example` 为本地配置，填入 **YOUR_HOST** 与密码：

```bash
REDIS_URL=redis://YOUR_HOST:6379/0
DATABASE_URL=postgresql://kb:YOUR_PG_PASSWORD@YOUR_HOST:5433/enterprise_kb
ES_URL=http://YOUR_HOST:9200
S3_ENDPOINT=http://YOUR_HOST:9000
S3_ACCESS_KEY=kbadmin
S3_SECRET_KEY=YOUR_MINIO_PASSWORD
```

> **安全提示：** 请勿将真实密码、内网 IP 提交到公开 Git 仓库。生产环境请为 ES / MinIO / PG 开启认证。

> 当前 Demo 应用仍默认使用 Chroma + SQLite；上述变量供 **Phase 2b–4** 开发对接时使用。

---

## 6. 日常运维

```bash
# 查看状态
docker compose -f docker-compose.enterprise.yml ps

# 重启单个服务
docker compose -f docker-compose.enterprise.yml restart redis

# 查看日志
docker logs -f kb-elasticsearch --tail 100

# 停止 / 启动
docker compose -f docker-compose.enterprise.yml down
docker compose -f docker-compose.enterprise.yml up -d

# 完全清理（⚠️ 会删除所有数据卷）
docker compose -f docker-compose.enterprise.yml down -v
```

---

## 7. 常见问题

### Elasticsearch 启动慢或 OOM？

- 检查 `docker logs kb-elasticsearch`
- 确认 `ES_JAVA_OPTS=-Xms256m -Xmx256m`（6GB NAS 推荐）
- 确保宿主机剩余内存 > 1.5GB

### PostgreSQL 连不上 5432？

请使用 compose 映射端口 **5433**。

### 从外网访问？

默认应仅内网可达。外网需 VPN 或反向代理，并**务必**配置认证。

---

## 8. 下一步（开发对接）

中间件就绪后，按 [ENTERPRISE_PLAN.md](./ENTERPRISE_PLAN.md) 推进：

| 阶段 | 内容 | 依赖中间件 |
|------|------|-----------|
| Phase 2a | 调参面板 + Rerank + 阈值过滤 | 无 |
| Phase 2b | ES 混合检索 | Elasticsearch + IK |
| Phase 3 | Redis 会话 + 异步入库 | Redis |
| Phase 4 | pgvector 向量库 + MinIO 文件 | PostgreSQL + MinIO |
