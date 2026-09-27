"""Compare local Ollama models on identical retrieved RAG context."""

import argparse
import csv
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import httpx

from cybersecurity_advisor.generation.answering import SYSTEM_PROMPT, build_context, build_prompt

DEFAULT_MODELS = ("qwen3.5:4b", "gemma3:4b", "llama3.2:3b")
CITATION = re.compile(r"\[S(\d+)\]")
THAI = re.compile(r"[\u0e00-\u0e7f]")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def select_questions(rows: list[dict[str, Any]], per_group: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    counts: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        group = row["language_group"]
        if counts[group] < per_group:
            selected.append(row)
            counts[group] += 1
    return selected


def retrieve_contexts(
    client: httpx.Client,
    questions: list[dict[str, Any]],
    api_url: str,
    top_k: int,
    max_context_chars: int,
) -> list[dict[str, Any]]:
    contexts = []
    for question in questions:
        group = question["language_group"]
        response = client.post(
            f"{api_url.rstrip('/')}/api/v1/hybrid/retrieve",
            json={
                "query": question["query"],
                "top_k": top_k,
                "fusion_method": "rrf",
                "language": group if group in {"th", "en"} else None,
            },
        )
        response.raise_for_status()
        context, sources = build_context(response.json(), max_chars=max_context_chars)
        if not sources:
            raise RuntimeError(f"No evidence returned for {question['query_id']}")
        contexts.append({**question, "context": context, "sources": sources})
    return contexts


def unload(client: httpx.Client, ollama_url: str, model: str) -> None:
    client.post(
        f"{ollama_url.rstrip('/')}/api/generate",
        json={"model": model, "keep_alive": 0},
    ).raise_for_status()


def model_vram(client: httpx.Client, ollama_url: str, model: str) -> int | None:
    response = client.get(f"{ollama_url.rstrip('/')}/api/ps")
    response.raise_for_status()
    row = next((item for item in response.json().get("models", []) if item["name"] == model), None)
    return row.get("size_vram") if row else None


def citation_metrics(answer: str, source_count: int) -> tuple[float, float]:
    citations = [int(value) for value in CITATION.findall(answer)]
    if not citations:
        return 0.0, 0.0
    valid = sum(1 <= value <= source_count for value in citations)
    return valid / len(citations), 1.0 if valid else 0.0


def run_model(
    client: httpx.Client,
    model: str,
    contexts: list[dict[str, Any]],
    ollama_url: str,
    max_output_tokens: int,
) -> list[dict[str, Any]]:
    client.post(
        f"{ollama_url.rstrip('/')}/api/generate",
        json={"model": model, "prompt": "Reply only with OK.", "stream": False},
    ).raise_for_status()
    rows = []
    for question in contexts:
        started = time.perf_counter()
        response = client.post(
            f"{ollama_url.rstrip('/')}/api/generate",
            json={
                "model": model,
                "system": SYSTEM_PROMPT,
                "prompt": build_prompt(question["query"], question["context"]),
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0,
                    "seed": 42,
                    "num_ctx": 4096,
                    "num_predict": max_output_tokens,
                },
            },
        )
        response.raise_for_status()
        wall_latency_ms = (time.perf_counter() - started) * 1000
        payload = response.json()
        answer = str(payload.get("response") or "").strip()
        validity, coverage = citation_metrics(answer, len(question["sources"]))
        eval_count = int(payload.get("eval_count") or 0)
        eval_seconds = float(payload.get("eval_duration") or 0) / 1e9
        rows.append(
            {
                "model": model,
                "query_id": question["query_id"],
                "language_group": question["language_group"],
                "question": question["query"],
                "context": question["context"],
                "answer": answer,
                "sources": question["sources"],
                "wall_latency_ms": wall_latency_ms,
                "prompt_tokens": payload.get("prompt_eval_count"),
                "output_tokens": eval_count,
                "hit_output_limit": eval_count >= max_output_tokens,
                "tokens_per_second": eval_count / eval_seconds if eval_seconds else 0.0,
                "citation_validity": validity,
                "citation_coverage": coverage,
                "language_match": float(
                    bool(THAI.search(answer)) == bool(THAI.search(question["query"]))
                ),
            }
        )
    vram = model_vram(client, ollama_url, model)
    for row in rows:
        row["model_vram_mib"] = vram / 2**20 if vram is not None else None
    unload(client, ollama_url, model)
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["model"]].append(row)
    return [
        {
            "model": model,
            "questions": len(model_rows),
            "avg_latency_ms": mean(row["wall_latency_ms"] for row in model_rows),
            "avg_tokens_per_second": mean(row["tokens_per_second"] for row in model_rows),
            "citation_validity": mean(row["citation_validity"] for row in model_rows),
            "citation_coverage": mean(row["citation_coverage"] for row in model_rows),
            "language_match": mean(row["language_match"] for row in model_rows),
            "completion_rate": mean(not row["hit_output_limit"] for row in model_rows),
            "model_vram_mib": model_rows[0]["model_vram_mib"],
        }
        for model, model_rows in grouped.items()
    ]


