import os
import re
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

_hf_endpoint = os.getenv("HF_ENDPOINT")
if _hf_endpoint:
    os.environ["HF_ENDPOINT"] = _hf_endpoint

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
CHROMA_DIR = DATA_DIR / "chroma"
DB_PATH = DATA_DIR / "metadata.db"
SAMPLE_DOCS_DIR = BASE_DIR / "sample-docs"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "deepseek-chat")

# DeepSeek 无 Embedding API，默认用本地中文向量模型
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
HF_ENDPOINT = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")

TOP_K = int(os.getenv("RAG_TOP_K", "4"))
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "64"))
FETCH_K = int(os.getenv("RAG_FETCH_K", "20"))
USE_MMR = os.getenv("RAG_USE_MMR", "false").lower() in {"1", "true", "yes"}
MMR_LAMBDA = float(os.getenv("RAG_MMR_LAMBDA", "0.5"))
USE_RERANK = os.getenv("RAG_USE_RERANK", "false").lower() in {"1", "true", "yes"}
TEMPERATURE = float(os.getenv("RAG_TEMPERATURE", "0.2"))
HISTORY_TURNS = int(os.getenv("RAG_HISTORY_TURNS", "3"))
MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "4000"))
SNIPPET_LENGTH = int(os.getenv("RAG_SNIPPET_LENGTH", "200"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))

DEFAULT_SYSTEM_PROMPT = (
    "你是企业内部知识库助手。仅根据提供的上下文回答，"
    "不知道就说不知道。回答简洁，并在末尾列出引用文档名。"
)

_score_threshold_raw = os.getenv("RAG_SCORE_THRESHOLD", "").strip()
SCORE_THRESHOLD: float | None = float(_score_threshold_raw) if _score_threshold_raw else None

RETRIEVAL_MODE = os.getenv("RAG_RETRIEVAL_MODE", "vector")
HYBRID_ALPHA = float(os.getenv("RAG_HYBRID_ALPHA", "0.5"))
RRF_K = int(os.getenv("RAG_RRF_K", "60"))

# ── 企业中间件（统一在 .env 维护，见 .env.example / docker-compose.enterprise.yml）──


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _normalize_host(host: str) -> str:
    """去掉误填的 http(s):// 前缀，只保留 IP 或域名。"""
    host = host.strip().rstrip("/")
    for prefix in ("https://", "http://"):
        if host.lower().startswith(prefix):
            host = host[len(prefix) :]
    return host.split("/", 1)[0]


def _normalize_database_url(url: str) -> str:
    """兼容 JDBC 写法与 host 中误带的 http://（Python/psycopg 仅支持 postgresql://）。"""
    url = url.strip()
    if url.lower().startswith("jdbc:"):
        url = url[5:]
    if not url:
        return ""
    # postgresql://http://host:5432/db 或 postgresql://user:pass@http://host:5432/db
    url = re.sub(r"(^postgresql://)(?:https?://)", r"\1", url, flags=re.IGNORECASE)
    url = re.sub(r"(@)(?:https?://)", r"\1", url, flags=re.IGNORECASE)
    return url


# 宿主机地址（设置后自动拼接下方连接串；也可单独覆盖各 *_URL）
MIDDLEWARE_HOST = _normalize_host(_env("MIDDLEWARE_HOST"))

# 与 docker-compose.enterprise.yml 共用（默认值与 .env.example 一致）
POSTGRES_USER = _env("POSTGRES_USER", "kb")
POSTGRES_PASSWORD = _env("POSTGRES_PASSWORD", "changeme_pg_password")
POSTGRES_DB = _env("POSTGRES_DB", "enterprise_kb")
POSTGRES_HOST_PORT = _env("POSTGRES_HOST_PORT", "5433")
MINIO_ROOT_USER = _env("MINIO_ROOT_USER", "kbadmin")
MINIO_ROOT_PASSWORD = _env("MINIO_ROOT_PASSWORD", "changeme_minio_password")
ES_JAVA_OPTS = _env("ES_JAVA_OPTS", "-Xms256m -Xmx256m")


def _middleware_urls() -> dict[str, str]:
    if not MIDDLEWARE_HOST:
        return {}
    urls = {
        "REDIS_URL": f"redis://{MIDDLEWARE_HOST}:6379/0",
        "ES_URL": f"http://{MIDDLEWARE_HOST}:9200",
        "S3_ENDPOINT": f"http://{MIDDLEWARE_HOST}:9000",
    }
    if POSTGRES_PASSWORD:
        pw = quote_plus(POSTGRES_PASSWORD)
        urls["DATABASE_URL"] = (
            f"postgresql://{POSTGRES_USER}:{pw}@{MIDDLEWARE_HOST}:{POSTGRES_HOST_PORT}/{POSTGRES_DB}"
        )
    return urls


_mw = _middleware_urls()

# Elasticsearch（Phase 2b 混合检索，留空则仅向量检索）
ES_URL = _env("ES_URL") or _mw.get("ES_URL", "")
ES_INDEX_PREFIX = _env("ES_INDEX_PREFIX", "enterprise_kb")

# Redis（Phase 3 会话持久化 + 异步入库）
REDIS_URL = _env("REDIS_URL") or _mw.get("REDIS_URL", "")
CONVERSATION_TTL_SECONDS = int(os.getenv("CONVERSATION_TTL_SECONDS", "604800"))
CONVERSATION_STORE = _env("CONVERSATION_STORE", "auto").lower()  # auto | memory | redis
JOB_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "86400"))
# 配置 REDIS_URL 后默认开启异步入库；设为 false 可强制同步
_async_ingest_raw = _env("ASYNC_INGEST", "auto").lower()
ASYNC_INGEST = (
    _async_ingest_raw in {"1", "true", "yes"}
    if _async_ingest_raw != "auto"
    else bool(REDIS_URL)
)
ASYNC_INGEST_THRESHOLD_MB = float(os.getenv("ASYNC_INGEST_THRESHOLD_MB", "1"))

# PostgreSQL + pgvector（Phase 4 向量库）
DATABASE_URL = _normalize_database_url(_env("DATABASE_URL") or _mw.get("DATABASE_URL", ""))
VECTOR_STORE = _env("VECTOR_STORE", "chroma").lower()  # chroma | pgvector

# MinIO / S3（Phase 4 文件存储）
STORAGE_BACKEND = _env("STORAGE_BACKEND", "local").lower()  # local | s3
S3_ENDPOINT = _env("S3_ENDPOINT") or _mw.get("S3_ENDPOINT", "")
S3_ACCESS_KEY = _env("S3_ACCESS_KEY") or MINIO_ROOT_USER
S3_SECRET_KEY = _env("S3_SECRET_KEY") or MINIO_ROOT_PASSWORD
S3_BUCKET = _env("S3_BUCKET", "enterprise-kb")
