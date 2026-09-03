#!/usr/bin/env python3
"""切分内在指标分析：块长分布、空块率、边界质量。

不调用 Embedding / LLM，纯文本切分统计，用于调 chunk_size 前的快速体检。
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import SAMPLE_DOCS_DIR

BOUNDARY_PATTERN = re.compile(r"[。！？\n]$")


@dataclass
class DocumentStats:
    filename: str
    chunk_count: int
    avg_chunk_len: float
    std_chunk_len: float
    min_chunk_len: int
    max_chunk_len: int
    empty_chunk_count: int
    boundary_good_count: int
    boundary_good_rate: float


@dataclass
class AnalysisSummary:
    chunk_size: int
    chunk_overlap: int
    overlap_ratio: float
    document_count: int
    total_chunks: int
    avg_chunk_len: float
    std_chunk_len: float
    empty_chunk_rate: float
    boundary_good_rate: float
    chunks_per_doc_avg: float


def load_documents(docs_dir: Path) -> list[Document]:
    docs: list[Document] = []
    for path in sorted(docs_dir.glob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".markdown", ".txt"}:
            continue
        loader = TextLoader(str(path), encoding="utf-8")
        loaded = loader.load()
        for doc in loaded:
            doc.metadata["filename"] = path.name
        docs.extend(loaded)
    if not docs:
        raise FileNotFoundError(f"未在 {docs_dir} 找到可加载的文档")
    return docs


def is_boundary_good(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if len(stripped) < 50:
        return True
    return bool(BOUNDARY_PATTERN.search(stripped))


def analyze_document(filename: str, chunks: list[Document]) -> DocumentStats:
    lengths = [len(c.page_content) for c in chunks]
    empty_count = sum(1 for c in chunks if not c.page_content.strip())
    boundary_good = sum(1 for c in chunks if is_boundary_good(c.page_content))

    if lengths:
        avg_len = statistics.mean(lengths)
        std_len = statistics.pstdev(lengths) if len(lengths) > 1 else 0.0
        min_len = min(lengths)
        max_len = max(lengths)
    else:
        avg_len = std_len = 0.0
        min_len = max_len = 0

    n = len(chunks) or 1
    return DocumentStats(
        filename=filename,
        chunk_count=len(chunks),
        avg_chunk_len=avg_len,
        std_chunk_len=std_len,
        min_chunk_len=min_len,
        max_chunk_len=max_len,
        empty_chunk_count=empty_count,
        boundary_good_count=boundary_good,
        boundary_good_rate=boundary_good / n,
    )


def run_analysis(
    docs_dir: Path,
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[AnalysisSummary, list[DocumentStats]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    source_docs = load_documents(docs_dir)

    per_doc: list[DocumentStats] = []
    all_chunks: list[Document] = []

    for doc in source_docs:
        filename = str(doc.metadata.get("filename", "unknown"))
        pieces = splitter.split_documents([doc])
        per_doc.append(analyze_document(filename, pieces))
        all_chunks.extend(pieces)

    lengths = [len(c.page_content) for c in all_chunks]
    empty_count = sum(1 for c in all_chunks if not c.page_content.strip())
    boundary_good = sum(1 for c in all_chunks if is_boundary_good(c.page_content))
    total = len(all_chunks) or 1

    summary = AnalysisSummary(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        overlap_ratio=chunk_overlap / chunk_size if chunk_size else 0.0,
        document_count=len(source_docs),
        total_chunks=len(all_chunks),
        avg_chunk_len=statistics.mean(lengths) if lengths else 0.0,
        std_chunk_len=statistics.pstdev(lengths) if len(lengths) > 1 else 0.0,
        empty_chunk_rate=empty_count / total,
        boundary_good_rate=boundary_good / total,
        chunks_per_doc_avg=len(all_chunks) / len(source_docs) if source_docs else 0.0,
    )
    return summary, per_doc


def print_report(summary: AnalysisSummary, per_doc: list[DocumentStats], verbose: bool) -> None:
    print()
    print("=" * 72)
    print("切分内在指标分析")
    print("=" * 72)
    print(
        f"chunk_size={summary.chunk_size}, overlap={summary.chunk_overlap} "
        f"(ratio={summary.overlap_ratio:.1%})"
    )
    print(f"文档数: {summary.document_count}, 总块数: {summary.total_chunks}")
    print(f"平均块长: {summary.avg_chunk_len:.1f} ± {summary.std_chunk_len:.1f}")
    print(f"空块率: {summary.empty_chunk_rate:.1%}")
    print(f"边界良好率: {summary.boundary_good_rate:.1%}")
    print(f"平均每文档块数: {summary.chunks_per_doc_avg:.1f}")
    print("-" * 72)
    print(f"{'filename':<28} {'chunks':>6} {'avg_len':>8} {'boundary':>9}")
    for doc in per_doc:
        print(
            f"{doc.filename:<28} {doc.chunk_count:>6} "
            f"{doc.avg_chunk_len:>8.0f} {doc.boundary_good_rate:>8.0%}"
        )
    if verbose:
        print("-" * 72)
        for doc in per_doc:
            print(f"\n[{doc.filename}] min={doc.min_chunk_len}, max={doc.max_chunk_len}")
    print()


def write_json(path: Path, summary: AnalysisSummary, per_doc: list[DocumentStats]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "summary": asdict(summary),
        "per_document": [asdict(d) for d in per_doc],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="分析文档切分的内在指标")
    parser.add_argument("--chunk-size", type=int, default=512, help="chunk_size，默认 512")
    parser.add_argument("--chunk-overlap", type=int, default=64, help="chunk_overlap，默认 64")
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=SAMPLE_DOCS_DIR,
        help="待分析文档目录，默认 sample-docs",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "eval",
        help="报告输出目录，默认 data/eval",
    )
    parser.add_argument("--verbose", action="store_true", help="打印每文档 min/max 块长")
    args = parser.parse_args()

    summary, per_doc = run_analysis(args.docs_dir, args.chunk_size, args.chunk_overlap)
    print_report(summary, per_doc, args.verbose)

    out_path = args.output_dir / "chunk_analysis.json"
    write_json(out_path, summary, per_doc)
    print(f"报告已写入: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
