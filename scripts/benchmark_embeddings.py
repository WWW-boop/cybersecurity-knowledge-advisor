"""Compare multilingual embedding models on the local retrieval corpus."""

import argparse
import csv
import gc
import json
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean

import numpy as np

MODELS = {
    "bge-m3": ("BAAI/bge-m3", False, None),
    "gte-multilingual-base": ("Alibaba-NLP/gte-multilingual-base", True, None),
    "congen-multilingual-mpnet": (
        "kornwtp/ConGen-paraphrase-multilingual-mpnet-base-v2",
        False,
        None,
    ),
}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def rank_metrics(
    ranked_source_ids: list[str], expected_source_ids: list[str]
) -> tuple[float, float]:
    expected = set(expected_source_ids)
    retrieved = set(ranked_source_ids)
    recall = len(expected & retrieved) / len(expected)
    first_rank = next(
        (rank for rank, source_id in enumerate(ranked_source_ids, 1) if source_id in expected),
        None,
    )
    return recall, 1 / first_rank if first_rank else 0.0


def summarize(per_query: list[dict]) -> dict[str, float | dict[str, float]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in per_query:
        groups[row["language_group"]].append(row)
    recall_by_language = {
        group: mean(row["recall_at_5"] for row in rows) for group, rows in sorted(groups.items())
    }
    return {
        "recall_at_5": mean(row["recall_at_5"] for row in per_query),
        "macro_recall_at_5": mean(recall_by_language.values()),
        "mrr_at_5": mean(row["mrr_at_5"] for row in per_query),
        "recall_at_5_by_language": recall_by_language,
    }


def percentile(values: list[float], percent: float) -> float:
    return float(np.percentile(np.asarray(values), percent))


def validate_token_ids(model, texts: list[str]) -> None:
    transformer = model._first_module()
    tokenizer = transformer.tokenizer
    embeddings = transformer.auto_model.get_input_embeddings()
    encoded = tokenizer(
        texts,
        truncation=True,
        max_length=model.max_seq_length,
        padding=False,
    )["input_ids"]
    highest_id = max(max(token_ids) for token_ids in encoded)
    if highest_id >= embeddings.num_embeddings:
        raise ValueError(
            f"Tokenizer produced token ID {highest_id}, but the model has only "
            f"{embeddings.num_embeddings} embedding rows"
        )


def evaluate_model(
    name: str,
    model_id: str,
    trust_remote_code: bool,
    chunks: list[dict],
    questions: list[dict],
    batch_size: int,
    max_length: int,
    model_max_length: int | None,
    top_k: int,
    device: str,
    local_files_only: bool,
) -> dict:
    import torch
    from sentence_transformers import SentenceTransformer

    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    load_started = time.perf_counter()
    model = SentenceTransformer(
        model_id,
        device=device,
        trust_remote_code=trust_remote_code,
        local_files_only=local_files_only,
    )
    config = model._first_module().auto_model.config
    position_limit = max(1, getattr(config, "max_position_embeddings", max_length) - 2)
    model.max_seq_length = min(
        model.max_seq_length,
        max_length,
        model_max_length or max_length,
        position_limit,
    )
    model.encode("warmup", normalize_embeddings=True, show_progress_bar=False)
    load_seconds = time.perf_counter() - load_started

    texts = [f"{row['title']}\n{row['section']}\n{row['content']}" for row in chunks]
    validate_token_ids(model, texts)
    encode_started = time.perf_counter()
    corpus_vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    corpus_encode_seconds = time.perf_counter() - encode_started

    per_query = []
    latencies = []
    for question in questions:
        query_started = time.perf_counter()
        query_vector = model.encode(
            question["query"],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        scores = corpus_vectors @ query_vector
        ranked_indices = np.argsort(scores)[-top_k:][::-1]
        latency_ms = (time.perf_counter() - query_started) * 1000
        latencies.append(latency_ms)
        ranked_sources = [chunks[index]["source_id"] for index in ranked_indices]
        recall, mrr = rank_metrics(ranked_sources, question["expected_source_ids"])
        per_query.append(
            {
                "query_id": question["query_id"],
                "language_group": question["language_group"],
                "query": question["query"],
                "expected_source_ids": question["expected_source_ids"],
                "recall_at_5": recall,
                "mrr_at_5": mrr,
                "latency_ms": latency_ms,
                "results": [
                    {
                        "rank": rank,
                        "chunk_id": chunks[index]["chunk_id"],
                        "source_id": chunks[index]["source_id"],
                        "score": float(scores[index]),
                    }
                    for rank, index in enumerate(ranked_indices, 1)
                ],
            }
        )

    summary = summarize(per_query)
    result = {
        "name": name,
        "model_id": model_id,
        "revision": getattr(config, "_commit_hash", None),
        "device": device,
        "hardware": torch.cuda.get_device_name(0) if device == "cuda" else "CPU",
        "peak_device_memory_mib": (
            torch.cuda.max_memory_allocated() / 2**20 if device == "cuda" else None
        ),
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "dimensions": int(model.get_embedding_dimension()),
        "max_sequence_length": model.max_seq_length,
        "chunks": len(chunks),
        "questions": len(questions),
        "load_seconds": load_seconds,
        "corpus_encode_seconds": corpus_encode_seconds,
        "p50_query_latency_ms": percentile(latencies, 50),
        "p95_query_latency_ms": percentile(latencies, 95),
        "estimated_vector_storage_mib": len(chunks) * corpus_vectors.shape[1] * 4 / 2**20,
        **summary,
        "per_query": per_query,
    }
    del model, corpus_vectors
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    return result


def write_csv(results: list[dict], output: Path) -> None:
    fields = [
        "name",
        "model_id",
        "parameters",
        "dimensions",
        "max_sequence_length",
        "recall_at_5",
        "macro_recall_at_5",
        "mrr_at_5",
        "p50_query_latency_ms",
        "p95_query_latency_ms",
        "corpus_encode_seconds",
        "estimated_vector_storage_mib",
        "hardware",
        "peak_device_memory_mib",
    ]
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: result[field] for field in fields} for result in results)


