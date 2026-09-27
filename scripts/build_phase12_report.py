"""Combine Phase 12 experiment artifacts into one honest summary and overview chart."""

import argparse
import json
from pathlib import Path
from typing import Any

from cybersecurity_advisor.evaluation.dataset import load_evaluation_dataset


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def value(row: dict[str, Any], key: str) -> str:
    item = row.get(key)
    return "N/A" if item is None else f"{item:.3f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=Path, default=Path("data/evaluation/results")
    )
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/evaluation/questions.v0.1.jsonl")
    )
    args = parser.parse_args()
    retrieval = read_json(args.root / "retrieval-phase12" / "summary.json")
    generation = read_json(args.root / "generation-local-full" / "summary.json")
    ablation = read_json(args.root / "generation-ablation-smoke" / "summary.json")
    api_status = read_json(args.root / "generation-api-status" / "summary.json")
    questions = load_evaluation_dataset(args.dataset)
    reviewed = sum(question.review_status == "reviewed" for question in questions)

    lines = [
        "# Phase 12 evaluation report",
        "",
        "> PRELIMINARY: retrieval labels and generated answers still require independent "
        "human review.",
        "",
        "## Dataset",
        "",
        f"- Questions: {len(questions)} (Thai/English/cross-language)",
        f"- Human-reviewed records: {reviewed}/{len(questions)}",
        "- Automatic reference-token F1 is a transparent proxy, not a human correctness score.",
        "",
        "## Retrieval",
        "",
        "| Method | Recall@5 | Precision@5 | MRR@5 | NDCG@5 | Avg latency (s) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        f"| {row['retriever']} | {row['recall_at_k']:.3f} | "
        f"{row['precision_at_k']:.3f} | {row['mrr_at_k']:.3f} | "
        f"{row['ndcg_at_k']:.3f} | {row['avg_latency_ms'] / 1000:.3f} |"
        for row in retrieval
    )
    local = generation[0]
    lines.extend(
        [
            "",
            "## Local generation: Qwen 3.5 4B + Dynamic Hybrid + all JEV",
            "",
            f"- Questions completed: {local['questions']}",
            f"- Reference token F1: {value(local, 'avg_reference_token_f1')}",
            f"- JEV groundedness: {value(local, 'avg_groundedness')}",
            f"- Citation coverage: {value(local, 'avg_citation_coverage')}",
            f"- Unsupported claim rate: {value(local, 'avg_unsupported_claim_rate')}",
            f"- Average latency: {local['avg_total_latency_ms'] / 1000:.3f} seconds",
            f"- P95 latency: {local['p95_latency_ms'] / 1000:.3f} seconds",
            f"- Average context: {local['avg_context_tokens']:.1f} tokens / "
            f"{local['avg_final_context_k']:.2f} chunks",
            f"- Process RAM: {local['avg_process_memory_mib']:.1f} MiB",
            f"- Ollama model VRAM: {local['avg_gpu_vram_mib']:.1f} MiB",
            "",
            "## JEV ablation smoke test",
            "",
            "The eight Fixed/Dynamic x JEV configurations completed on one question. "
            "This proves the experiment paths run, but n=1 is not evidence of superiority.",
            "",
            "| Experiment | Ref F1 | Groundedness | Context tokens | Latency (s) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    lines.extend(
        f"| {row['experiment']} | {value(row, 'avg_reference_token_f1')} | "
        f"{value(row, 'avg_groundedness')} | {value(row, 'avg_context_tokens')} | "
        f"{row['avg_total_latency_ms'] / 1000:.3f} |"
        for row in ablation
        if row["status"] == "complete"
    )
    lines.extend(
        [
            "",
            "## API LLM status",
            "",
            f"- {api_status[0]['status']}: {api_status[0].get('reason', '')}",
            "- The runner supports API token/cost metrics once credentials and per-million-token "
            "prices are supplied.",
            "",
            "## Preliminary interpretation",
            "",
            "- Hybrid Dynamic had the highest Recall@5 and improved MRR over fixed Hybrid, "
            "but used more retrieval latency.",
            "- Pre-generation JEV sharply reduced context in the smoke case, while citation JEV "
            "made claim-level groundedness measurable.",
            "- Final Local-vs-API and ablation conclusions are blocked by missing API credentials "
            "and incomplete human review, not by missing evaluation code.",
        ]
    )
    report = args.root / "phase12-report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 2, figsize=(13, 5))
    names = [row["retriever"] for row in retrieval]
    recall_bars = axes[0].bar(names, [row["recall_at_k"] for row in retrieval], color="#2563eb")
    axes[0].set_title("Retrieval Recall@5")
    axes[0].set_ylim(0, 1)
    axes[0].bar_label(recall_bars, fmt="%.3f")
    stages = ("retrieval", "JEV filter", "generation", "citation JEV")
    stage_values = (
        local["avg_retrieval_latency_ms"] / 1000,
        local["avg_jev_filter_latency_ms"] / 1000,
        local["avg_generation_latency_ms"] / 1000,
        local["avg_citation_validation_latency_ms"] / 1000,
    )
    stage_bars = axes[1].bar(stages, stage_values, color="#16a34a")
    axes[1].set_title("Average end-to-end latency breakdown")
    axes[1].set_ylabel("seconds")
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].bar_label(stage_bars, fmt="%.2f")
    figure.tight_layout()
    figure.savefig(args.root / "phase12-overview.png", dpi=180, bbox_inches="tight")
    plt.close(figure)
    print(report)


if __name__ == "__main__":
    main()
