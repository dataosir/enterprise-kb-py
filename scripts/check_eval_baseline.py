#!/usr/bin/env python3
"""对比 L1/L2 评测结果与 baseline.json，用于 CI 门禁与上线前回归。

读取:
  - data/eval/chunk_analysis.json  (L1)
  - data/benchmark/benchmark_rag_params.json  (L2)

用法:
  python scripts/check_eval_baseline.py
  python scripts/check_eval_baseline.py --update-baseline  # 用当前结果更新基线
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = ROOT / "data" / "eval" / "baseline.json"
CHUNK_REPORT = ROOT / "data" / "eval" / "chunk_analysis.json"
BENCHMARK_REPORT = ROOT / "data" / "benchmark" / "benchmark_rag_params.json"
L3_REPORT = ROOT / "data" / "eval" / "eval_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"未找到报告: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def find_l2_result(report: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
    for row in report.get("results", []):
        if (
            row.get("retrieval_mode") == config["retrieval_mode"]
            and row.get("chunk_size") == config["chunk_size"]
            and row.get("chunk_overlap") == config["chunk_overlap"]
            and row.get("top_k") == config["top_k"]
        ):
            return row
    return None


def check_l1(summary: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = baseline["l1_chunk"]

    if summary.get("chunk_size") != expected["chunk_size"]:
        errors.append(
            f"L1 chunk_size 不匹配: 报告={summary.get('chunk_size')}, "
            f"基线={expected['chunk_size']}"
        )
    if summary.get("chunk_overlap") != expected["chunk_overlap"]:
        errors.append(
            f"L1 chunk_overlap 不匹配: 报告={summary.get('chunk_overlap')}, "
            f"基线={expected['chunk_overlap']}"
        )

    empty_rate = float(summary.get("empty_chunk_rate", 1.0))
    if empty_rate > float(expected["max_empty_chunk_rate"]):
        errors.append(
            f"L1 空块率过高: {empty_rate:.1%} > 基线 {expected['max_empty_chunk_rate']:.1%}"
        )

    boundary_rate = float(summary.get("boundary_good_rate", 0.0))
    if boundary_rate < float(expected["min_boundary_good_rate"]):
        errors.append(
            f"L1 边界良好率过低: {boundary_rate:.1%} < 基线 "
            f"{expected['min_boundary_good_rate']:.1%}"
        )
    return errors


def check_l2(row: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = baseline["l2_retrieval"]

    hit1 = float(row.get("hit_at_1_rate", 0.0))
    if hit1 < float(expected["min_hit_at_1_rate"]):
        errors.append(
            f"L2 hit@1 过低: {hit1:.1%} < 基线 {expected['min_hit_at_1_rate']:.1%}"
        )

    hitk = float(row.get("hit_at_k_rate", 0.0))
    if hitk < float(expected["min_hit_at_k_rate"]):
        errors.append(
            f"L2 hit@k 过低: {hitk:.1%} < 基线 {expected['min_hit_at_k_rate']:.1%}"
        )

    mrr = float(row.get("mrr", 0.0))
    if mrr < float(expected["min_mrr"]):
        errors.append(f"L2 MRR 过低: {mrr:.3f} < 基线 {expected['min_mrr']:.3f}")

    avg_ms = float(row.get("avg_retrieval_ms", 0.0))
    max_avg = float(expected.get("max_avg_retrieval_ms", float("inf")))
    if avg_ms > max_avg:
        errors.append(f"L2 平均检索延迟过高: {avg_ms:.0f}ms > 基线 {max_avg:.0f}ms")

    p95_ms = float(row.get("p95_retrieval_ms", 0.0))
    max_p95 = float(expected.get("max_p95_retrieval_ms", float("inf")))
    if p95_ms > max_p95:
        errors.append(f"L2 P95 检索延迟过高: {p95_ms:.0f}ms > 基线 {max_p95:.0f}ms")

    return errors


def check_l3(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    l3_cfg = baseline.get("l3_generation", {})
    if not l3_cfg.get("enabled"):
        return []

    errors: list[str] = []
    summary = report.get("summary", {})

    faith = summary.get("avg_faithfulness")
    min_faith = l3_cfg.get("min_faithfulness")
    if faith is not None and min_faith is not None and float(faith) < float(min_faith):
        errors.append(f"L3 faithfulness 过低: {float(faith):.3f} < 基线 {float(min_faith):.3f}")

    relevancy = summary.get("avg_answer_relevancy")
    min_rel = l3_cfg.get("min_answer_relevancy")
    if relevancy is not None and min_rel is not None and float(relevancy) < float(min_rel):
        errors.append(
            f"L3 answer_relevancy 过低: {float(relevancy):.3f} < 基线 {float(min_rel):.3f}"
        )
    return errors


def update_baseline_from_reports(
    baseline_path: Path,
    chunk_report: Path,
    benchmark_report: Path,
) -> dict[str, Any]:
    chunk_data = load_json(chunk_report)
    bench_data = load_json(benchmark_report)
    baseline = load_json(baseline_path)

    summary = chunk_data["summary"]
    config = baseline["l2_retrieval"]["config"]
    l2_row = find_l2_result(bench_data, config)
    if l2_row is None:
        raise ValueError(f"benchmark 报告中未找到配置: {config}")

    baseline["updated_at"] = date.today().isoformat()
    baseline["l1_chunk"]["max_empty_chunk_rate"] = float(summary["empty_chunk_rate"])
    baseline["l1_chunk"]["min_boundary_good_rate"] = float(summary["boundary_good_rate"])
    baseline["l2_retrieval"]["min_hit_at_1_rate"] = float(l2_row["hit_at_1_rate"])
    baseline["l2_retrieval"]["min_hit_at_k_rate"] = float(l2_row["hit_at_k_rate"])
    baseline["l2_retrieval"]["min_mrr"] = float(l2_row["mrr"])
    baseline["l2_retrieval"]["max_avg_retrieval_ms"] = max(
        10000.0, float(l2_row.get("avg_retrieval_ms", 0.0)) * 2
    )
    baseline["l2_retrieval"]["max_p95_retrieval_ms"] = max(
        20000.0, float(l2_row.get("p95_retrieval_ms", 0.0)) * 2
    )
    return baseline


def print_summary(
    summary: dict[str, Any],
    l2_row: dict[str, Any],
    baseline: dict[str, Any],
    errors: list[str],
) -> None:
    print()
    print("=" * 72)
    print("评测基线对比")
    print("=" * 72)
    l1 = baseline["l1_chunk"]
    l2 = baseline["l2_retrieval"]
    print(
        f"L1: empty_rate={summary['empty_chunk_rate']:.1%} "
        f"(max {l1['max_empty_chunk_rate']:.1%}), "
        f"boundary={summary['boundary_good_rate']:.1%} "
        f"(min {l1['min_boundary_good_rate']:.1%})"
    )
    print(
        f"L2 [{l2['config']['retrieval_mode']} c{l2['config']['chunk_size']} "
        f"k{l2['config']['top_k']}]: "
        f"hit@1={l2_row['hit_at_1_rate']:.1%} (min {l2['min_hit_at_1_rate']:.1%}), "
        f"hit@k={l2_row['hit_at_k_rate']:.1%} (min {l2['min_hit_at_k_rate']:.1%}), "
        f"mrr={l2_row['mrr']:.3f} (min {l2['min_mrr']:.3f}), "
        f"ret_ms={l2_row.get('avg_retrieval_ms', 0):.0f}"
    )
    if errors:
        print("-" * 72)
        for err in errors:
            print(f"FAIL: {err}")
        print("=" * 72)
        print(f"共 {len(errors)} 项未达基线")
    else:
        print("-" * 72)
        print("PASS: 全部指标达到基线")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="对比评测结果与 baseline.json")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="基线文件路径",
    )
    parser.add_argument(
        "--chunk-report",
        type=Path,
        default=CHUNK_REPORT,
        help="L1 切分报告",
    )
    parser.add_argument(
        "--benchmark-report",
        type=Path,
        default=BENCHMARK_REPORT,
        help="L2 benchmark 报告",
    )
    parser.add_argument(
        "--l3-report",
        type=Path,
        default=L3_REPORT,
        help="L3 eval_report.json（l3_generation.enabled=true 时检查）",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="用当前报告更新 baseline.json（收紧阈值到当前实测值）",
    )
    args = parser.parse_args()

    if args.update_baseline:
        updated = update_baseline_from_reports(
            args.baseline, args.chunk_report, args.benchmark_report
        )
        args.baseline.write_text(
            json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"已更新基线: {args.baseline}")
        return 0

    baseline = load_json(args.baseline)
    chunk_data = load_json(args.chunk_report)
    bench_data = load_json(args.benchmark_report)

    summary = chunk_data["summary"]
    l2_config = baseline["l2_retrieval"]["config"]
    l2_row = find_l2_result(bench_data, l2_config)
    if l2_row is None:
        print(f"ERROR: benchmark 中未找到配置 {l2_config}", file=sys.stderr)
        return 1

    errors = check_l1(summary, baseline) + check_l2(l2_row, baseline)
    if baseline.get("l3_generation", {}).get("enabled") and args.l3_report.exists():
        l3_data = load_json(args.l3_report)
        errors.extend(check_l3(l3_data, baseline))
    elif baseline.get("l3_generation", {}).get("enabled"):
        errors.append(f"L3 已启用但未找到报告: {args.l3_report}")

    print_summary(summary, l2_row, baseline, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
