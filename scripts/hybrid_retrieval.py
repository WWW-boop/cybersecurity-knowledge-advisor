"""Query Dense + Graph retrieval and print normalized fused evidence."""

import argparse
import json
import sys

import httpx
from neo4j import GraphDatabase
from qdrant_client import QdrantClient

from cybersecurity_advisor.config.settings import get_settings
from cybersecurity_advisor.graph.retrieval import GraphRetriever, Neo4jGraphRepository
from cybersecurity_advisor.jev.entity_validation import JevEntityValidator, JevError
from cybersecurity_advisor.retrieval.dense import DenseRetriever
from cybersecurity_advisor.retrieval.hybrid import HybridRetriever


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser()
    command.add_argument("query")
    command.add_argument("--top-k", type=int, default=5)
    command.add_argument("--dense-k", type=int, default=10)
    command.add_argument("--graph-k", type=int, default=10)
    command.add_argument("--max-depth", type=int, choices=(1, 2, 3), default=2)
    command.add_argument("--language", choices=("th", "en"))
    command.add_argument("--topic")
    command.add_argument("--score-threshold", type=float)
    command.add_argument("--fusion-method", choices=("naive", "rrf", "weighted"))
    command.add_argument("--dense-weight", type=float)
    command.add_argument("--graph-weight", type=float)
    command.add_argument("--rrf-k", type=int)
    command.add_argument(
        "--skip-jev",
        action="store_true",
        help="Disable JEV entity validation for an explicit ablation run",
    )
    return command


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argument_parser = parser()
    args = argument_parser.parse_args()
    settings = get_settings()
    password = (
        settings.neo4j_password.get_secret_value() if settings.neo4j_password is not None else None
    )
    if password is None:
        argument_parser.error("NEO4J_PASSWORD is required for hybrid retrieval")

    validator = None
    if not args.skip_jev:
        if settings.jev_api_key is None:
            argument_parser.error(
                "JEV_API_KEY (or TYPE_SAFE) is required; use --skip-jev only for ablation"
            )
        validator = JevEntityValidator(
            httpx.Client(
                base_url=settings.jev_api_url.rstrip("/"),
                headers={"Authorization": f"Bearer {settings.jev_api_key.get_secret_value()}"},
                timeout=settings.jev_timeout_seconds,
            ),
            model=settings.jev_model,
        )

    qdrant_api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
    qdrant_client = QdrantClient(url=settings.qdrant_url, api_key=qdrant_api_key)
    dense = DenseRetriever(
        client=qdrant_client,
        collection_name=settings.qdrant_collection,
        model_name=settings.embedding_model,
        model_revision=settings.embedding_revision,
        trust_remote_code=settings.embedding_trust_remote_code,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        max_length=settings.embedding_max_length,
    )
    try:
        with GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, password),
        ) as driver:
            driver.verify_connectivity()
            graph = GraphRetriever(
                Neo4jGraphRepository(driver, database=settings.neo4j_database),
                max_per_document=settings.graph_max_per_document,
                entity_validator=validator,
                entity_min_confidence=settings.jev_entity_min_confidence,
            )
            hybrid = HybridRetriever(
                dense,
                graph,
                dense_weight=settings.hybrid_dense_weight,
                graph_weight=settings.hybrid_graph_weight,
                rrf_k=settings.hybrid_rrf_k,
                max_per_document=settings.hybrid_max_per_document,
                default_method=settings.hybrid_fusion_method,
            )
            rows = hybrid.search(
                args.query,
                top_k=args.top_k,
                dense_k=args.dense_k,
                graph_k=args.graph_k,
                max_depth=args.max_depth,
                language=args.language,
                topic=args.topic,
                score_threshold=args.score_threshold,
                method=args.fusion_method,
                dense_weight=args.dense_weight,
                graph_weight=args.graph_weight,
                rrf_k=args.rrf_k,
            )
    except JevError as error:
        argument_parser.error(str(error))
    finally:
        if validator is not None:
            validator.close()
        qdrant_client.close()
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
