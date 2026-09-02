#!/usr/bin/env python3
"""RAG 调参对比：在 sample-docs 上批量测试不同 chunk_size / top_k 的检索效果。

不调用 LLM，只测入库切分与向量检索，适合本地快速对比参数。
每次运行在独立临时目录建库，不影响 data/chroma 生产数据。
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import (
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    SAMPLE_DOCS_DIR,
)

# 默认评测问题：question + 期望命中的 sample-docs 文件名
DEFAULT_CASES: list[dict[str, str]] = [
    {"question": "退款多久到账？", "expected_filename": "refund-policy.md"},
    {"question": "购买后几天内可以全额退款？", "expected_filename": "refund-policy.md"},
    {"question": "远程办公考勤怎么打卡？", "expected_filename": "remote-work-policy.md"},
    {"question": "VPN 连不上怎么办？", "expected_filename": "it-faq.md"},
    {"question": "忘记公司邮箱密码怎么办？", "expected_filename": "it-faq.md"},
]


@dataclass
class CaseResult:
    question: str
    expected_filename: str
    hit_at_1: bool
    hit_at_k: bool
    top_filename: str
    top_score: float
    context_chars: int
    retrieved_files: list[str] = field(default_factory=list)


@dataclass
class ConfigResult:
    chunk_size: int
    chunk_overlap: int
    top_k: int
    total_chunks: int
    ingest_seconds: float
    hit_at_1_rate: float
    hit_at_k_rate: float
    avg_top_score: float
    avg_context_chars: float
    case_results: list[CaseResult]


def parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def load_embeddings() -> Any:
    if EMBEDDING_PROVIDER == "openai":
        kwargs: dict[str, Any] = {"model": EMBEDDING_MODEL, "api_key": OPENAI_API_KEY}
        if OPENAI_BASE_URL:
            kwargs["base_url"] = OPENAI_BASE_URL
        return OpenAIEmbeddings(**kwargs)
    return HuggingFaceEmbeddings(
        model_name=LOCAL_EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def load_sample_documents() -> list[Document]:
    docs: list[Document] = []
    for path in sorted(SAMPLE_DOCS_DIR.glob("*")):
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
        raise FileNotFoundError(f"未在 {SAMPLE_DOCS_DIR} 找到可加载的示例文档")
    return docs


def build_vectorstore(
    embeddings: Any,
    persist_dir: Path,
    collection_name: str,
    chunk_size: int,
    chunk_overlap: int,
    source_docs: list[Document],
) -> tuple[Chroma, int, float]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks: list[Document] = []
    for doc in source_docs:
        for piece in splitter.split_documents([doc]):
            piece.metadata["filename"] = doc.metadata.get("filename", "unknown")
            chunks.append(piece)

    start = time.perf_counter()
    store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )
    if chunks:
        store.add_documents(chunks)
    elapsed = time.perf_counter() - start
    return store, len(chunks), elapsed


def evaluate_config(
    embeddings: Any,
    work_dir: Path,
    source_docs: list[Document],
    cases: list[dict[str, str]],
    chunk_size: int,
    chunk_overlap: int,
    top_k: int,
) -> ConfigResult:
    tag = f"c{chunk_size}_o{chunk_overlap}_k{top_k}"
    persist_dir = work_dir / tag
    persist_dir.mkdir(parents=True, exist_ok=True)

    store, total_chunks, ingest_seconds = build_vectorstore(
        embeddings,
        persist_dir,
        collection_name=f"bench_{tag}",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        source_docs=source_docs,
    )

    case_results: list[CaseResult] = []
    for case in cases:
        question = case["question"]
        expected = case["expected_filename"]
        hits = store.similarity_search_with_score(question, k=top_k)

        retrieved_files = [str(doc.metadata.get("filename", "unknown")) for doc, _ in hits]
        top_filename = retrieved_files[0] if retrieved_files else ""
        top_score = float(hits[0][1]) if hits else 0.0
        context_chars = sum(len(doc.page_content) for doc, _ in hits)

        case_results.append(
            CaseResult(
                question=question,
                expected_filename=expected,
                hit_at_1=top_filename == expected,
                hit_at_k=expected in retrieved_files,
                top_filename=top_filename,
                top_score=top_score,
                context_chars=context_chars,
                retrieved_files=retrieved_files,
            )
        )

    n = len(case_results)
    hit_at_1_rate = sum(c.hit_at_1 for c in case_results) / n
    hit_at_k_rate = sum(c.hit_at_k for c in case_results) / n
    avg_top_score = sum(c.top_score for c in case_results) / n
    avg_context_chars = sum(c.context_chars for c in case_results) / n

    return ConfigResult(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        top_k=top_k,
        total_chunks=total_chunks,
        ingest_seconds=ingest_seconds,
        hit_at_1_rate=hit_at_1_rate,
        hit_at_k_rate=hit_at_k_rate,
        avg_top_score=avg_top_score,
        avg_context_chars=avg_context_chars,
        case_results=case_results,
    )


def print_summary(results: list[ConfigResult]) -> None:
    print()
    print("=" * 88)
    print("RAG 调参对比结果（sample-docs 检索评测，未调用 LLM）")
    print("=" * 88)
    header = (
        f"{'chunk':>6} {'overlap':>7} {'top_k':>5} "
        f"{'chunks':>6} {'ingest_s':>8} {'hit@1':>6} {'hit@k':>6} "
        f"{'avg_score':>9} {'ctx_chars':>9}"
    )
    print(header)
    print("-" * 88)
    for r in sorted(results, key=lambda x: (-x.hit_at_k_rate, -x.hit_at_1_rate, x.avg_top_score)):
        print(
            f"{r.chunk_size:>6} {r.chunk_overlap:>7} {r.top_k:>5} "
            f"{r.total_chunks:>6} {r.ingest_seconds:>8.2f} "
            f"{r.hit_at_1_rate:>6.0%} {r.hit_at_k_rate:>6.0%} "
            f"{r.avg_top_score:>9.4f} {r.avg_context_chars:>9.0f}"
        )
    print("-" * 88)
    best = max(results, key=lambda x: (x.hit_at_k_rate, x.hit_at_1_rate, -x.avg_top_score))
    print(
        f"推荐组合（hit@k 优先）: chunk_size={best.chunk_size}, "
        f"chunk_overlap={best.chunk_overlap}, top_k={best.top_k}"
    )
    print("说明: hit@1 = Top1 命中期望文档; hit@k = Top-K 内命中; score 越小通常越相似 (L2)")
    print()


def write_csv(path: Path, results: list[ConfigResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "chunk_size",
                "chunk_overlap",
                "top_k",
                "total_chunks",
                "ingest_seconds",
                "hit_at_1_rate",
                "hit_at_k_rate",
                "avg_top_score",
                "avg_context_chars",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r.chunk_size,
                    r.chunk_overlap,
                    r.top_k,
                    r.total_chunks,
                    f"{r.ingest_seconds:.3f}",
                    f"{r.hit_at_1_rate:.4f}",
                    f"{r.hit_at_k_rate:.4f}",
                    f"{r.avg_top_score:.4f}",
                    f"{r.avg_context_chars:.0f}",
                ]
            )


def write_json(path: Path, results: list[ConfigResult], cases: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cases": cases,
        "results": [
            {
                "chunk_size": r.chunk_size,
                "chunk_overlap": r.chunk_overlap,
                "top_k": r.top_k,
                "total_chunks": r.total_chunks,
                "ingest_seconds": r.ingest_seconds,
                "hit_at_1_rate": r.hit_at_1_rate,
                "hit_at_k_rate": r.hit_at_k_rate,
                "avg_top_score": r.avg_top_score,
                "avg_context_chars": r.avg_context_chars,
                "details": [
                    {
                        "question": c.question,
                        "expected_filename": c.expected_filename,
                        "hit_at_1": c.hit_at_1,
                        "hit_at_k": c.hit_at_k,
                        "top_filename": c.top_filename,
                        "top_score": c.top_score,
                        "context_chars": c.context_chars,
                        "retrieved_files": c.retrieved_files,
                    }
                    for c in r.case_results
                ],
            }
            for r in results
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="对比不同 RAG chunk_size / top_k 的检索效果")
    parser.add_argument(
        "--chunk-sizes",
        default="256,512,768",
        help="逗号分隔的 chunk_size 列表，默认 256,512,768",
    )
    parser.add_argument(
        "--top-k-values",
        default="2,4,6",
        help="逗号分隔的 top_k 列表，默认 2,4,6",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=64,
        help="chunk_overlap，默认 64（与 .env 一致）",
    )
    parser.add_argument(
        "--cases-file",
        type=Path,
        help="自定义评测 JSON 文件，格式 [{\"question\":\"...\", \"expected_filename\":\"...\"}]",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "benchmark",
        help="结果与临时向量库目录，默认 data/benchmark",
    )
    parser.add_argument("--no-csv", action="store_true", help="不写入 CSV")
    parser.add_argument("--verbose", action="store_true", help="打印每个问题的命中详情")
    args = parser.parse_args()

    chunk_sizes = parse_int_list(args.chunk_sizes)
    top_k_values = parse_int_list(args.top_k_values)
    cases = DEFAULT_CASES
    if args.cases_file:
        cases = json.loads(args.cases_file.read_text(encoding="utf-8"))

    work_dir = args.output_dir
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"加载 Embedding（provider={EMBEDDING_PROVIDER}）...")
    embeddings = load_embeddings()
    source_docs = load_sample_documents()
    print(f"示例文档 {len(source_docs)} 篇，评测问题 {len(cases)} 条")
    print(f"参数网格: chunk_sizes={chunk_sizes}, top_k={top_k_values}, overlap={args.chunk_overlap}")

    results: list[ConfigResult] = []
    total = len(chunk_sizes) * len(top_k_values)
    idx = 0
    for chunk_size in chunk_sizes:
        for top_k in top_k_values:
            idx += 1
            print(f"[{idx}/{total}] chunk={chunk_size}, top_k={top_k} ...", flush=True)
            result = evaluate_config(
                embeddings,
                work_dir,
                source_docs,
                cases,
                chunk_size=chunk_size,
                chunk_overlap=args.chunk_overlap,
                top_k=top_k,
            )
            results.append(result)
            if args.verbose:
                for c in result.case_results:
                    mark = "OK" if c.hit_at_k else "MISS"
                    print(f"  [{mark}] {c.question} -> top1={c.top_filename} (expect {c.expected_filename})")

    print_summary(results)

    if not args.no_csv:
        write_csv(work_dir / "benchmark_rag_params.csv", results)
        write_json(work_dir / "benchmark_rag_params.json", results, cases)
        print(f"结果已写入: {work_dir / 'benchmark_rag_params.csv'}")
        print(f"详情已写入: {work_dir / 'benchmark_rag_params.json'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
