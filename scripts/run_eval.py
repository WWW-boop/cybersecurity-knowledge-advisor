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
    "hybrid_dynamic": "/api/v1/hybrid/retrieve",
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
    elif retriever in {"hybrid", "hybrid_dynamic"}:
        payload.update(
            dense_k=max(10, top_k * 2),
            graph_k=max(10, top_k * 2),
            max_depth=2,
            fusion_method="rrf",
            dynamic_k=retriever == "hybrid_dynamic",
        )
    return payload


def entity_metrics(
    question: EvaluationQuestion, results: list[dict[str, Any]]
) -> dict[str, float | None]:
    """Score accepted graph entities against the dataset's expected entity labels."""

    def normalize(value: str) -> str:
        return "".join(character for character in value.casefold() if character.isalnum())

    expected = {normalize(value) for value in question.expected_entities}
    predicted = {
        normalize(str(validation.get("name") or ""))
        for row in results
        for validation in (
            row.get("entity_validations")
            or (row.get("metadata") or {}).get("entity_validations")
            or []
        )
        if validation.get("decision") == "same"
    }
    if not expected:
        return {"entity_precision": None, "entity_recall": None, "entity_f1": None}
    correct = len(expected & predicted)
    precision = correct / len(predicted) if predicted else 0.0
    recall = correct / len(expected)
    return {
        "entity_precision": precision,
        "entity_recall": recall,
        "entity_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
    }


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
            budget = (
                (results[0].get("metadata") or {}).get("retrieval_budget") if results else None
            ) or {}
            rows.append(
                {
                    "retriever": retriever,
                    "question_id": question.question_id,
                    "language_group": question.language_group,
                    "question_type": question.question_type,
                    "expected_documents": question.relevant_documents,
                    "retrieved_documents": ranked[:top_k],
                    "retrieved_chunks": [row["chunk_id"] for row in results],
                    "review_status": question.review_status,
                    "latency_ms": latency_ms,
                    "dense_k": budget.get("dense_k"),
                    "graph_k": budget.get("graph_k"),
                    "graph_depth": budget.get("graph_depth"),
                    "fusion_k": budget.get("fusion_k"),
                    "final_context_k": budget.get("selected_context_k", len(results)),
                    "context_tokens": budget.get("estimated_context_tokens"),
                    "chunk_recall_at_k": (
                        len(set(question.relevant_chunks) & {row["chunk_id"] for row in results})
                        / len(question.relevant_chunks)
                        if question.relevant_chunks
                        else None
                    ),
                    **(
                        entity_metrics(question, results)
                        if retriever != "dense"
                        else {
                            "entity_precision": None,
                            "entity_recall": None,
                            "entity_f1": None,
                        }
                    ),
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
    summaries = []
    for retriever in ENDPOINTS:
        group = [row for row in rows if row["retriever"] == retriever]
        if not group:
            continue
        summary = {
            "retriever": retriever,
            "questions": len(group),
            "top_k": top_k,
            **{metric: mean(row[metric] for row in group) for metric in METRICS},
            "avg_latency_ms": mean(row["latency_ms"] for row in group),
            "p50_latency_ms": median(row["latency_ms"] for row in group),
            "p95_latency_ms": percentile([row["latency_ms"] for row in group], 0.95),
        }
        for key in (
            "chunk_recall_at_k",
            "entity_precision",
            "entity_recall",
            "entity_f1",
            "dense_k",
            "graph_k",
            "graph_depth",
            "fusion_k",
            "final_context_k",
            "context_tokens",
        ):
            values = [row[key] for row in group if row[key] is not None]
            summary[f"avg_{key}"] = mean(values) if values else None
        summaries.append(summary)
    return summaries


def write_outputs(output: Path, rows: list[dict[str, Any]], summary: list[dict[str, Any]]) -> None:
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
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [row["retriever"] for row in summary]
    figure, axes = plt.subplots(2, 2, figsize=(12, 8))
    charts = (
        ("recall_at_k", "Document Recall@K", "ratio", 1),
        ("mrr_at_k", "MRR@K", "ratio", 1),
        ("avg_latency_ms", "Average retrieval latency", "seconds", 0.001),
        ("avg_final_context_k", "Average final context K", "chunks", 1),
    )
    for axis, (key, title, unit, scale) in zip(axes.flat, charts, strict=True):
        values = [(row.get(key) or 0) * scale for row in summary]
        bars = axis.bar(names, values, color=("#2563eb", "#7c3aed", "#16a34a", "#f59e0b"))
        axis.set_title(title)
        axis.set_ylabel(unit)
        axis.tick_params(axis="x", rotation=15)
        axis.bar_label(bars, fmt="%.2f", padding=3)
    figure.suptitle("Retrieval and Dynamic Top-K comparison")
    figure.tight_layout()
    figure.savefig(output / "comparison.png", dpi=180, bbox_inches="tight")
    plt.close(figure)

    review_note = (
        "All labels reviewed."
        if all(row["review_status"] == "reviewed" for row in rows)
        else "PRELIMINARY: dataset labels are draft and require human review."
    )
    lines = [
        "# Retrieval evaluation",
        "",
        review_note,
        "",
        "| Method | Recall@K | MRR@K | Avg latency (s) |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| {row['retriever']} | {row['recall_at_k']:.3f} | "
        f"{row['mrr_at_k']:.3f} | {row['avg_latency_ms'] / 1000:.3f} |"
        for row in summary
    )
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


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
