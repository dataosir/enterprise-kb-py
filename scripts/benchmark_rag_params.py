#!/usr/bin/env python3
"""RAG 调参对比：在 sample-docs 上批量测试不同 chunk_size / top_k / 检索模式。

不调用 LLM，只测入库切分与检索，适合本地快速对比参数。
每次运行在独立临时目录建库，不影响 data/chroma 生产数据。
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

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
    ES_URL,
    HYBRID_ALPHA,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    RRF_K,
    SAMPLE_DOCS_DIR,
)
from app.services.retrieval.es_store import ElasticsearchStore
from app.services.retrieval.hybrid import fuse_hybrid_results
from app.services.retrieval.reranker import Reranker

BENCHMARK_ES_PREFIX = "benchmark_rag"
CASES_FILE = ROOT / "scripts" / "benchmark_cases.json"

FALLBACK_CASES: list[dict[str, Any]] = [
    {"question": "退款多久到账？", "expected_filename": "refund-policy.md", "tags": ["semantic", "faq"]},
    {
        "question": "购买后几天内可以全额退款？",
        "expected_filename": "refund-policy.md",
        "tags": ["semantic"],
    },
    {
        "question": "远程办公考勤怎么打卡？",
        "expected_filename": "remote-work-policy.md",
        "tags": ["semantic"],
    },
    {"question": "VPN 连不上怎么办？", "expected_filename": "it-faq.md", "tags": ["semantic", "faq"]},
    {
        "question": "忘记公司邮箱密码怎么办？",
        "expected_filename": "it-faq.md",
        "tags": ["semantic", "faq"],
    },
]


def load_cases(cases_file: Path | None) -> list[dict[str, Any]]:
    path = cases_file or CASES_FILE
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return FALLBACK_CASES


@dataclass
class CaseResult:
    question: str
    expected_filename: str
    tags: list[str]
    hit_at_1: bool
    hit_at_k: bool
    reciprocal_rank: float
    first_hit_rank: int | None
    retrieval_ms: float
    top_filename: str
    top_score: float
    context_chars: int
    chunk_recall_at_k: float | None = None
    retrieved_files: list[str] = field(default_factory=list)
    retrieved_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class ConfigResult:
    retrieval_mode: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    fetch_k: int
    hybrid_alpha: float
    rrf_k: int
    total_chunks: int
    ingest_seconds: float
    hit_at_1_rate: float
    hit_at_k_rate: float
    mrr: float
    avg_retrieval_ms: float
    p95_retrieval_ms: float
    avg_top_score: float
    avg_context_chars: float
    avg_chunk_recall_at_k: float | None
    by_tag: dict[str, dict[str, float]]
    case_results: list[CaseResult]
    hybrid_fallback: bool = False


def parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


VALID_MODES = {"vector", "hybrid", "mmr", "rerank", "hybrid_rerank"}


def parse_mode_list(raw: str) -> list[str]:
    modes = [m.strip().lower() for m in raw.split(",") if m.strip()]
    unknown = set(modes) - VALID_MODES
    if unknown:
        raise ValueError(f"不支持的检索模式: {unknown}，支持: {sorted(VALID_MODES)}")
    return modes or ["vector"]


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


def assign_chunk_ids(chunks: list[Document]) -> None:
    """按文档内顺序分配稳定 chunk_id（filename#index），便于标注 expected_chunk_ids。"""
    counters: dict[str, int] = defaultdict(int)
    for chunk in chunks:
        filename = str(chunk.metadata.get("filename", "unknown"))
        chunk.metadata["chunk_id"] = f"{filename}#{counters[filename]}"
        counters[filename] += 1


