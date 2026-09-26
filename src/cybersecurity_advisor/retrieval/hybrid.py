"""Normalized Dense + Graph fusion with provenance and source diversity."""

import math
import re
from collections import defaultdict
from typing import Any, Literal, Protocol

FusionMethod = Literal["naive", "rrf", "weighted"]


class DenseSearch(Protocol):
    """Dense retrieval contract used without importing the embedding stack."""

    def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]: ...


class GraphSearch(Protocol):
    """Graph retrieval contract used by hybrid fusion."""

    def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]: ...


class HybridRetriever:
    """Retrieve from Dense and Graph paths, then fuse normalized candidates."""

    def __init__(
        self,
        dense_retriever: DenseSearch,
        graph_retriever: GraphSearch,
        *,
        dense_weight: float = 0.6,
        graph_weight: float = 0.4,
        rrf_k: int = 60,
        max_per_document: int = 2,
        default_method: FusionMethod = "rrf",
    ) -> None:
        self._validate_weights(dense_weight, graph_weight)
        if rrf_k < 1:
            raise ValueError("rrf_k must be positive")
        if max_per_document < 1:
            raise ValueError("max_per_document must be positive")
        if default_method not in {"naive", "rrf", "weighted"}:
            raise ValueError(f"Unsupported fusion method: {default_method}")
        self.dense_retriever = dense_retriever
        self.graph_retriever = graph_retriever
        self.dense_weight = dense_weight
        self.graph_weight = graph_weight
        self.rrf_k = rrf_k
        self.max_per_document = max_per_document
        self.default_method = default_method

    @staticmethod
    def _validate_weights(dense_weight: float, graph_weight: float) -> None:
        if dense_weight < 0 or graph_weight < 0:
            raise ValueError("fusion weights must not be negative")
        if dense_weight + graph_weight <= 0:
            raise ValueError("at least one fusion weight must be positive")

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))

    @classmethod
    def _normalized_dense_score(cls, score: float | None) -> float:
        if score is None:
            return 0.0
        return cls._clamp((score + 1.0) / 2.0)

    @classmethod
    def _normalized_graph_score(cls, score: float | None) -> float:
        return cls._clamp(score or 0.0)

    @staticmethod
    def _content_key(row: dict[str, Any]) -> tuple[str, str] | None:
        content = re.sub(r"\s+", " ", str(row.get("content") or "")).strip().casefold()
        if not content:
            return None
        return (str(row.get("url") or "").strip().casefold(), content)

    @staticmethod
    def _document_key(row: dict[str, Any]) -> str:
        return str(
            row.get("document_id") or row.get("source_id") or row.get("url") or row["chunk_id"]
        )

    @staticmethod
    def _merge_metadata(target: dict[str, Any], source: dict[str, Any]) -> None:
        for key, value in source.items():
            if key in {"score", "graph_score"}:
                continue
            if key not in target or target[key] in (None, "", [], {}):
                target[key] = value
            elif key == "entity_validations":
                known = {item["entity_id"] for item in target[key]}
                target[key].extend(item for item in value if item.get("entity_id") not in known)
            elif key in {"matched_entity_ids", "matched_entities", "relationships"}:
                target[key] = sorted({*target[key], *value})

    def _aggregate(
        self,
        dense_rows: list[dict[str, Any]],
        graph_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        by_chunk_id: dict[str, dict[str, Any]] = {}
        by_content: dict[tuple[str, str], dict[str, Any]] = {}

        def add(row: dict[str, Any], retriever: Literal["dense", "graph"], rank: int) -> None:
            chunk_id = str(row.get("chunk_id") or "")
            content = str(row.get("content") or "")
            if not chunk_id or not content.strip():
                return
            content_key = self._content_key(row)
            candidate = by_chunk_id.get(chunk_id)
            if candidate is None and content_key is not None:
                candidate = by_content.get(content_key)
            if candidate is None:
                metadata = {
                    key: value for key, value in row.items() if key not in {"score", "graph_score"}
                }
                candidate = {
                    **metadata,
                    "chunk_id": chunk_id,
                    "dense_score": None,
                    "graph_score": None,
                    "dense_rank": None,
                    "graph_rank": None,
                    "retrievers": set(),
                    "duplicate_chunk_ids": set(),
                    "first_seen": len(candidates) + 1,
                }
                candidates.append(candidate)
                if content_key is not None:
                    by_content[content_key] = candidate
            else:
                self._merge_metadata(candidate, row)
                if candidate["chunk_id"] != chunk_id:
                    candidate["duplicate_chunk_ids"].add(chunk_id)
            by_chunk_id[chunk_id] = candidate
            candidate["retrievers"].add(retriever)
            if retriever == "dense":
                if candidate["dense_rank"] is None or rank < candidate["dense_rank"]:
                    candidate["dense_score"] = float(row["score"])
                    candidate["dense_rank"] = rank
            else:
                if candidate["graph_rank"] is None or rank < candidate["graph_rank"]:
                    candidate["graph_score"] = float(row["graph_score"])
                    candidate["graph_rank"] = rank

        for rank, row in enumerate(dense_rows, start=1):
            add(row, "dense", rank)
        for rank, row in enumerate(graph_rows, start=1):
            add(row, "graph", rank)
        return candidates

    def fuse(
        self,
        dense_rows: list[dict[str, Any]],
        graph_rows: list[dict[str, Any]],
        *,
        top_k: int = 5,
        method: FusionMethod | None = None,
        dense_weight: float | None = None,
        graph_weight: float | None = None,
        rrf_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fuse already-ranked retrieval results into normalized candidates."""
        if top_k < 1:
            raise ValueError("top_k must be positive")
        resolved_method = self.default_method if method is None else method
        if resolved_method not in {"naive", "rrf", "weighted"}:
            raise ValueError(f"Unsupported fusion method: {resolved_method}")
        resolved_dense_weight = self.dense_weight if dense_weight is None else dense_weight
        resolved_graph_weight = self.graph_weight if graph_weight is None else graph_weight
        self._validate_weights(resolved_dense_weight, resolved_graph_weight)
        resolved_rrf_k = self.rrf_k if rrf_k is None else rrf_k
        if resolved_rrf_k < 1:
            raise ValueError("rrf_k must be positive")

        candidates = self._aggregate(dense_rows, graph_rows)
        total_weight = resolved_dense_weight + resolved_graph_weight
        max_rrf_score = 2 / (resolved_rrf_k + 1)
        for candidate in candidates:
            dense_rank = candidate["dense_rank"]
            graph_rank = candidate["graph_rank"]
            if resolved_method == "naive":
                score = 1 / candidate["first_seen"]
            elif resolved_method == "rrf":
                raw_score = sum(
                    1 / (resolved_rrf_k + rank)
                    for rank in (dense_rank, graph_rank)
                    if rank is not None
                )
                score = raw_score / max_rrf_score
            else:
                score = (
                    resolved_dense_weight * self._normalized_dense_score(candidate["dense_score"])
                    + resolved_graph_weight * self._normalized_graph_score(candidate["graph_score"])
                ) / total_weight
            candidate["hybrid_score"] = self._clamp(score)
            candidate["fusion_method"] = resolved_method
            candidate["retrievers"] = sorted(candidate["retrievers"])
            candidate["duplicate_chunk_ids"] = sorted(candidate["duplicate_chunk_ids"])
            del candidate["first_seen"]

        ranked = sorted(
            candidates,
            key=lambda row: (
                -row["hybrid_score"],
                row["dense_rank"] if row["dense_rank"] is not None else math.inf,
                row["graph_rank"] if row["graph_rank"] is not None else math.inf,
                row["chunk_id"],
            ),
        )
        selected: list[dict[str, Any]] = []
        document_counts: defaultdict[str, int] = defaultdict(int)
        for row in ranked:
            document_key = self._document_key(row)
            if document_counts[document_key] >= self.max_per_document:
                continue
            selected.append(row)
            document_counts[document_key] += 1
            if len(selected) == top_k:
                break
        return selected

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        dense_k: int = 10,
        graph_k: int = 10,
        max_depth: int = 2,
        language: str | None = None,
        topic: str | None = None,
        score_threshold: float | None = None,
        method: FusionMethod | None = None,
        dense_weight: float | None = None,
        graph_weight: float | None = None,
        rrf_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Run both retrievers and return normalized, diverse hybrid evidence."""
        if not query.strip():
            raise ValueError("Query must not be empty")
        if dense_k < 1 or graph_k < 1:
            raise ValueError("retrieval candidate limits must be positive")
        dense_rows = self.dense_retriever.search(
            query,
            top_k=dense_k,
            language=language,
            topic=topic,
            score_threshold=score_threshold,
        )
        graph_rows = self.graph_retriever.search(
            query,
            top_k=graph_k,
            max_depth=max_depth,
            language=language,
            topic=topic,
        )
        return self.fuse(
            dense_rows,
            graph_rows,
            top_k=top_k,
            method=method,
            dense_weight=dense_weight,
            graph_weight=graph_weight,
            rrf_k=rrf_k,
        )
