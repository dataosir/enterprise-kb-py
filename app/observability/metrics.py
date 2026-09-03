"""轻量 Prometheus 风格指标（无额外依赖）。"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict


class _Histogram:
    def __init__(self, buckets: tuple[float, ...]) -> None:
        self.buckets = buckets
        self.counts = {b: 0 for b in buckets}
        self.inf_count = 0
        self.sum = 0.0
        self.count = 0

    def observe(self, value: float) -> None:
        self.sum += value
        self.count += 1
        placed = False
        for bucket in self.buckets:
            if value <= bucket:
                self.counts[bucket] += 1
                placed = True
                break
        if not placed:
            self.inf_count += 1


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._histograms: dict[str, _Histogram] = {}

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] += value

    def observe(self, name: str, value: float, **labels: str) -> None:
        hist_key = name + "|" + ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        with self._lock:
            if hist_key not in self._histograms:
                self._histograms[hist_key] = _Histogram(
                    (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
                )
            self._histograms[hist_key].observe(value)

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            counter_names = {name for name, _ in self._counters}
            for name in sorted(counter_names):
                lines.append(f"# TYPE {name} counter")
                for (metric_name, labels), value in sorted(self._counters.items()):
                    if metric_name != name:
                        continue
                    label_str = _format_labels(labels)
                    lines.append(f"{name}{label_str} {value}")

            hist_base_names = {k.split("|", 1)[0] for k in self._histograms}
            for base_name in sorted(hist_base_names):
                lines.append(f"# TYPE {base_name} histogram")
                for hist_key, hist in sorted(self._histograms.items()):
                    if not hist_key.startswith(base_name + "|"):
                        continue
                    label_part = hist_key[len(base_name) + 1 :]
                    labels = _parse_labels(label_part)
                    label_str = _format_labels(labels)
                    cumulative = 0
                    for bucket in hist.buckets:
                        cumulative += hist.counts[bucket]
                        le = _format_float(bucket)
                        lines.append(f'{base_name}_bucket{label_str},le="{le}" {cumulative}')
                    cumulative += hist.inf_count
                    lines.append(f'{base_name}_bucket{label_str},le="+Inf" {cumulative}')
                    lines.append(f"{base_name}_sum{label_str} {hist.sum}")
                    lines.append(f"{base_name}_count{label_str} {hist.count}")
        return "\n".join(lines) + "\n"


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{v}"' for k, v in labels)
    return "{" + inner + "}"


def _parse_labels(raw: str) -> tuple[tuple[str, str], ...]:
    if not raw:
        return ()
    pairs: list[tuple[str, str]] = []
    for part in raw.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            pairs.append((k, v))
    return tuple(pairs)


def _format_float(value: float) -> str:
    if value == math.inf:
        return "+Inf"
    text = f"{value:g}"
    return text


METRICS = MetricsRegistry()


def estimate_tokens(*texts: str) -> int:
    total_chars = sum(len(t) for t in texts if t)
    return max(1, total_chars // 4) if total_chars else 0


def record_chat_metrics(
    *,
    retrieval_seconds: float,
    generation_seconds: float,
    stream: bool,
    question: str,
    answer: str,
    context: str,
) -> None:
    METRICS.inc("rag_chat_total", stream="true" if stream else "false")
    METRICS.observe("rag_retrieval_seconds", retrieval_seconds)
    METRICS.observe("rag_generation_seconds", generation_seconds)
    tokens = estimate_tokens(question, context, answer)
    METRICS.inc("rag_tokens_estimated", value=float(tokens))


def record_feedback(rating: str) -> None:
    METRICS.inc("rag_feedback_total", rating=rating)