def build_vectorstore(
    embeddings: Any,
    persist_dir: Path,
    collection_name: str,
    chunk_size: int,
    chunk_overlap: int,
    source_docs: list[Document],
) -> tuple[Chroma, list[Document], int, float]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks: list[Document] = []
    for doc in source_docs:
        for piece in splitter.split_documents([doc]):
            piece.metadata["filename"] = doc.metadata.get("filename", "unknown")
            piece.metadata["doc_id"] = doc.metadata.get("doc_id", piece.metadata.get("filename", ""))
            chunks.append(piece)

    assign_chunk_ids(chunks)

    start = time.perf_counter()
    store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )
    if chunks:
        store.add_documents(chunks)
    elapsed = time.perf_counter() - start
    return store, chunks, len(chunks), elapsed


def create_benchmark_es_store() -> ElasticsearchStore:
    return ElasticsearchStore(ES_URL, BENCHMARK_ES_PREFIX)


def _hybrid_fuse(
    question: str,
    store: Chroma,
    es_store: ElasticsearchStore | None,
    *,
    fetch_k: int,
    hybrid_alpha: float,
    rrf_k: int,
) -> tuple[list[tuple[Document, float]], bool]:
    """返回 (fused_results, hybrid_fallback)。"""
    if es_store and es_store.available and es_store.count() > 0:
        vector_results = store.similarity_search_with_score(question, k=fetch_k)
        bm25_results = es_store.search(question, size=fetch_k)
        fused = fuse_hybrid_results(
            vector_results,
            bm25_results,
            alpha=hybrid_alpha,
            rrf_k=rrf_k,
        )
        return fused, False

    print("  [warn] hybrid 模式但 ES 不可用或索引为空，已回退 vector", flush=True)
    return store.similarity_search_with_score(question, k=fetch_k), True


def search_hits(
    question: str,
    store: Chroma,
    es_store: ElasticsearchStore | None,
    reranker: Reranker | None,
    *,
    retrieval_mode: str,
    top_k: int,
    fetch_k: int,
    hybrid_alpha: float,
    rrf_k: int,
    mmr_lambda: float,
) -> tuple[list[tuple[Document, float]], bool]:
    """返回 (hits, hybrid_fallback)。"""
    recall_k = max(fetch_k, top_k)
    hybrid_fallback = False

    if retrieval_mode == "mmr":
        docs = store.max_marginal_relevance_search(
            question,
            k=top_k,
            fetch_k=recall_k,
            lambda_mult=mmr_lambda,
        )
        return [(doc, 0.0) for doc in docs], False

    if retrieval_mode in {"hybrid", "hybrid_rerank"}:
        fused, hybrid_fallback = _hybrid_fuse(
            question,
            store,
            es_store,
            fetch_k=recall_k,
            hybrid_alpha=hybrid_alpha,
            rrf_k=rrf_k,
        )
        if retrieval_mode == "hybrid":
            return fused[:top_k], hybrid_fallback
        if reranker and fused:
            return reranker.rerank(question, fused, top_k), hybrid_fallback
        return fused[:top_k], hybrid_fallback

    vector_results = store.similarity_search_with_score(question, k=recall_k)
    if retrieval_mode == "rerank" and reranker and vector_results:
        return reranker.rerank(question, vector_results, top_k), False
    return vector_results[:top_k], False


def compute_reciprocal_rank(retrieved_files: list[str], expected: str) -> tuple[float, int | None]:
    """返回 (reciprocal_rank, first_hit_rank)。未命中时 rank 为 None、RR 为 0。"""
    for rank, filename in enumerate(retrieved_files, start=1):
        if filename == expected:
            return 1.0 / rank, rank
    return 0.0, None


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * pct) - 1))
    return ordered[index]


def compute_chunk_recall_at_k(
    hits: list[tuple[Document, float]],
    case: dict[str, Any],
) -> float | None:
    """Chunk 级 Recall@K：expected_chunk_ids 或 expected_chunk_substrings 命中比例。"""
    expected_ids = case.get("expected_chunk_ids") or []
    if expected_ids:
        retrieved_ids = [str(doc.metadata.get("chunk_id", "")) for doc, _ in hits]
        matched = sum(1 for eid in expected_ids if eid in retrieved_ids)
        return matched / len(expected_ids)

    substrings = case.get("expected_chunk_substrings") or []
    if substrings:
        contents = [doc.page_content for doc, _ in hits]
        matched = sum(
            1
            for sub in substrings
            if any(sub in content for content in contents)
        )
        return matched / len(substrings)
    return None


