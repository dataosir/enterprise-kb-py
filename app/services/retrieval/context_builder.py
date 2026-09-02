from __future__ import annotations

from app.models.domain import RetrievedChunk


def build_context(sources: list[RetrievedChunk], max_chars: int) -> str:
    """按字符预算拼接检索上下文，避免撑爆 LLM 窗口。"""
    if max_chars <= 0 or not sources:
        return ""

    parts: list[str] = []
    total = 0
    separator_len = 2  # "\n\n"

    for source in sources:
        part = f"[{source.filename}] {source.content}"
        next_total = total + len(part) + (separator_len if parts else 0)
        if next_total <= max_chars:
            parts.append(part)
            total = next_total
            continue

        remaining = max_chars - total - (separator_len if parts else 0)
        if remaining > 80:
            parts.append(part[: remaining - 3] + "...")
        break

    return "\n\n".join(parts)
