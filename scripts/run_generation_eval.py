"""Run generation, JEV ablation, and system-metric experiments through the chat API."""

import argparse
import csv
import json
import math
import re
import sys
import time
from pathlib import Path
from statistics import mean, median
from typing import Any

import httpx

from cybersecurity_advisor.evaluation.dataset import EvaluationQuestion, load_evaluation_dataset

TOKEN = re.compile(r"[A-Za-z0-9_]+|[\u0E00-\u0E7F]")
CITATION = re.compile(r"\[S(\d+)\]", re.IGNORECASE)


def tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN.findall(text)]


def reference_token_f1(answer: str, reference: str) -> float:
    """Return a transparent lexical correctness proxy for multilingual answers."""
    answer_tokens = tokens(answer)
    reference_tokens = tokens(reference)
    if not answer_tokens or not reference_tokens:
        return 0.0
    answer_counts = {token: answer_tokens.count(token) for token in set(answer_tokens)}
    reference_counts = {token: reference_tokens.count(token) for token in set(reference_tokens)}
    overlap = sum(
        min(count, reference_counts.get(token, 0)) for token, count in answer_counts.items()
    )
    precision = overlap / len(answer_tokens)
    recall = overlap / len(reference_tokens)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def expected_term_coverage(answer: str, question: EvaluationQuestion) -> float:
    terms = [*question.expected_topics, *question.expected_entities]
    normalized = answer.casefold().replace("_", " ")
    return mean(term.casefold().replace("_", " ") in normalized for term in terms) if terms else 1.0


def deterministic_citation_metrics(answer: str, source_count: int) -> tuple[float, float]:
    citations = [int(value) for value in CITATION.findall(answer)]
    if not citations:
        return 0.0, 0.0
    valid = sum(1 <= value <= source_count for value in citations)
    return valid / len(citations), float(valid > 0)


def percentile(values: list[float], value: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * value) - 1)]


def evaluate_experiment(
    client: httpx.Client,
    questions: list[EvaluationQuestion],
    *,
    api_url: str,
    provider: str,
    jev_mode: str,
    dynamic_k: bool,
    experiment: str,
    input_cost_per_million: float,
    output_cost_per_million: float,
) -> tuple[list[dict[str, Any]], str | None]:
    rows: list[dict[str, Any]] = []
    for question in questions:
        started = time.perf_counter()
        response = client.post(
            f"{api_url.rstrip('/')}/api/v1/chat",
            json={
                "query": question.question,
                "provider": provider,
                "language": question.language if question.language_group != "cross" else None,
                "fusion_method": "rrf",
                "dynamic_k": dynamic_k,
                "jev_mode": jev_mode,
            },
        )
        if response.status_code >= 400:
            return rows, f"HTTP {response.status_code}: {error_detail(response)}"
        body = response.json()
        citation = body.get("citation_validation") or {}
        validity, coverage = deterministic_citation_metrics(body["answer"], len(body["sources"]))
        input_tokens = body.get("input_tokens")
        output_tokens = body.get("output_tokens")
        cost = None
        if (
            provider == "openai"
            and input_tokens is not None
            and output_tokens is not None
            and (input_cost_per_million or output_cost_per_million)
        ):
            cost = (
                input_tokens * input_cost_per_million
                + output_tokens * output_cost_per_million
            ) / 1_000_000
        source_ids = [source.get("corpus_source_id") for source in body["sources"]]
        expected = set(question.relevant_documents)
        rows.append(
            {
                "experiment": experiment,
                "provider": provider,
                "model": body["model"],
                "jev_mode": jev_mode,
                "dynamic_k": dynamic_k,
                "question_id": question.question_id,
                "language_group": question.language_group,
                "question_type": question.question_type,
                "review_status": question.review_status,
                "answer": body["answer"],
                "reference_answer": question.reference_answer,
                "source_ids": source_ids,
                "source_chunks": [source["chunk_id"] for source in body["sources"]],
                "context_document_recall": len(expected & set(source_ids)) / len(expected),
                "reference_token_f1": reference_token_f1(body["answer"], question.reference_answer),
                "answer_relevance": expected_term_coverage(body["answer"], question),
                "citation_accuracy": citation.get("groundedness", validity),
                "citation_coverage": citation.get("citation_coverage", coverage),
                "groundedness": citation.get("groundedness"),
                "unsupported_claim_rate": (
                    citation.get("unsupported_claims", 0) / citation["total_claims"]
                    if citation.get("total_claims")
                    else None
                ),
                "total_latency_ms": body["total_latency_ms"],
                "wall_latency_ms": (time.perf_counter() - started) * 1000,
                "retrieval_latency_ms": body["retrieval_latency_ms"],
                "jev_filter_latency_ms": body["jev_filter_latency_ms"],
                "generation_latency_ms": body["generation_latency_ms"],
                "citation_validation_latency_ms": body["citation_validation_latency_ms"],
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "context_tokens": body["context_tokens"],
                "final_context_k": body["final_context_k"],
                "jev_passed": (body.get("jev_filter") or {}).get("passed"),
                "process_cpu_seconds": body["process_cpu_seconds"],
                "process_memory_mib": body.get("process_memory_mib"),
                "estimated_api_cost_usd": cost,
                "retrieval_budget": body.get("retrieval_budget"),
            }
        )
    return rows, None