def write_chart(results: list[dict], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    display_names = {
        "bge-m3": "BGE-M3",
        "gte-multilingual-base": "GTE multilingual",
        "congen-multilingual-mpnet": "ConGen MPNet",
    }
    labels = [display_names.get(result["name"], result["name"]) for result in results]
    colors = ["#2563eb", "#16a34a", "#ea580c"]
    figure, axes = plt.subplots(2, 3, figsize=(18, 10))
    figure.suptitle(
        "Embedding Model Benchmark\n"
        f"{results[0]['hardware']} · {results[0]['chunks']} chunks · "
        f"{results[0]['questions']} seed questions",
        fontsize=18,
        fontweight="bold",
    )

    language_axis = axes[0, 0]
    groups = ["th", "en", "cross"]
    positions = np.arange(len(groups))
    width = 0.24
    for index, (result, label, color) in enumerate(
        zip(results, labels, colors[: len(results)], strict=True)
    ):
        values = [result["recall_at_5_by_language"][group] for group in groups]
        offset = (index - (len(results) - 1) / 2) * width
        bars = language_axis.bar(positions + offset, values, width, label=label, color=color)
        language_axis.bar_label(bars, fmt="%.2f", fontsize=8, padding=2)
    language_axis.set_title("Recall@5 by language ↑")
    language_axis.set_xticks(positions, ["Thai", "English", "Cross-language"])
    language_axis.set_ylim(0, 1.12)
    language_axis.legend(fontsize=8)

    panels = [
        (axes[0, 1], "Macro Recall@5 ↑", "macro_recall_at_5", 1.0, "%.3f"),
        (axes[0, 2], "MRR@5 ↑", "mrr_at_5", 1.0, "%.3f"),
        (axes[1, 0], "P95 query latency (ms) ↓", "p95_query_latency_ms", None, "%.1f"),
        (axes[1, 1], "Corpus encoding time (s) ↓", "corpus_encode_seconds", None, "%.1f"),
        (axes[1, 2], "Peak GPU memory (MiB) ↓", "peak_device_memory_mib", None, "%.0f"),
    ]
    for axis, title, key, fixed_max, value_format in panels:
        values = [float(result[key]) for result in results]
        bars = axis.barh(labels, values, color=colors[: len(results)])
        axis.bar_label(bars, fmt=value_format, padding=3)
        axis.set_title(title)
        axis.set_xlim(0, fixed_max or max(values) * 1.18)
        axis.invert_yaxis()
        axis.grid(axis="x", alpha=0.2)

    figure.tight_layout(rect=(0, 0, 1, 0.93))
    figure.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(figure)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser()
    command.add_argument("--chunks", type=Path, default=Path("data/chunks/chunks.jsonl"))
    command.add_argument(
        "--questions",
        type=Path,
        default=Path("data/evaluation/retrieval_questions.seed.jsonl"),
    )
    command.add_argument("--output", type=Path, default=Path("data/evaluation/model-benchmark"))
    command.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    command.add_argument("--batch-size", type=int, default=8)
    command.add_argument("--max-length", type=int, default=1024)
    command.add_argument("--top-k", type=int, default=5)
    command.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    command.add_argument("--allow-downloads", action="store_true")
    command.add_argument("--resume", action="store_true")
    return command


def main() -> None:
    args = parser().parse_args()
    import torch

    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    if device == "auto":
        device = "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    chunks = load_jsonl(args.chunks)
    questions = load_jsonl(args.questions)
    if not chunks or not questions:
        raise ValueError("Chunks and questions must not be empty")
    if args.top_k < 1 or args.top_k > len(chunks):
        raise ValueError("top-k must be between 1 and the number of chunks")
    args.output.mkdir(parents=True, exist_ok=True)

    results = []
    for name in args.models:
        model_id, trust_remote_code, model_max_length = MODELS[name]
        checkpoint = args.output / f"{name}.json"
        if args.resume and checkpoint.exists():
            result = json.loads(checkpoint.read_text(encoding="utf-8"))
            if (
                result["device"] == device
                and result["chunks"] == len(chunks)
                and result["questions"] == len(questions)
            ):
                result["macro_recall_at_5"] = mean(result["recall_at_5_by_language"].values())
                print(f"using checkpoint for {name}", flush=True)
                results.append(result)
                continue
        print(f"benchmarking {name} ({model_id})", flush=True)
        result = evaluate_model(
            name,
            model_id,
            trust_remote_code,
            chunks,
            questions,
            args.batch_size,
            args.max_length,
            model_max_length,
            args.top_k,
            device,
            not args.allow_downloads,
        )
        results.append(result)
        checkpoint.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    (args.output / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csv(results, args.output / "summary.csv")
    write_chart(results, args.output / "comparison.png")
    for result in results:
        print(
            f"{result['name']}: Recall@5={result['recall_at_5']:.3f}, "
            f"MRR@5={result['mrr_at_5']:.3f}, "
            f"p95={result['p95_query_latency_ms']:.1f}ms"
        )


if __name__ == "__main__":
    main()
