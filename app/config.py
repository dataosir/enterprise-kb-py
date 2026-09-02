import os
from pathlib import Path

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

# Phase 2b: Elasticsearch 混合检索（留空则仅向量检索）
ES_URL = os.getenv("ES_URL", "").strip()
ES_INDEX_PREFIX = os.getenv("ES_INDEX_PREFIX", "enterprise_kb")
RETRIEVAL_MODE = os.getenv("RAG_RETRIEVAL_MODE", "vector")
HYBRID_ALPHA = float(os.getenv("RAG_HYBRID_ALPHA", "0.5"))
RRF_K = int(os.getenv("RAG_RRF_K", "60"))
