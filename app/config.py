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