def compute_by_tag(case_results: list[CaseResult]) -> dict[str, dict[str, float]]:
    tag_cases: dict[str, list[CaseResult]] = defaultdict(list)
    for case in case_results:
        tags = case.tags or ["untagged"]
        for tag in tags:
            tag_cases[tag].append(case)

    by_tag: dict[str, dict[str, float]] = {}
    for tag, cases in sorted(tag_cases.items()):
        n = len(cases)
        by_tag[tag] = {
            "count": float(n),
            "hit_at_1_rate": sum(c.hit_at_1 for c in cases) / n,
            "hit_at_k_rate": sum(c.hit_at_k for c in cases) / n,
            "mrr": sum(c.reciprocal_rank for c in cases) / n,
        }
    return by_tag


def evaluate_config(
    embeddings: Any,
    work_dir: Path,
    source_docs: list[Document],
    cases: list[dict[str, Any]],
    *,
    retrieval_mode: str,
    chunk_size: int,
    chunk_overlap: int,
    top_k: int,
    fetch_k: int,
    hybrid_alpha: float,
    rrf_k: int,
    mmr_lambda: float,
    es_store: ElasticsearchStore | None,
    reranker: Reranker | None,
) -> ConfigResult:
    tag = f"c{chunk_size}_o{chunk_overlap}_k{top_k}_{retrieval_mode}"
    persist_dir = work_dir / tag
    persist_dir.mkdir(parents=True, exist_ok=True)

    store, chunks, total_chunks, ingest_seconds = build_vectorstore(
        embeddings,
        persist_dir,
        collection_name=f"bench_{tag}",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        source_docs=source_docs,
    )

    hybrid_fallback = False
    if retrieval_mode in ("hybrid", "hybrid_rerank") and es_store:
        es_store.clear_index()
        indexed = es_store.index_chunks(chunks)
        if indexed == 0:
            hybrid_fallback = True

    case_results: list[CaseResult] = []
    for case in cases:
        question = case["question"]
        expected = case["expected_filename"]
        tags = case.get("tags", [])
        t0 = time.perf_counter()
        hits, fell_back = search_hits(
            question,
            store,
            es_store,
            reranker,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
            fetch_k=fetch_k,
            hybrid_alpha=hybrid_alpha,
            rrf_k=rrf_k,
            mmr_lambda=mmr_lambda,
        )
        retrieval_ms = (time.perf_counter() - t0) * 1000
        hybrid_fallback = hybrid_fallback or fell_back

        retrieved_files = [str(doc.metadata.get("filename", "unknown")) for doc, _ in hits]
        retrieved_chunk_ids = [str(doc.metadata.get("chunk_id", "")) for doc, _ in hits]
        top_filename = retrieved_files[0] if retrieved_files else ""
        top_score = float(hits[0][1]) if hits else 0.0
        context_chars = sum(len(doc.page_content) for doc, _ in hits)
        reciprocal_rank, first_hit_rank = compute_reciprocal_rank(retrieved_files, expected)
        chunk_recall = compute_chunk_recall_at_k(hits, case)

        case_results.append(
            CaseResult(
                question=question,
                expected_filename=expected,
                tags=tags,
                hit_at_1=top_filename == expected,
                hit_at_k=expected in retrieved_files,
                reciprocal_rank=reciprocal_rank,
                first_hit_rank=first_hit_rank,
                retrieval_ms=retrieval_ms,
                top_filename=top_filename,
                top_score=top_score,
                context_chars=context_chars,
                chunk_recall_at_k=chunk_recall,
                retrieved_files=retrieved_files,
                retrieved_chunk_ids=retrieved_chunk_ids,
            )
        )

    n = len(case_results) or 1
    retrieval_times = [c.retrieval_ms for c in case_results]
    chunk_recalls = [c.chunk_recall_at_k for c in case_results if c.chunk_recall_at_k is not None]
    avg_chunk_recall = sum(chunk_recalls) / len(chunk_recalls) if chunk_recalls else None
    return ConfigResult(
        retrieval_mode=retrieval_mode,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        top_k=top_k,
        fetch_k=fetch_k,
        hybrid_alpha=hybrid_alpha,
        rrf_k=rrf_k,
        total_chunks=total_chunks,
        ingest_seconds=ingest_seconds,
        hit_at_1_rate=sum(c.hit_at_1 for c in case_results) / n,
        hit_at_k_rate=sum(c.hit_at_k for c in case_results) / n,
        mrr=sum(c.reciprocal_rank for c in case_results) / n,
        avg_retrieval_ms=sum(retrieval_times) / n,
        p95_retrieval_ms=percentile(retrieval_times, 0.95),
        avg_top_score=sum(c.top_score for c in case_results) / n,
        avg_context_chars=sum(c.context_chars for c in case_results) / n,
        avg_chunk_recall_at_k=avg_chunk_recall,
        by_tag=compute_by_tag(case_results),
        case_results=case_results,
        hybrid_fallback=hybrid_fallback,
    )


