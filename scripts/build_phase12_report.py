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
    parser.add_argument("--root", type=Path, default=Path("data/evaluation/results"))
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/evaluation/questions.v0.1.jsonl")
    )
    args = parser.parse_args()
    retrieval = read_json(args.root / "retrieval-phase12" / "summary.json")
    generation = read_json(args.root / "generation-local-full" / "summary.json")
    ablation = read_json(args.root / "generation-ablation-smoke" / "summary.json")
    api = read_json(args.root / "generation-api-full" / "summary.json")[0]
    qwen_api = read_json(args.root / "generation-qwen36-token3000-full" / "summary.json")[0]
    qwen_rows = read_json(args.root / "generation-qwen36-token3000-full" / "results.json")
    qwen_cap_hits = sum((row.get("output_tokens") or 0) >= 3000 for row in qwen_rows)
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
            "## API comparison: GPT-4o Mini + Dynamic Hybrid + all JEV",
            "",
            f"- Questions completed: {api['questions']}",
            f"- Reference token F1: {value(api, 'avg_reference_token_f1')}",
            f"- JEV groundedness: {value(api, 'avg_groundedness')}",
            f"- Citation coverage: {value(api, 'avg_citation_coverage')}",
            f"- Unsupported claim rate: {value(api, 'avg_unsupported_claim_rate')}",
            f"- Average latency: {api['avg_total_latency_ms'] / 1000:.3f} seconds",
            f"- P95 latency: {api['p95_latency_ms'] / 1000:.3f} seconds",
            f"- Average context: {api['avg_context_tokens']:.1f} tokens / "
            f"{api['avg_final_context_k']:.2f} chunks",
            "- API cost remains N/A until project-approved per-token rates are supplied.",
            "",
            "## Selected API: Qwen 3.6 Flash (3,000-token ceiling)",
            "",
            f"- Questions completed: {qwen_api['questions']}",
            f"- Reference token F1: {value(qwen_api, 'avg_reference_token_f1')}",
            f"- JEV groundedness: {value(qwen_api, 'avg_groundedness')}",
            f"- Citation coverage: {value(qwen_api, 'avg_citation_coverage')}",
            f"- Unsupported claim rate: {value(qwen_api, 'avg_unsupported_claim_rate')}",
            f"- Average latency: {qwen_api['avg_total_latency_ms'] / 1000:.3f} seconds",
            f"- P95 latency: {qwen_api['p95_latency_ms'] / 1000:.3f} seconds",
            f"- Average output tokens: {qwen_api['avg_output_tokens']:.1f}",
            f"- Runs at or above the 3,000-token ceiling: {qwen_cap_hits}/{len(qwen_rows)}",
            "",
            "## Preliminary interpretation",
            "",
            "- Hybrid Dynamic had the highest Recall@5 and improved MRR over fixed Hybrid, "
            "but used more retrieval latency.",
            "- Pre-generation JEV sharply reduced context in the smoke case, while citation JEV "
            "made claim-level groundedness measurable.",
            "- The GPT-4o Mini comparator was about 3.3x faster and had slightly higher "
            "reference-token F1, "
            "but lower citation groundedness and coverage than the local baseline.",
            "- The selected Qwen 3.6 API improved citation metrics over GPT-4o Mini but used about "
            "7.7x more output tokens and had latency close to Local Qwen.",
            "- Final quality conclusions remain blocked by incomplete human review, not by missing "
            "evaluation code or API execution.",
        ]
    )
    report = args.root / "phase12-report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 3, figsize=(18, 5))
    names = [row["retriever"] for row in retrieval]
    recall_bars = axes[0].bar(names, [row["recall_at_k"] for row in retrieval], color="#2563eb")
    axes[0].set_title("Retrieval Recall@5")
    axes[0].set_ylim(0, 1)
    axes[0].bar_label(recall_bars, fmt="%.3f")
    metrics = ("Ref F1", "Groundedness", "Citation coverage")
    width = 0.25
    positions = range(len(metrics))
    local_bars = axes[1].bar(
        [position - width for position in positions],
        [
            local["avg_reference_token_f1"],
            local["avg_groundedness"],
            local["avg_citation_coverage"],
        ],
        width,
        label="Local Qwen 3.5",
    )
    api_bars = axes[1].bar(
        list(positions),
        [api["avg_reference_token_f1"], api["avg_groundedness"], api["avg_citation_coverage"]],
        width,
        label="GPT-4o Mini API",
    )
    qwen_bars = axes[1].bar(
        [position + width for position in positions],
        [
            qwen_api["avg_reference_token_f1"],
            qwen_api["avg_groundedness"],
            qwen_api["avg_citation_coverage"],
        ],
        width,
        label="Qwen 3.6 API",
    )
    axes[1].set_title("Generation quality proxies")
    axes[1].set_xticks(list(positions), metrics)
    axes[1].set_ylim(0, 1)
    axes[1].legend()
    axes[1].bar_label(local_bars, fmt="%.2f")
    axes[1].bar_label(api_bars, fmt="%.2f")
    axes[1].bar_label(qwen_bars, fmt="%.2f")
    latency_bars = axes[2].bar(
        ("Local Qwen 3.5", "GPT-4o Mini", "Qwen 3.6 API"),
        [
            local["avg_total_latency_ms"] / 1000,
            api["avg_total_latency_ms"] / 1000,
            qwen_api["avg_total_latency_ms"] / 1000,
        ],
        color=("#16a34a", "#f59e0b", "#7c3aed"),
    )
    axes[2].set_title("Average end-to-end latency")
    axes[2].set_ylabel("seconds")
    axes[2].bar_label(latency_bars, fmt="%.2f")
    figure.tight_layout()
    figure.savefig(args.root / "phase12-overview.png", dpi=180, bbox_inches="tight")
    plt.close(figure)
    print(report)


if __name__ == "__main__":
    main()
