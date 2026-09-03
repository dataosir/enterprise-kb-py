"""聚合 L1–L4 离线评测报告、基线门禁与运行时 /metrics，供评测看板使用。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import BASE_DIR
from app.observability.metrics import METRICS

CHUNK_REPORT = BASE_DIR / "data" / "eval" / "chunk_analysis.json"
BENCHMARK_REPORT = BASE_DIR / "data" / "benchmark" / "benchmark_rag_params.json"
L3_REPORT = BASE_DIR / "data" / "eval" / "eval_report.json"
BASELINE_FILE = BASE_DIR / "data" / "eval" / "baseline.json"
FEEDBACK_FILE = BASE_DIR / "data" / "eval" / "feedback.jsonl"
BAD_CASES_FILE = BASE_DIR / "data" / "eval" / "bad_cases_candidates.json"
BENCHMARK_CASES = BASE_DIR / "scripts" / "benchmark_cases.json"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _find_l2_result(report: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
    for row in report.get("results", []):
        if (
            row.get("retrieval_mode") == config["retrieval_mode"]
            and row.get("chunk_size") == config["chunk_size"]
            and row.get("chunk_overlap") == config["chunk_overlap"]
            and row.get("top_k") == config["top_k"]
        ):
            return row
    return None


def _metric_status(value: float | None, threshold: float, higher_is_better: bool) -> str:
    if value is None:
        return "missing"
    if higher_is_better:
        return "pass" if value >= threshold else "fail"
    return "pass" if value <= threshold else "fail"


def _check_l1(summary: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    cfg = baseline.get("l1_chunk", {})
    empty_rate = float(summary.get("empty_chunk_rate", 1.0))
    boundary_rate = float(summary.get("boundary_good_rate", 0.0))
    max_empty = float(cfg.get("max_empty_chunk_rate", 0.0))
    min_boundary = float(cfg.get("min_boundary_good_rate", 0.0))

    checks = [
        {
            "id": "empty_chunk_rate",
            "label": "空块率",
            "value": empty_rate,
            "threshold": max_empty,
            "unit": "ratio",
            "higher_is_better": False,
            "status": _metric_status(empty_rate, max_empty, False),
        },
        {
            "id": "boundary_good_rate",
            "label": "边界良好率",
            "value": boundary_rate,
            "threshold": min_boundary,
            "unit": "ratio",
            "higher_is_better": True,
            "status": _metric_status(boundary_rate, min_boundary, True),
        },
    ]
    return {
        "layer": "L1",
        "title": "切分质量",
        "tool": "analyze_chunks.py",
        "report_path": str(CHUNK_REPORT.relative_to(BASE_DIR)),
        "summary": summary,
        "checks": checks,
        "pass": all(c["status"] == "pass" for c in checks),
    }


def _check_l2(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    cfg = baseline.get("l2_retrieval", {})
    checks = [
        {
            "id": "hit_at_1_rate",
            "label": "Hit@1",
            "value": float(row.get("hit_at_1_rate", 0.0)),
            "threshold": float(cfg.get("min_hit_at_1_rate", 0.0)),
            "unit": "ratio",
            "higher_is_better": True,
            "status": _metric_status(
                float(row.get("hit_at_1_rate", 0.0)),
                float(cfg.get("min_hit_at_1_rate", 0.0)),
                True,
            ),
        },
        {
            "id": "hit_at_k_rate",
            "label": "Hit@K",
            "value": float(row.get("hit_at_k_rate", 0.0)),
            "threshold": float(cfg.get("min_hit_at_k_rate", 0.0)),
            "unit": "ratio",
            "higher_is_better": True,
            "status": _metric_status(
                float(row.get("hit_at_k_rate", 0.0)),
                float(cfg.get("min_hit_at_k_rate", 0.0)),
                True,
            ),
        },
        {
            "id": "mrr",
            "label": "MRR",
            "value": float(row.get("mrr", 0.0)),
            "threshold": float(cfg.get("min_mrr", 0.0)),
            "unit": "score",
            "higher_is_better": True,
            "status": _metric_status(
                float(row.get("mrr", 0.0)),
                float(cfg.get("min_mrr", 0.0)),
                True,
            ),
        },
        {
            "id": "avg_retrieval_ms",
            "label": "检索延迟 P50",
            "value": float(row.get("avg_retrieval_ms", 0.0)),
            "threshold": float(cfg.get("max_avg_retrieval_ms", float("inf"))),
            "unit": "ms",
            "higher_is_better": False,
            "status": _metric_status(
                float(row.get("avg_retrieval_ms", 0.0)),
                float(cfg.get("max_avg_retrieval_ms", float("inf"))),
                False,
            ),
        },
        {
            "id": "p95_retrieval_ms",
            "label": "检索延迟 P95",
            "value": float(row.get("p95_retrieval_ms", 0.0)),
            "threshold": float(cfg.get("max_p95_retrieval_ms", float("inf"))),
            "unit": "ms",
            "higher_is_better": False,
            "status": _metric_status(
                float(row.get("p95_retrieval_ms", 0.0)),
                float(cfg.get("max_p95_retrieval_ms", float("inf"))),
                False,
            ),
        },
    ]
    return {
        "layer": "L2",
        "title": "检索质量",
        "tool": "benchmark_rag_params.py",
        "report_path": str(BENCHMARK_REPORT.relative_to(BASE_DIR)),
        "config": cfg.get("config", {}),
        "summary": row,
        "checks": checks,
        "pass": all(c["status"] == "pass" for c in checks),
    }


def _check_l3(report: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    cfg = baseline.get("l3_generation", {})
    enabled = bool(cfg.get("enabled"))
    summary = report.get("summary", {})
    faith = summary.get("avg_faithfulness")
    relevancy = summary.get("avg_answer_relevancy")

    checks = [
        {
            "id": "faithfulness",
            "label": "Faithfulness",
            "value": float(faith) if faith is not None else None,
            "threshold": float(cfg.get("min_faithfulness", 0.8)),
            "unit": "score",
            "higher_is_better": True,
            "status": (
                "skip"
                if not enabled
                else _metric_status(
                    float(faith) if faith is not None else None,
                    float(cfg.get("min_faithfulness", 0.8)),
                    True,
                )
            ),
        },
        {
            "id": "answer_relevancy",
            "label": "Answer Relevancy",
            "value": float(relevancy) if relevancy is not None else None,
            "threshold": float(cfg.get("min_answer_relevancy", 0.7)),
            "unit": "score",
            "higher_is_better": True,
            "status": (
                "skip"
                if not enabled
                else _metric_status(
                    float(relevancy) if relevancy is not None else None,
                    float(cfg.get("min_answer_relevancy", 0.7)),
                    True,
                )
            ),
        },
        {
            "id": "avg_generation_ms",
            "label": "生成延迟",
            "value": float(summary.get("avg_generation_ms", 0.0)),
            "threshold": None,
            "unit": "ms",
            "higher_is_better": False,
            "status": "info",
        },
    ]
    active_checks = [c for c in checks if c["status"] not in {"skip", "info"}]
    return {
        "layer": "L3",
        "title": "生成质量",
        "tool": "eval_ragas.py",
        "report_path": str(L3_REPORT.relative_to(BASE_DIR)),
        "enabled_in_baseline": enabled,
        "summary": summary,
        "checks": checks,
        "pass": enabled and active_checks and all(c["status"] == "pass" for c in active_checks),
    }


def _summarize_l4(feedback_rows: list[dict[str, Any]], bad_cases: dict[str, Any] | None) -> dict[str, Any]:
    up = sum(1 for r in feedback_rows if r.get("rating") == "up")
    down = sum(1 for r in feedback_rows if r.get("rating") == "down")
    total = len(feedback_rows)
    down_rate = down / total if total else None
    return {
        "layer": "L4",
        "title": "业务反馈",
        "tool": "/api/feedback + export_bad_cases.py",
        "report_path": str(FEEDBACK_FILE.relative_to(BASE_DIR)),
        "summary": {
            "feedback_total": total,
            "thumbs_up": up,
            "thumbs_down": down,
            "down_rate": down_rate,
            "bad_case_candidates": len((bad_cases or {}).get("candidates", [])),
        },
        "checks": [
            {
                "id": "feedback_total",
                "label": "反馈总数",
                "value": float(total),
                "threshold": None,
                "unit": "count",
                "higher_is_better": True,
                "status": "info",
            },
            {
                "id": "thumbs_down",
                "label": "差评数",
                "value": float(down),
                "threshold": None,
                "unit": "count",
                "higher_is_better": False,
                "status": "info",
            },
        ],
        "pass": None,
    }


def parse_prometheus_text(text: str) -> dict[str, Any]:
    """将 METRICS.render() 文本解析为看板可用的摘要。"""
    counters: dict[str, float] = {}
    labeled_counters: dict[str, dict[str, float]] = {}
    histograms: dict[str, dict[str, float]] = {}

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{([^}]*)\})?\s+([^\s]+)$", line)
        if not match:
            continue
        name, _bracket, labels_raw, raw_value = match.group(1), match.group(2), match.group(3), match.group(4)
        try:
            value = float(raw_value)
        except ValueError:
            continue

        if name.endswith("_sum"):
            base = name[: -len("_sum")]
            histograms.setdefault(base, {})["sum"] = value
        elif name.endswith("_count"):
            base = name[: -len("_count")]
            histograms.setdefault(base, {})["count"] = value
        elif name.endswith("_bucket"):
            continue
        elif labels_raw:
            label_map = dict(re.findall(r'(\w+)="([^"]*)"', labels_raw))
            labeled_counters.setdefault(name, {})[json.dumps(label_map, sort_keys=True)] = value
        else:
            counters[name] = counters.get(name, 0.0) + value

    feedback_up = 0.0
    feedback_down = 0.0
    for labels_json, value in labeled_counters.get("rag_feedback_total", {}).items():
        labels = json.loads(labels_json)
        if labels.get("rating") == "up":
            feedback_up += value
        elif labels.get("rating") == "down":
            feedback_down += value

    runtime: dict[str, Any] = {
        "counters": counters,
        "labeled_counters": labeled_counters,
        "feedback_up": feedback_up,
        "feedback_down": feedback_down,
        "histograms": {},
    }
    for name, hist in histograms.items():
        count = hist.get("count", 0.0)
        total_sum = hist.get("sum", 0.0)
        runtime["histograms"][name] = {
            "count": count,
            "sum": total_sum,
            "avg": total_sum / count if count else 0.0,
        }
    return runtime


def build_influence_graph() -> dict[str, Any]:
    """指标影响关系图（思维导图数据源）。"""
    return {
        "root": {
            "id": "system_quality",
            "label": "系统整体质量",
            "type": "outcome",
        },
        "nodes": [
            {"id": "chunk_size", "label": "chunk_size", "type": "knob", "group": "L1"},
            {"id": "chunk_overlap", "label": "chunk_overlap", "type": "knob", "group": "L1"},
            {"id": "top_k", "label": "top_k", "type": "knob", "group": "L2"},
            {"id": "fetch_k", "label": "fetch_k", "type": "knob", "group": "L2"},
            {"id": "retrieval_mode", "label": "retrieval_mode", "type": "knob", "group": "L2"},
            {"id": "hybrid_alpha", "label": "hybrid_alpha", "type": "knob", "group": "L2"},
            {"id": "use_rerank", "label": "use_rerank", "type": "knob", "group": "L2"},
            {"id": "use_mmr", "label": "use_mmr", "type": "knob", "group": "L2"},
            {"id": "score_threshold", "label": "score_threshold", "type": "knob", "group": "L2"},
            {"id": "temperature", "label": "temperature", "type": "knob", "group": "L3"},
            {"id": "system_prompt", "label": "system_prompt", "type": "knob", "group": "L3"},
            {"id": "l1_empty", "label": "空块率", "type": "metric", "group": "L1"},
            {"id": "l1_boundary", "label": "边界质量", "type": "metric", "group": "L1"},
            {"id": "l1_chunks_per_doc", "label": "块数/文档", "type": "metric", "group": "L1"},
            {"id": "l2_hit1", "label": "Hit@1", "type": "metric", "group": "L2"},
            {"id": "l2_hitk", "label": "Hit@K", "type": "metric", "group": "L2"},
            {"id": "l2_mrr", "label": "MRR", "type": "metric", "group": "L2"},
            {"id": "l2_retrieval_ms", "label": "检索延迟", "type": "metric", "group": "L2"},
            {"id": "l3_faith", "label": "Faithfulness", "type": "metric", "group": "L3"},
            {"id": "l3_relevancy", "label": "Answer Relevancy", "type": "metric", "group": "L3"},
            {"id": "l3_gen_ms", "label": "生成延迟", "type": "metric", "group": "L3"},
            {"id": "l4_feedback", "label": "用户反馈", "type": "metric", "group": "L4"},
            {"id": "l4_bad_cases", "label": "差评回流", "type": "metric", "group": "L4"},
            {"id": "gate_baseline", "label": "基线门禁", "type": "gate", "group": "ops"},
            {"id": "gate_ci", "label": "CI eval-smoke", "type": "gate", "group": "ops"},
            {"id": "ops_metrics", "label": "/metrics", "type": "gate", "group": "ops"},
        ],
        "edges": [
            {"from": "chunk_size", "to": "l1_empty", "effect": "过大/过小易空块或截断"},
            {"from": "chunk_overlap", "to": "l1_boundary", "effect": "提高重叠改善边界"},
            {"from": "chunk_size", "to": "l1_chunks_per_doc", "effect": "块越大块数越少"},
            {"from": "l1_empty", "to": "l2_hitk", "effect": "空块降低召回"},
            {"from": "l1_boundary", "to": "l2_hit1", "effect": "差边界影响 Top1"},
            {"from": "top_k", "to": "l2_hitk", "effect": "增大 K 提高召回"},
            {"from": "top_k", "to": "l2_retrieval_ms", "effect": "上下文变长略增延迟"},
            {"from": "fetch_k", "to": "l2_hitk", "effect": "扩大候选池"},
            {"from": "fetch_k", "to": "l2_mrr", "effect": "为 rerank 提供更多候选"},
            {"from": "retrieval_mode", "to": "l2_hit1", "effect": "hybrid 利于 keyword"},
            {"from": "hybrid_alpha", "to": "l2_mrr", "effect": "向量/BM25 权重"},
            {"from": "use_rerank", "to": "l2_mrr", "effect": "精排提升排名"},
            {"from": "use_rerank", "to": "l2_retrieval_ms", "effect": "显著增加延迟"},
            {"from": "use_mmr", "to": "l2_hitk", "effect": "去重可能牺牲召回"},
            {"from": "score_threshold", "to": "l2_hitk", "effect": "过高导致空检索"},
            {"from": "l2_hitk", "to": "l3_faith", "effect": "检索差则易幻觉"},
            {"from": "l2_hit1", "to": "l3_relevancy", "effect": "Top1 错则答非所问"},
            {"from": "temperature", "to": "l3_faith", "effect": "高温增加幻觉"},
            {"from": "system_prompt", "to": "l3_faith", "effect": "约束引用与拒答"},
            {"from": "system_prompt", "to": "l3_relevancy", "effect": "引导回答结构"},
            {"from": "l3_faith", "to": "system_quality", "effect": "可信度"},
            {"from": "l3_relevancy", "to": "system_quality", "effect": "有用性"},
            {"from": "l2_mrr", "to": "system_quality", "effect": "检索排名"},
            {"from": "l2_hitk", "to": "system_quality", "effect": "检索覆盖"},
            {"from": "l4_feedback", "to": "l4_bad_cases", "effect": "差评导出"},
            {"from": "l4_bad_cases", "to": "l2_hitk", "effect": "扩充用例回归"},
            {"from": "l1_empty", "to": "gate_baseline", "effect": "L1 门禁"},
            {"from": "l2_mrr", "to": "gate_baseline", "effect": "L2 门禁"},
            {"from": "gate_baseline", "to": "gate_ci", "effect": "PR 阻断"},
            {"from": "ops_metrics", "to": "l2_retrieval_ms", "effect": "线上 P50/P95"},
            {"from": "ops_metrics", "to": "l3_gen_ms", "effect": "线上生成耗时"},
            {"from": "l4_feedback", "to": "system_quality", "effect": "用户满意度"},
        ],
        "layers": [
            {
                "id": "L1",
                "label": "L1 切分",
                "color": "#22c55e",
                "metrics": ["l1_empty", "l1_boundary", "l1_chunks_per_doc"],
            },
            {
                "id": "L2",
                "label": "L2 检索",
                "color": "#3b82f6",
                "metrics": ["l2_hit1", "l2_hitk", "l2_mrr", "l2_retrieval_ms"],
            },
            {
                "id": "L3",
                "label": "L3 生成",
                "color": "#a855f7",
                "metrics": ["l3_faith", "l3_relevancy", "l3_gen_ms"],
            },
            {
                "id": "L4",
                "label": "L4 业务",
                "color": "#f59e0b",
                "metrics": ["l4_feedback", "l4_bad_cases"],
            },
            {
                "id": "ops",
                "label": "运维门禁",
                "color": "#64748b",
                "metrics": ["gate_baseline", "gate_ci", "ops_metrics"],
            },
        ],
    }


def build_eval_dashboard() -> dict[str, Any]:
    baseline = _load_json(BASELINE_FILE) or {}
    chunk_data = _load_json(CHUNK_REPORT)
    bench_data = _load_json(BENCHMARK_REPORT)
    l3_data = _load_json(L3_REPORT)
    bad_cases = _load_json(BAD_CASES_FILE)
    cases_data = _load_json(BENCHMARK_CASES)
    feedback_rows = _load_jsonl(FEEDBACK_FILE)

    layers: list[dict[str, Any]] = []
    gate_errors: list[str] = []

    if chunk_data and baseline:
        l1 = _check_l1(chunk_data["summary"], baseline)
        layers.append(l1)
        if not l1["pass"]:
            gate_errors.append("L1 未达基线")
    else:
        layers.append(
            {
                "layer": "L1",
                "title": "切分质量",
                "missing": True,
                "message": "运行 make analyze-chunks 生成报告",
            }
        )
        gate_errors.append("缺少 L1 报告")

    l2_row = None
    if bench_data and baseline:
        l2_config = baseline.get("l2_retrieval", {}).get("config", {})
        l2_row = _find_l2_result(bench_data, l2_config)
        if l2_row:
            l2 = _check_l2(l2_row, baseline)
            layers.append(l2)
            if not l2["pass"]:
                gate_errors.append("L2 未达基线")
        else:
            layers.append(
                {
                    "layer": "L2",
                    "title": "检索质量",
                    "missing": True,
                    "message": f"benchmark 中无配置 {l2_config}",
                }
            )
            gate_errors.append("缺少 L2 基线配置结果")
    else:
        layers.append(
            {
                "layer": "L2",
                "title": "检索质量",
                "missing": True,
                "message": "运行 make benchmark 生成报告",
            }
        )
        gate_errors.append("缺少 L2 报告")

    if l3_data:
        layers.append(_check_l3(l3_data, baseline))
    else:
        layers.append(
            {
                "layer": "L3",
                "title": "生成质量",
                "missing": True,
                "message": "运行 eval_ragas.py --run 生成报告",
            }
        )

    layers.append(_summarize_l4(feedback_rows, bad_cases))

    benchmark_modes: list[dict[str, Any]] = []
    if bench_data:
        for row in bench_data.get("results", []):
            benchmark_modes.append(
                {
                    "retrieval_mode": row.get("retrieval_mode"),
                    "chunk_size": row.get("chunk_size"),
                    "top_k": row.get("top_k"),
                    "hit_at_1_rate": row.get("hit_at_1_rate"),
                    "hit_at_k_rate": row.get("hit_at_k_rate"),
                    "mrr": row.get("mrr"),
                    "avg_retrieval_ms": row.get("avg_retrieval_ms"),
                    "by_tag": row.get("by_tag", {}),
                }
            )

    if isinstance(cases_data, list):
        case_list = cases_data
    elif cases_data:
        case_list = cases_data.get("cases", [])
    else:
        case_list = []
    case_count = len(case_list)
    expected_answer_count = sum(1 for c in case_list if c.get("expected_answer"))

    runtime = parse_prometheus_text(METRICS.render())

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline": baseline,
        "gate": {
            "pass": len(gate_errors) == 0,
            "errors": gate_errors,
        },
        "layers": layers,
        "benchmark_modes": benchmark_modes,
        "benchmark_cases": {
            "total": case_count,
            "with_expected_answer": expected_answer_count,
        },
        "runtime_metrics": runtime,
        "influence_graph": build_influence_graph(),
        "commands": {
            "l1": "make analyze-chunks",
            "l2": "make benchmark",
            "l3": "eval_ragas.py --run --ragas",
            "gate": "make eval-smoke",
            "bad_cases": "make export-bad-cases",
        },
    }
