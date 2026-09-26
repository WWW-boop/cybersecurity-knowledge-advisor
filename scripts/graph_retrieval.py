"""Query bounded Neo4j graph paths and print their supporting chunks."""

import argparse
import json
import sys
from pathlib import Path

from neo4j import GraphDatabase

from cybersecurity_advisor.config.settings import get_settings
from cybersecurity_advisor.graph.construction import GraphRecord
from cybersecurity_advisor.graph.retrieval import (
    GraphRetriever,
    InMemoryGraphRepository,
    Neo4jGraphRepository,
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser()
    command.add_argument("query")
    command.add_argument("--top-k", type=int, default=5)
    command.add_argument("--max-depth", type=int, choices=(1, 2, 3), default=2)
    command.add_argument("--language", choices=("th", "en"))
    command.add_argument("--topic")
    command.add_argument(
        "--records",
        type=Path,
        help="Use graph_records.jsonl offline instead of connecting to Neo4j",
    )
    return command


def search(retriever: GraphRetriever, args: argparse.Namespace) -> list[dict]:
    return retriever.search(
        args.query,
        top_k=args.top_k,
        max_depth=args.max_depth,
        language=args.language,
        topic=args.topic,
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argument_parser = parser()
    args = argument_parser.parse_args()
    settings = get_settings()
    if args.records is not None:
        records = [
            GraphRecord.from_dict(json.loads(line))
            for line in args.records.read_text(encoding="utf-8").splitlines()
            if line
        ]
        rows = search(
            GraphRetriever(
                InMemoryGraphRepository(records),
                max_per_document=settings.graph_max_per_document,
            ),
            args,
        )
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    password = (
        settings.neo4j_password.get_secret_value() if settings.neo4j_password is not None else None
    )
    if password is None:
        argument_parser.error(
            "NEO4J_PASSWORD is required for live Neo4j queries; "
            "set it in .env or use --records for offline retrieval"
        )
    with GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, password) if password is not None else None,
    ) as driver:
        driver.verify_connectivity()
        retriever = GraphRetriever(
            Neo4jGraphRepository(driver, database=settings.neo4j_database),
            max_per_document=settings.graph_max_per_document,
        )
        rows = search(retriever, args)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