def print_summary(results: list[ConfigResult]) -> None:
    print()
    print("=" * 100)
    print("RAG 调参对比结果（sample-docs 检索评测，未调用 LLM）")
    print("=" * 100)
    header = (
        f"{'mode':<7} {'chunk':>6} {'overlap':>7} {'top_k':>5} "
        f"{'chunks':>6} {'ingest_s':>8} {'hit@1':>6} {'hit@k':>6} {'mrr':>6} "
        f"{'cRec':>6} {'ret_ms':>7} {'avg_score':>9} {'ctx_chars':>9}"
    )
    print(header)
    print("-" * 100)
    for r in sorted(
        results,
        key=lambda x: (-x.hit_at_k_rate, -x.hit_at_1_rate, x.avg_top_score),
    ):
        mode_label = r.retrieval_mode
        if r.hybrid_fallback:
            mode_label += "*"
        crec = f"{r.avg_chunk_recall_at_k:.0%}" if r.avg_chunk_recall_at_k is not None else "  n/a"
        print(
            f"{mode_label:<7} {r.chunk_size:>6} {r.chunk_overlap:>7} {r.top_k:>5} "
            f"{r.total_chunks:>6} {r.ingest_seconds:>8.2f} "
            f"{r.hit_at_1_rate:>6.0%} {r.hit_at_k_rate:>6.0%} {r.mrr:>6.0%} "
            f"{crec:>6} "
            f"{r.avg_retrieval_ms:>7.0f} "
            f"{r.avg_top_score:>9.4f} {r.avg_context_chars:>9.0f}"
        )
    print("-" * 100)
    best = max(results, key=lambda x: (x.hit_at_k_rate, x.hit_at_1_rate, -x.avg_top_score))
    print(
        f"推荐组合（hit@k 优先）: mode={best.retrieval_mode}, "
        f"chunk_size={best.chunk_size}, chunk_overlap={best.chunk_overlap}, top_k={best.top_k}"
    )
    print(
        "说明: hit@1 = Top1 命中; hit@k = Top-K 命中; mrr = 首个正确结果排名倒数均值; "
        "* = hybrid 已回退 vector"
    )
    print()


