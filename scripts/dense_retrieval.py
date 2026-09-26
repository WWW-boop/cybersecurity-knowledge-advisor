"""Index and query BGE-M3 dense vectors in Qdrant."""

import argparse
import json
import sys
from pathlib import Path

from qdrant_client import QdrantClient

from cybersecurity_advisor.config.settings import get_settings
from cybersecurity_advisor.retrieval.dense import DenseRetriever


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser()
    command.add_argument(
        "--local-path",
        type=Path,
        help="Use persistent Qdrant local mode instead of QDRANT_URL",
    )
    subcommands = command.add_subparsers(dest="command", required=True)

    index = subcommands.add_parser("index")
    index.add_argument("--chunks", type=Path, default=Path("data/chunks/chunks.jsonl"))
    index.add_argument("--recreate", action="store_true")

    query = subcommands.add_parser("query")
    query.add_argument("query")
    query.add_argument("--top-k", type=int, default=5)
    query.add_argument("--language", choices=("th", "en"))
    query.add_argument("--topic")
    query.add_argument("--score-threshold", type=float)

    demo = subcommands.add_parser("demo")
    demo.add_argument("query")
    demo.add_argument("--chunks", type=Path, default=Path("data/chunks/chunks.jsonl"))
    demo.add_argument("--top-k", type=int, default=5)
    return command


def retriever(local_path: Path | None) -> DenseRetriever:
    settings = get_settings()
    if local_path:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        client = QdrantClient(path=local_path)
    else:
        api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        client = QdrantClient(url=settings.qdrant_url, api_key=api_key)
    return DenseRetriever(
        client=client,
        collection_name=settings.qdrant_collection,
        model_name=settings.embedding_model,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        max_length=settings.embedding_max_length,
    )


def print_results(results: list[dict[str, object]]) -> None:
    for result in results:
        print(
            json.dumps(
                {
                    "score": round(float(result["score"]), 4),
                    "chunk_id": result["chunk_id"],
                    "title": result["title"],
                    "citation": result["citation"],
                    "url": result["url"],
                    "content": str(result["content"])[:500],
                },
                ensure_ascii=False,
            )
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parser().parse_args()
    dense = retriever(args.local_path)
    if args.command == "index":
        print(f"indexed {dense.index(args.chunks, recreate=args.recreate)} chunks")
    elif args.command == "query":
        print_results(
            dense.search(
                args.query,
                top_k=args.top_k,
                language=args.language,
                topic=args.topic,
                score_threshold=args.score_threshold,
            )
        )
    else:
        print(f"indexed {dense.index(args.chunks, recreate=True)} chunks")
        print_results(dense.search(args.query, top_k=args.top_k))


if __name__ == "__main__":
    main()
