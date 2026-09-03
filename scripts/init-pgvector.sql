-- PostgreSQL + pgvector 初始化（docker-compose.enterprise.yml 首次启动自动执行）
CREATE EXTENSION IF NOT EXISTS vector;

-- 向量片段表（维度在应用首次连接时按 Embedding 模型自动创建）
-- 若需手动预创建，将 512 改为你使用的 Embedding 维度（BGE-small-zh 为 512）
CREATE TABLE IF NOT EXISTS kb_chunks (
    id          TEXT PRIMARY KEY,
    doc_id      TEXT NOT NULL,
    filename    TEXT NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(512),
    metadata    JSONB DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS kb_chunks_doc_id_idx ON kb_chunks (doc_id);

-- 数据量较大时可手动创建 IVFFlat 索引（需先有数据）:
-- CREATE INDEX IF NOT EXISTS kb_chunks_embedding_idx
--   ON kb_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
