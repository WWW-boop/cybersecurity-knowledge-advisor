"""Extract cybersecurity graph facts and ingest them into Neo4j."""

import argparse
import json
from pathlib import Path

from cybersecurity_advisor.config.settings import get_settings
from cybersecurity_advisor.graph.construction import (
    GraphRecord,
    Neo4jGraphStore,
    extract_graph_record,
)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser()
    subcommands = command.add_subparsers(dest="command", required=True)
    extract = subcommands.add_parser("extract")
    extract.add_argument("--chunks", type=Path, default=Path("data/chunks/chunks.jsonl"))
    extract.add_argument("--output", type=Path, default=Path("data/graph/graph_records.jsonl"))
    ingest = subcommands.add_parser("ingest")
    ingest.add_argument("--input", type=Path, default=Path("data/graph/graph_records.jsonl"))
    return command


def main() -> None:
    args = parser().parse_args()
    if args.command == "extract":
        records = [extract_graph_record(chunk) for chunk in load_jsonl(args.chunks)]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            "".join(json.dumps(record.to_dict(), ensure_ascii=False) + "\n" for record in records),
            encoding="utf-8",
        )
        print(
            f"wrote {len(records)} records, "
            f"{sum(len(record.entities) for record in records)} entity mentions, "
            f"{sum(len(record.facts) for record in records)} facts"
        )
        return

    from neo4j import GraphDatabase

    settings = get_settings()
    if settings.neo4j_password is None:
        raise ValueError("NEO4J_PASSWORD is required")
    records = [GraphRecord.from_dict(value) for value in load_jsonl(args.input)]
    with GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    ) as driver:
        driver.verify_connectivity()
        store = Neo4jGraphStore(driver)
        store.ensure_schema()
        chunks, facts = store.ingest(records)
    print(f"ingested {chunks} chunks and {facts} semantic facts")


if __name__ == "__main__":
    main()