def average(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return mean(values) if values else None


def error_detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", response.text))
    except ValueError:
        return response.text or "unknown"


def summarize(
    rows: list[dict[str, Any]], skipped: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    summaries = []
    for experiment in dict.fromkeys(row["experiment"] for row in rows):
        group = [row for row in rows if row["experiment"] == experiment]
        summary = {
            "experiment": experiment,
            "status": "complete",
            "questions": len(group),
            "provider": group[0]["provider"],
            "model": group[0]["model"],
            "jev_mode": group[0]["jev_mode"],
            "dynamic_k": group[0]["dynamic_k"],
            "p50_latency_ms": median(row["total_latency_ms"] for row in group),
            "p95_latency_ms": percentile([row["total_latency_ms"] for row in group], 0.95),
        }
        for key in (
            "reference_token_f1",
            "answer_relevance",
            "context_document_recall",
            "citation_accuracy",
            "citation_coverage",
            "groundedness",
            "unsupported_claim_rate",
            "total_latency_ms",
            "retrieval_latency_ms",
            "jev_filter_latency_ms",
            "generation_latency_ms",
            "citation_validation_latency_ms",
            "input_tokens",
            "output_tokens",
            "context_tokens",
            "final_context_k",
            "jev_passed",
            "process_cpu_seconds",
            "process_memory_mib",
            "estimated_api_cost_usd",
            "gpu_vram_mib",
        ):
            summary[f"avg_{key}"] = average(group, key)
        summaries.append(summary)
    summaries.extend(skipped)
    return summaries


def write_outputs(
    output: Path,
    rows: list[dict[str, Any]],
    summary: list[dict[str, Any]],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = list(dict.fromkeys(key for row in summary for key in row))
    with (output / "summary.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)
    with (output / "manual_review.csv").open("w", encoding="utf-8-sig", newline="") as file:
        fields = [
            "experiment",
            "question_id",
            "answer",
            "reference_answer",
            "correctness_1_to_5",
            "groundedness_1_to_5",
            "language_quality_1_to_5",
            "reviewer",
            "notes",
        ]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)

    completed = [row for row in summary if row["status"] == "complete"]
    if completed:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        names = [
            f"{row['provider']}\n{row['jev_mode'].replace('_pregen', '+pregen')}\n"
            f"{'dynamic' if row['dynamic_k'] else 'fixed'}"
            for row in completed
        ]
        figure, axes = plt.subplots(2, 2, figsize=(13, 9))
        charts = (
            ("avg_reference_token_f1", "Reference token F1", "ratio", 1),
            ("avg_groundedness", "JEV groundedness", "ratio", 1),
            ("avg_total_latency_ms", "Average total latency", "seconds", 0.001),
            ("avg_context_tokens", "Average context tokens", "tokens", 1),
        )
        for axis, (key, title, unit, scale) in zip(axes.flat, charts, strict=True):
            values = [(row.get(key) or 0) * scale for row in completed]
            bars = axis.bar(names, values, color="#2563eb")
            axis.set_title(title)
            axis.set_ylabel(unit)
            axis.tick_params(axis="x", rotation=0, labelsize=8)
            axis.bar_label(bars, fmt="%.2f", padding=3)
        figure.suptitle("Generation and JEV ablation comparison")
        figure.tight_layout()
        figure.savefig(output / "comparison.png", dpi=180, bbox_inches="tight")
        plt.close(figure)

    lines = [
        "# Generation evaluation",
        "",
        "Automatic correctness uses lexical reference-token F1; final quality claims require "
        "the manual review sheet.",
        "",
        "| Experiment | Status | Provider | JEV | Dynamic K | Questions |",
        "|---|---|---|---|---:|---:|",
    ]
    lines.extend(
        f"| {row['experiment']} | {row['status']} | {row.get('provider', '')} | "
        f"{row.get('jev_mode', '')} | {row.get('dynamic_k', '')} | "
        f"{row.get('questions', 0)} |"
        for row in summary
    )
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser()
    command.add_argument(
        "--dataset", type=Path, default=Path("data/evaluation/questions.v0.1.jsonl")
    )
    command.add_argument("--api-url", default="http://localhost:8000")
    command.add_argument("--providers", nargs="+", choices=("ollama", "openai"), default=["ollama"])
    command.add_argument(
        "--jev-modes",
        nargs="+",
        choices=("none", "pregen", "entity_pregen", "all"),
        default=["none", "pregen", "entity_pregen", "all"],
    )
    command.add_argument(
        "--dynamic-modes",
        nargs="+",
        choices=("fixed", "dynamic"),
        default=["fixed", "dynamic"],
    )
    command.add_argument("--limit", type=int, default=0)
    command.add_argument("--timeout", type=float, default=300)
    command.add_argument("--api-input-cost-per-million", type=float, default=0)
    command.add_argument("--api-output-cost-per-million", type=float, default=0)
    command.add_argument(
        "--output", type=Path, default=Path("data/evaluation/results/generation-ablation")
    )
    return command


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parser().parse_args()
    questions = load_evaluation_dataset(args.dataset)
    if args.limit:
        questions = questions[: args.limit]
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    with httpx.Client(timeout=args.timeout) as client:
        for provider in args.providers:
            for mode in args.jev_modes:
                for dynamic_mode in args.dynamic_modes:
                    experiment = f"{provider}-{mode}-{dynamic_mode}"
                    experiment_rows, reason = evaluate_experiment(
                        client,
                        questions,
                        api_url=args.api_url,
                        provider=provider,
                        jev_mode=mode,
                        dynamic_k=dynamic_mode == "dynamic",
                        experiment=experiment,
                        input_cost_per_million=args.api_input_cost_per_million,
                        output_cost_per_million=args.api_output_cost_per_million,
                    )
                    rows.extend(experiment_rows)
                    if reason:
                        skipped.append(
                            {
                                "experiment": experiment,
                                "status": "skipped",
                                "provider": provider,
                                "jev_mode": mode,
                                "dynamic_k": dynamic_mode == "dynamic",
                                "questions": len(experiment_rows),
                                "reason": reason,
                            }
                        )
        try:
            models = client.get("http://localhost:11434/api/ps").json().get("models", [])
            vram_by_model = {item["name"]: item.get("size_vram", 0) / 2**20 for item in models}
            for row in rows:
                row["gpu_vram_mib"] = vram_by_model.get(row["model"])
        except (httpx.HTTPError, ValueError, KeyError):
            for row in rows:
                row["gpu_vram_mib"] = None
    summary = summarize(rows, skipped)
    write_outputs(args.output, rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
