"""Run document-level retrieval evaluation against the project API."""

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path
from statistics import mean, median
from typing import Any

import httpx

from cybersecurity_advisor.evaluation.dataset import EvaluationQuestion, load_evaluation_dataset

ENDPOINTS = {
    "dense": "/api/v1/retrieve",
    "graph": "/api/v1/graph/retrieve",
    "hybrid": "/api/v1/hybrid/retrieve",
}
METRICS = ("recall_at_k", "precision_at_k", "hit_rate_at_k", "mrr_at_k", "ndcg_at_k")


def deduplicate_source_ids(rows: list[dict[str, Any]]) -> list[str]:
    """Return source IDs in first-result order, ignoring duplicate chunks."""
    ranked: list[str] = []
    for row in rows:
        source_id = str((row.get("metadata") or {}).get("source_id") or "")
        if not source_id:
            raise ValueError("retrieval result is missing metadata.source_id")
        if source_id not in ranked:
            ranked.append(source_id)
    return ranked


def retrieval_metrics(expected: set[str], ranked: list[str], *, k: int) -> dict[str, float]:
    """Calculate binary document relevance metrics at K."""
    retrieved = ranked[:k]
    relevance = [int(source_id in expected) for source_id in retrieved]
    relevant_documents = expected.intersection(retrieved)
    first_relevant = next((rank for rank, value in enumerate(relevance, start=1) if value), None)
    dcg = sum(value / math.log2(rank + 1) for rank, value in enumerate(relevance, start=1))
    ideal_relevant = min(len(expected), k)
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_relevant + 1))
    return {
        "recall_at_k": len(relevant_documents) / len(expected),
        "precision_at_k": sum(relevance) / k,
        "hit_rate_at_k": float(bool(relevant_documents)),
        "mrr_at_k": 1 / first_relevant if first_relevant is not None else 0.0,
        "ndcg_at_k": dcg / idcg if idcg else 0.0,
    }


def request_payload(question: EvaluationQuestion, retriever: str, top_k: int) -> dict[str, Any]:
    """Build the smallest request shared by one retrieval experiment."""
    payload: dict[str, Any] = {
        "query": question.question,
        "top_k": top_k,
        "language": question.language if question.language_group != "cross" else None,
    }
    if retriever == "graph":
        payload["max_depth"] = 2
    elif retriever == "hybrid":
        payload.update(
            dense_k=max(10, top_k * 2),
            graph_k=max(10, top_k * 2),
            max_depth=2,
            fusion_method="rrf",
        )
    return payload


def evaluate(
    client: httpx.Client,
    questions: list[EvaluationQuestion],
    retrievers: list[str],
    *,
    api_url: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """Evaluate every question against each requested retrieval endpoint."""
    rows: list[dict[str, Any]] = []
    for retriever in retrievers:
        warmup = client.post(
            f"{api_url.rstrip('/')}{ENDPOINTS[retriever]}",
            json=request_payload(questions[0], retriever, top_k),
        )
        warmup.raise_for_status()
        for question in questions:
            started = time.perf_counter()
            response = client.post(
                f"{api_url.rstrip('/')}{ENDPOINTS[retriever]}",
                json=request_payload(question, retriever, top_k),
            )
            response.raise_for_status()
            latency_ms = (time.perf_counter() - started) * 1000
            results = response.json()
            ranked = deduplicate_source_ids(results)
            rows.append(
                {
                    "retriever": retriever,
                    "question_id": question.question_id,
                    "language_group": question.language_group,
                    "question_type": question.question_type,
                    "expected_documents": question.relevant_documents,
                    "retrieved_documents": ranked[:top_k],
                    "retrieved_chunks": [row["chunk_id"] for row in results],
                    "latency_ms": latency_ms,
                    **retrieval_metrics(set(question.relevant_documents), ranked, k=top_k),
                }
            )
    return rows


def percentile(values: list[float], percentile_value: float) -> float:
    """Return a nearest-rank percentile without adding a dependency."""
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile_value * len(ordered)))
    return ordered[rank - 1]


def summarize(rows: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    """Build one macro-average row per retrieval method."""
    return [
        {
            "retriever": retriever,
            "questions": len(group),
            "top_k": top_k,
            **{metric: mean(row[metric] for row in group) for metric in METRICS},
            "avg_latency_ms": mean(row["latency_ms"] for row in group),
            "p50_latency_ms": median(row["latency_ms"] for row in group),
            "p95_latency_ms": percentile([row["latency_ms"] for row in group], 0.95),
        }
        for retriever in ENDPOINTS
        if (group := [row for row in rows if row["retriever"] == retriever])
    ]


def write_outputs(
    output: Path, rows: list[dict[str, Any]], summary: list[dict[str, Any]]
) -> None:
    """Write reproducible machine-readable evaluation artifacts."""
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "summary.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser()
    command.add_argument(
        "--dataset", type=Path, default=Path("data/evaluation/questions.v0.1.jsonl")
    )
    command.add_argument("--api-url", default="http://localhost:8000")
    command.add_argument(
        "--retrievers", nargs="+", choices=tuple(ENDPOINTS), default=list(ENDPOINTS)
    )
    command.add_argument("--top-k", type=int, choices=range(1, 26), default=5)
    command.add_argument("--timeout", type=float, default=120)
    command.add_argument(
        "--output", type=Path, default=Path("data/evaluation/results/retrieval-baseline")
    )
    return command


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parser().parse_args()
    questions = load_evaluation_dataset(args.dataset)
    with httpx.Client(timeout=args.timeout) as client:
        rows = evaluate(
            client,
            questions,
            args.retrievers,
            api_url=args.api_url,
            top_k=args.top_k,
        )
    summary = summarize(rows, args.top_k)
    write_outputs(args.output, rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