def write_csv(path: Path, results: list[ConfigResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "retrieval_mode",
                "chunk_size",
                "chunk_overlap",
                "top_k",
                "fetch_k",
                "hybrid_alpha",
                "rrf_k",
                "total_chunks",
                "ingest_seconds",
                "hit_at_1_rate",
                "hit_at_k_rate",
                "mrr",
                "avg_retrieval_ms",
                "p95_retrieval_ms",
                "avg_top_score",
                "avg_context_chars",
                "avg_chunk_recall_at_k",
                "hybrid_fallback",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r.retrieval_mode,
                    r.chunk_size,
                    r.chunk_overlap,
                    r.top_k,
                    r.fetch_k,
                    r.hybrid_alpha,
                    r.rrf_k,
                    r.total_chunks,
                    f"{r.ingest_seconds:.3f}",
                    f"{r.hit_at_1_rate:.4f}",
                    f"{r.hit_at_k_rate:.4f}",
                    f"{r.mrr:.4f}",
                    f"{r.avg_retrieval_ms:.1f}",
                    f"{r.p95_retrieval_ms:.1f}",
                    f"{r.avg_top_score:.4f}",
                    f"{r.avg_context_chars:.0f}",
                    "" if r.avg_chunk_recall_at_k is None else f"{r.avg_chunk_recall_at_k:.4f}",
                    r.hybrid_fallback,
                ]
            )