def write_outputs(output: Path, rows: list[dict[str, Any]], summary: list[dict[str, Any]]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "summary.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    with (output / "manual_review.csv").open("w", encoding="utf-8-sig", newline="") as file:
        fields = [
            "model",
            "query_id",
            "question",
            "answer",
            "correctness_1_to_5",
            "groundedness_1_to_5",
            "language_quality_1_to_5",
            "notes",
        ]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})

    import matplotlib.pyplot as plt

    models = [row["model"] for row in summary]
    figure, axes = plt.subplots(2, 2, figsize=(12, 8))
    charts = (
        ("avg_latency_ms", "Average latency", "seconds", 0.001),
        ("avg_tokens_per_second", "Generation speed", "tokens/s", 1),
        ("completion_rate", "Answers completed before token limit", "ratio", 1),
        ("model_vram_mib", "GPU memory used by model", "MiB", 1),
    )
    for axis, (key, title, unit, scale) in zip(axes.flat, charts, strict=True):
        values = [(row[key] or 0) * scale for row in summary]
        bars = axis.bar(models, values, color=("#2563eb", "#16a34a", "#f59e0b"))
        axis.set_title(title)
        axis.set_ylabel(unit)
        axis.tick_params(axis="x", rotation=15)
        axis.bar_label(bars, fmt="%.1f", padding=3)
    figure.suptitle("Ollama RAG model comparison (identical hybrid context)")
    figure.tight_layout()
    figure.savefig(output / "comparison.png", dpi=180, bbox_inches="tight")
    plt.close(figure)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser()
    command.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    command.add_argument(
        "--questions", type=Path, default=Path("data/evaluation/retrieval_questions.seed.jsonl")
    )
    command.add_argument("--questions-per-group", type=int, default=2)
    command.add_argument("--api-url", default="http://localhost:8000")
    command.add_argument("--ollama-url", default="http://localhost:11434")
    command.add_argument("--top-k", type=int, default=5)
    command.add_argument("--max-context-chars", type=int, default=12000)
    command.add_argument("--max-output-tokens", type=int, default=300)
    command.add_argument("--timeout", type=float, default=300)
    command.add_argument("--output", type=Path, default=Path("data/evaluation/ollama-benchmark"))
    return command


def main() -> None:
    args = parser().parse_args()
    questions = select_questions(load_jsonl(args.questions), args.questions_per_group)
    with httpx.Client(timeout=args.timeout) as client:
        contexts = retrieve_contexts(
            client,
            questions,
            args.api_url,
            args.top_k,
            args.max_context_chars,
        )
        rows = [
            row
            for model in args.models
            for row in run_model(
                client,
                model,
                contexts,
                args.ollama_url,
                args.max_output_tokens,
            )
        ]
    summary = summarize(rows)
    write_outputs(args.output, rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
