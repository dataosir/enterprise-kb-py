#!/usr/bin/env python3
"""L3 端到端 RAG 评测脚手架（RAGAS）。

在隔离临时索引上跑问答，输出 faithfulness / answer_relevancy 等指标。
完整 RAGAS 依赖: pip install -r requirements-eval.txt

不装 RAGAS 时可用 --dry-run 校验用例结构。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import (
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    CHAT_MODEL,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    SAMPLE_DOCS_DIR,
)
from scripts.benchmark_rag_params import CASES_FILE, load_cases

EVAL_WORK_DIR = ROOT / "data" / "eval" / "ragas_work"
DEFAULT_OUTPUT = ROOT / "data" / "eval" / "eval_report.json"

RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是企业知识库助手。仅根据提供的上下文回答问题；"
            "若上下文不足，请明确说明无法从资料中得出答案。",
        ),
        ("human", "上下文:\n{context}\n\n问题: {question}"),
    ]
)


@dataclass
class EvalCaseResult:
    question: str
    expected_filename: str
    expected_answer: str | None
    tags: list[str]
    answer: str
    hit_at_k: bool
    retrieval_ms: float
    generation_ms: float
    faithfulness: float | None = None
    answer_relevancy: float | None = None


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


def load_llm() -> ChatOpenAI:
    kwargs: dict[str, Any] = {
        "model": CHAT_MODEL,
        "api_key": OPENAI_API_KEY,
        "temperature": 0.2,
    }
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    return ChatOpenAI(**kwargs)


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
        raise FileNotFoundError(f"未在 {SAMPLE_DOCS_DIR} 找到示例文档")
    return docs


def build_index(
    embeddings: Any,
    source_docs: list[Document],
    *,
    chunk_size: int,
    chunk_overlap: int,
    work_dir: Path,
) -> Chroma:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks: list[Document] = []
    for doc in source_docs:
        for piece in splitter.split_documents([doc]):
            piece.metadata["filename"] = doc.metadata.get("filename", "unknown")
            piece.metadata["chunk_id"] = str(uuid.uuid4())
            chunks.append(piece)

    store = Chroma(
        collection_name="eval_ragas",
        embedding_function=embeddings,
        persist_directory=str(work_dir),
    )
    if chunks:
        store.add_documents(chunks)
    return store


def generate_answer(llm: ChatOpenAI, question: str, contexts: list[str]) -> str:
    context = "\n\n---\n\n".join(contexts) if contexts else "（无相关上下文）"
    chain = RAG_PROMPT | llm
    return str(chain.invoke({"context": context, "question": question}).content)


def run_ragas_metrics(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str | None],
) -> tuple[list[float | None], list[float | None]]:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, faithfulness
    except ImportError as exc:
        raise RuntimeError(
            "未安装 RAGAS，请执行: pip install -r requirements-eval.txt"
        ) from exc

    rows = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": [g or "" for g in ground_truths],
    }
    dataset = Dataset.from_dict(rows)
    # RAGAS 默认用 gpt-4o-mini 作裁判；显式传入与业务一致的 DeepSeek / OpenAI 兼容 LLM
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=load_llm(),
        embeddings=load_embeddings(),
    )
    faith_scores = list(result["faithfulness"])
    rel_scores = list(result["answer_relevancy"])
    return faith_scores, rel_scores


def dry_run_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    with_answer = [c for c in cases if c.get("expected_answer")]
    return {
        "mode": "dry-run",
        "total_cases": len(cases),
        "cases_with_expected_answer": len(with_answer),
        "metrics_planned": ["faithfulness", "answer_relevancy", "hit_at_k"],
        "note": "补充 expected_answer 后执行 --run；需 OPENAI_API_KEY 与 requirements-eval.txt",
        "cases": [
            {
                "question": c["question"],
                "expected_filename": c["expected_filename"],
                "has_expected_answer": bool(c.get("expected_answer")),
                "tags": c.get("tags", []),
            }
            for c in cases
        ],
    }


def run_eval(
    cases: list[dict[str, Any]],
    *,
    chunk_size: int,
    chunk_overlap: int,
    top_k: int,
    work_dir: Path,
    use_ragas: bool,
) -> dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("L3 评测需要 OPENAI_API_KEY（或兼容 API Key）")

    embeddings = load_embeddings()
    llm = load_llm()
    source_docs = load_sample_documents()
    store = build_index(
        embeddings,
        source_docs,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        work_dir=work_dir,
    )

    case_results: list[EvalCaseResult] = []
    questions: list[str] = []
    answers: list[str] = []
    contexts_batch: list[list[str]] = []
    ground_truths: list[str | None] = []

    for case in cases:
        question = case["question"]
        expected = case["expected_filename"]
        tags = case.get("tags", [])
        expected_answer = case.get("expected_answer")

        t0 = time.perf_counter()
        hits = store.similarity_search_with_score(question, k=top_k)
        retrieval_ms = (time.perf_counter() - t0) * 1000

        contexts = [doc.page_content for doc, _ in hits]
        retrieved_files = [str(doc.metadata.get("filename", "unknown")) for doc, _ in hits]
        hit_at_k = expected in retrieved_files

        t1 = time.perf_counter()
        answer = generate_answer(llm, question, contexts)
        generation_ms = (time.perf_counter() - t1) * 1000

        case_results.append(
            EvalCaseResult(
                question=question,
                expected_filename=expected,
                expected_answer=expected_answer,
                tags=tags,
                answer=answer,
                hit_at_k=hit_at_k,
                retrieval_ms=retrieval_ms,
                generation_ms=generation_ms,
            )
        )
        questions.append(question)
        answers.append(answer)
        contexts_batch.append(contexts)
        ground_truths.append(expected_answer)

    if use_ragas:
        faith_scores, rel_scores = run_ragas_metrics(
            questions, answers, contexts_batch, ground_truths
        )
        for idx, case in enumerate(case_results):
            case.faithfulness = faith_scores[idx]
            case.answer_relevancy = rel_scores[idx]

    n = len(case_results) or 1
    faith_values = [c.faithfulness for c in case_results if c.faithfulness is not None]
    rel_values = [c.answer_relevancy for c in case_results if c.answer_relevancy is not None]

    return {
        "mode": "ragas" if use_ragas else "generation-only",
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "top_k": top_k,
        "summary": {
            "case_count": len(case_results),
            "hit_at_k_rate": sum(c.hit_at_k for c in case_results) / n,
            "avg_retrieval_ms": sum(c.retrieval_ms for c in case_results) / n,
            "avg_generation_ms": sum(c.generation_ms for c in case_results) / n,
            "avg_faithfulness": sum(faith_values) / len(faith_values) if faith_values else None,
            "avg_answer_relevancy": sum(rel_values) / len(rel_values) if rel_values else None,
        },
        "cases": [asdict(c) for c in case_results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="L3 RAGAS 端到端评测")
    parser.add_argument("--cases-file", type=Path, default=CASES_FILE)
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=CHUNK_OVERLAP)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--work-dir", type=Path, default=EVAL_WORK_DIR)
    parser.add_argument("--dry-run", action="store_true", help="仅校验用例，不调用 LLM")
    parser.add_argument("--run", action="store_true", help="执行问答评测")
    parser.add_argument(
        "--ragas",
        action="store_true",
        help="启用 RAGAS 指标（需 requirements-eval.txt）",
    )
    args = parser.parse_args()

    cases = load_cases(args.cases_file)
    if args.dry_run or not args.run:
        report = dry_run_report(cases)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"dry-run 报告: {args.output}")
        print(f"用例 {report['total_cases']} 条，含 expected_answer: {report['cases_with_expected_answer']}")
        if not args.run:
            print("提示: 执行 --run 开始 L3 评测（需 API Key）")
        return 0

    if args.work_dir.exists():
        import shutil

        shutil.rmtree(args.work_dir)
    args.work_dir.mkdir(parents=True, exist_ok=True)

    report = run_eval(
        cases,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        top_k=args.top_k,
        work_dir=args.work_dir,
        use_ragas=args.ragas,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = report["summary"]
    print()
    print("=" * 72)
    print("L3 端到端评测")
    print("=" * 72)
    print(f"模式: {report['mode']}")
    print(f"hit@k: {summary['hit_at_k_rate']:.1%}")
    print(f"检索: {summary['avg_retrieval_ms']:.0f}ms, 生成: {summary['avg_generation_ms']:.0f}ms")
    if summary["avg_faithfulness"] is not None:
        print(f"faithfulness: {summary['avg_faithfulness']:.3f}")
        print(f"answer_relevancy: {summary['avg_answer_relevancy']:.3f}")
    print(f"报告: {args.output}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
