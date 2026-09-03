from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_pg_available: bool | None = None


def pg_status() -> str:
  """not_configured | connected | unavailable"""
  from app.config import DATABASE_URL

  if not DATABASE_URL:
    return "not_configured"
  if _pg_available is False:
    return "unavailable"
  if _pg_available is True:
    return "connected"
  return "connected" if check_pg_connection() else "unavailable"


def check_pg_connection() -> bool:
  global _pg_available
  from app.config import DATABASE_URL

  if not DATABASE_URL:
    _pg_available = False
    return False
  try:
    with get_pg_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT 1")
    _pg_available = True
    return True
  except Exception as exc:
    logger.warning("PostgreSQL connection failed: %s", exc)
    _pg_available = False
    return False


def get_pg_connection() -> Any:
  import psycopg
  from pgvector.psycopg import register_vector

  from app.config import DATABASE_URL

  conn = psycopg.connect(DATABASE_URL)
  register_vector(conn)
  return conn