def write_json(path: Path, results: list[ConfigResult], cases: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cases": cases,
        "results": [
            {
                "retrieval_mode": r.retrieval_mode,
                "chunk_size": r.chunk_size,
                "chunk_overlap": r.chunk_overlap,
                "top_k": r.top_k,
                "fetch_k": r.fetch_k,
                "hybrid_alpha": r.hybrid_alpha,
                "rrf_k": r.rrf_k,
                "total_chunks": r.total_chunks,
                "ingest_seconds": r.ingest_seconds,
                "hit_at_1_rate": r.hit_at_1_rate,
                "hit_at_k_rate": r.hit_at_k_rate,
                "mrr": r.mrr,
                "avg_retrieval_ms": r.avg_retrieval_ms,
                "p95_retrieval_ms": r.p95_retrieval_ms,
                "avg_top_score": r.avg_top_score,
                "avg_context_chars": r.avg_context_chars,
                "avg_chunk_recall_at_k": r.avg_chunk_recall_at_k,
                "hybrid_fallback": r.hybrid_fallback,
                "by_tag": r.by_tag,
                "details": [
                    {
                        "question": c.question,
                        "expected_filename": c.expected_filename,
                        "tags": c.tags,
                        "hit_at_1": c.hit_at_1,
                        "hit_at_k": c.hit_at_k,
                        "reciprocal_rank": c.reciprocal_rank,
                        "first_hit_rank": c.first_hit_rank,
                        "retrieval_ms": c.retrieval_ms,
                        "top_filename": c.top_filename,
                        "top_score": c.top_score,
                        "context_chars": c.context_chars,
                        "chunk_recall_at_k": c.chunk_recall_at_k,
                        "retrieved_files": c.retrieved_files,
                        "retrieved_chunk_ids": c.retrieved_chunk_ids,
                    }
                    for c in r.case_results
                ],
            }
            for r in results
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_eval_history(results: list[ConfigResult], cases: list[dict[str, Any]]) -> None:
    """追加 L2 摘要到 history.jsonl，供看板趋势图使用。"""
    history_file = ROOT / "data" / "eval" / "history.jsonl"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "case_count": len(cases),
        "results": [
            {
                "retrieval_mode": r.retrieval_mode,
                "chunk_size": r.chunk_size,
                "top_k": r.top_k,
                "hit_at_1_rate": r.hit_at_1_rate,
                "hit_at_k_rate": r.hit_at_k_rate,
                "mrr": r.mrr,
                "avg_chunk_recall_at_k": r.avg_chunk_recall_at_k,
            }
            for r in results
        ],
    }
    with history_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="对比不同 RAG chunk_size / top_k / 检索模式")
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
        "--modes",
        default="vector",
        help="检索模式：vector,hybrid,mmr,rerank,hybrid_rerank（逗号分隔）",
    )
    parser.add_argument(
        "--mmr-lambda",
        type=float,
        default=0.5,
        help="MMR lambda，默认 0.5",
    )
    parser.add_argument(
        "--fetch-k",
        type=int,
        default=20,
        help="hybrid 模式向量/BM25 各取条数，默认 20",
    )
    parser.add_argument(
        "--hybrid-alpha",
        type=float,
        default=HYBRID_ALPHA,
        help="RRF 向量权重，默认与 RAG_HYBRID_ALPHA 一致",
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=RRF_K,
        help="RRF 常数，默认与 RAG_RRF_K 一致",
    )
    parser.add_argument(
        "--cases-file",
        type=Path,
        help='自定义评测 JSON，格式 [{"question":"...", "expected_filename":"...", "tags":[]}]',
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
    modes = parse_mode_list(args.modes)
    cases = load_cases(args.cases_file)

    work_dir = args.output_dir
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    es_store: ElasticsearchStore | None = None
    needs_es = any(m in modes for m in ("hybrid", "hybrid_rerank"))
    needs_rerank = any(m in modes for m in ("rerank", "hybrid_rerank"))
    if needs_es:
        es_store = create_benchmark_es_store()
        if not es_store.available:
            print(f"[warn] ES 不可用（ES_URL={ES_URL or '(empty)'}），hybrid 将回退 vector")
    reranker = Reranker() if needs_rerank else None

    print(f"加载 Embedding（provider={EMBEDDING_PROVIDER}）...")
    embeddings = load_embeddings()
    source_docs = load_sample_documents()
    print(f"示例文档 {len(source_docs)} 篇，评测问题 {len(cases)} 条")
    print(
        f"参数网格: modes={modes}, chunk_sizes={chunk_sizes}, "
        f"top_k={top_k_values}, overlap={args.chunk_overlap}"
    )

    results: list[ConfigResult] = []
    total = len(modes) * len(chunk_sizes) * len(top_k_values)
    idx = 0
    for mode in modes:
        for chunk_size in chunk_sizes:
            for top_k in top_k_values:
                idx += 1
                print(
                    f"[{idx}/{total}] mode={mode}, chunk={chunk_size}, top_k={top_k} ...",
                    flush=True,
                )
                result = evaluate_config(
                    embeddings,
                    work_dir,
                    source_docs,
                    cases,
                    retrieval_mode=mode,
                    chunk_size=chunk_size,
                    chunk_overlap=args.chunk_overlap,
                    top_k=top_k,
                    fetch_k=args.fetch_k,
                    hybrid_alpha=args.hybrid_alpha,
                    rrf_k=args.rrf_k,
                    mmr_lambda=args.mmr_lambda,
                    es_store=es_store,
                    reranker=reranker,
                )
                results.append(result)
                if args.verbose:
                    for c in result.case_results:
                        mark = "OK" if c.hit_at_k else "MISS"
                        rank_info = f"rank={c.first_hit_rank}" if c.first_hit_rank else "rank=-"
                        print(
                            f"  [{mark}] {c.question} -> top1={c.top_filename} "
                            f"(expect {c.expected_filename}, {rank_info}, "
                            f"{c.retrieval_ms:.0f}ms)"
                        )
                    for tag, stats in result.by_tag.items():
                        print(
                            f"  [tag:{tag}] hit@1={stats['hit_at_1_rate']:.0%} "
                            f"hit@k={stats['hit_at_k_rate']:.0%} (n={int(stats['count'])})"
                        )

    print_summary(results)

    if not args.no_csv:
        write_csv(work_dir / "benchmark_rag_params.csv", results)
        write_json(work_dir / "benchmark_rag_params.json", results, cases)
        append_eval_history(results, cases)
        print(f"结果已写入: {work_dir / 'benchmark_rag_params.csv'}")
        print(f"详情已写入: {work_dir / 'benchmark_rag_params.json'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
