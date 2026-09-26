"""Entity-aware graph retrieval with bounded Neo4j traversal."""

import re
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Protocol

from cybersecurity_advisor.graph.construction import ENTITIES, RELATION_TYPES, GraphRecord


@dataclass(frozen=True)
class EntityMatch:
    """A curated graph entity explicitly mentioned in a query."""

    entity_id: str
    name: str
    entity_type: str
    mention: str


@dataclass(frozen=True)
class GraphCandidate:
    """One evidence chunk recovered from an entity mention or semantic path."""

    chunk: dict[str, Any]
    start_entity_id: str
    entity_path: tuple[str, ...]
    relationships: tuple[str, ...]
    depth: int
    confidence: float


class GraphRepository(Protocol):
    """Storage boundary used by graph retrieval ranking."""

    def find_candidates(
        self,
        entity_ids: list[str],
        *,
        max_depth: int,
        language: str | None,
        topic: str | None,
        candidate_limit: int,
    ) -> list[GraphCandidate]: ...


def _find_alias(query: str, alias: str) -> bool:
    if alias.isascii():
        return re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", query, re.IGNORECASE) is not None
    return alias in query


def match_query_entities(query: str, limit: int = 8) -> list[EntityMatch]:
    """Link explicit Thai/English query mentions to the curated MVP entity set."""
    if not query.strip():
        raise ValueError("Query must not be empty")
    matches: list[EntityMatch] = []
    for entity in ENTITIES:
        mentions = [alias for alias in entity.aliases if _find_alias(query, alias)]
        if not mentions:
            continue
        matches.append(
            EntityMatch(
                entity_id=entity.entity_id,
                name=entity.name,
                entity_type=entity.entity_type,
                mention=max(mentions, key=len),
            )
        )
    return sorted(matches, key=lambda match: (-len(match.mention), match.entity_id))[:limit]


class Neo4jGraphRepository:
    """Recover evidence chunks from bounded semantic paths in Neo4j."""

    _SEMANTIC_QUERY = """
    UNWIND $entity_ids AS entity_id
    MATCH (start:Entity {entity_id: entity_id})
    MATCH path = (start)-[edges:%s*1..%d]-(related:Entity)
    UNWIND relationships(path) AS evidence
    MATCH (chunk:Chunk {chunk_id: evidence.source_chunk_id})
    WHERE ($language IS NULL OR chunk.language = $language)
      AND ($topic IS NULL OR chunk.topic = $topic)
    RETURN DISTINCT chunk { .* } AS chunk,
           start.entity_id AS start_entity_id,
           [node IN nodes(path) | node.entity_id] AS entity_path,
           [edge IN relationships(path) | type(edge)] AS relationships,
           length(path) AS depth,
           coalesce(evidence.confidence, 0.5) AS confidence
    ORDER BY confidence DESC, depth ASC, chunk.chunk_id ASC
    LIMIT $candidate_limit
    """

    _MENTION_QUERY = """
    UNWIND $entity_ids AS entity_id
    MATCH (start:Entity {entity_id: entity_id})-[:MENTIONED_IN]->(chunk:Chunk)
    WHERE ($language IS NULL OR chunk.language = $language)
      AND ($topic IS NULL OR chunk.topic = $topic)
    RETURN DISTINCT chunk { .* } AS chunk,
           start.entity_id AS start_entity_id,
           [start.entity_id] AS entity_path,
           [] AS relationships,
           0 AS depth,
           0.35 AS confidence
    ORDER BY chunk.chunk_id ASC
    LIMIT $candidate_limit
    """

    def __init__(self, driver: Any, database: str = "neo4j") -> None:
        self.driver = driver
        self.database = database

    def close(self) -> None:
        self.driver.close()

    @staticmethod
    def _records(result: Any) -> list[Any]:
        return list(result.records if hasattr(result, "records") else result[0])

    @staticmethod
    def _candidate(record: Any) -> GraphCandidate:
        return GraphCandidate(
            chunk=dict(record["chunk"]),
            start_entity_id=str(record["start_entity_id"]),
            entity_path=tuple(record["entity_path"]),
            relationships=tuple(record["relationships"]),
            depth=int(record["depth"]),
            confidence=float(record["confidence"]),
        )

    def find_candidates(
        self,
        entity_ids: list[str],
        *,
        max_depth: int,
        language: str | None,
        topic: str | None,
        candidate_limit: int,
    ) -> list[GraphCandidate]:
        if not 1 <= max_depth <= 3:
            raise ValueError("max_depth must be between 1 and 3")
        relationship_types = "|".join(sorted(RELATION_TYPES))
        parameters = {
            "entity_ids": entity_ids,
            "language": language,
            "topic": topic,
            "candidate_limit": candidate_limit,
        }
        semantic_result = self.driver.execute_query(
            self._SEMANTIC_QUERY % (relationship_types, max_depth),
            parameters_=parameters,
            database_=self.database,
            routing_="r",
        )
        mention_result = self.driver.execute_query(
            self._MENTION_QUERY,
            parameters_=parameters,
            database_=self.database,
            routing_="r",
        )
        return [
            self._candidate(record)
            for record in [*self._records(semantic_result), *self._records(mention_result)]
        ]


class InMemoryGraphRepository:
    """Deterministic offline repository for tests and corpus smoke checks."""

    def __init__(self, records: list[GraphRecord]) -> None:
        self.chunks: dict[str, dict[str, Any]] = {}
        self.mentions: defaultdict[str, set[str]] = defaultdict(set)
        self.adjacency: defaultdict[str, list[tuple[str, str, str, float]]] = defaultdict(list)
        for record in records:
            chunk_id = str(record.chunk["chunk_id"])
            self.chunks[chunk_id] = record.chunk
            for entity in record.entities:
                self.mentions[entity.entity_id].add(chunk_id)
            for fact in record.facts:
                edge = (fact.target_id, fact.relation, fact.source_chunk_id, fact.confidence)
                reverse = (fact.source_id, fact.relation, fact.source_chunk_id, fact.confidence)
                self.adjacency[fact.source_id].append(edge)
                self.adjacency[fact.target_id].append(reverse)

    @staticmethod
    def _allowed(chunk: dict[str, Any], language: str | None, topic: str | None) -> bool:
        return (language is None or chunk.get("language") == language) and (
            topic is None or chunk.get("topic") == topic
        )

    def find_candidates(
        self,
        entity_ids: list[str],
        *,
        max_depth: int,
        language: str | None,
        topic: str | None,
        candidate_limit: int,
    ) -> list[GraphCandidate]:
        if not 1 <= max_depth <= 3:
            raise ValueError("max_depth must be between 1 and 3")
        candidates: list[GraphCandidate] = []
        for start_entity_id in entity_ids:
            for chunk_id in sorted(self.mentions[start_entity_id]):
                chunk = self.chunks[chunk_id]
                if self._allowed(chunk, language, topic):
                    candidates.append(
                        GraphCandidate(
                            chunk=chunk,
                            start_entity_id=start_entity_id,
                            entity_path=(start_entity_id,),
                            relationships=(),
                            depth=0,
                            confidence=0.35,
                        )
                    )

            queue = deque([(start_entity_id, (start_entity_id,), ())])
            while queue:
                current, entity_path, relationships = queue.popleft()
                if len(relationships) >= max_depth:
                    continue
                for target, relation, chunk_id, confidence in sorted(self.adjacency[current]):
                    if target in entity_path:
                        continue
                    next_path = (*entity_path, target)
                    next_relationships = (*relationships, relation)
                    chunk = self.chunks.get(chunk_id)
                    if chunk is not None and self._allowed(chunk, language, topic):
                        candidates.append(
                            GraphCandidate(
                                chunk=chunk,
                                start_entity_id=start_entity_id,
                                entity_path=next_path,
                                relationships=next_relationships,
                                depth=len(next_relationships),
                                confidence=confidence,
                            )
                        )
                    queue.append((target, next_path, next_relationships))

        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.depth == 0,
                -candidate.confidence,
                candidate.depth,
                str(candidate.chunk.get("chunk_id")),
            ),
        )[: candidate_limit * 2]


class GraphRetriever:
    """Link a query to graph entities and rank provenance-preserving evidence."""

    def __init__(self, repository: GraphRepository, max_per_document: int = 2) -> None:
        if max_per_document < 1:
            raise ValueError("max_per_document must be positive")
        self.repository = repository
        self.max_per_document = max_per_document

    def close(self) -> None:
        """Close the backing service when it owns a long-lived connection."""
        close = getattr(self.repository, "close", None)
        if close is not None:
            close()

    @staticmethod
    def _score(candidate: GraphCandidate) -> float:
        if candidate.depth == 0:
            return candidate.confidence
        return candidate.confidence / (1 + 0.2 * (candidate.depth - 1))

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        max_depth: int = 2,
        language: str | None = None,
        topic: str | None = None,
    ) -> list[dict[str, Any]]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        if not 1 <= max_depth <= 3:
            raise ValueError("max_depth must be between 1 and 3")
        matches = match_query_entities(query)
        if not matches:
            return []
        match_by_id = {match.entity_id: match for match in matches}
        candidates = self.repository.find_candidates(
            list(match_by_id),
            max_depth=max_depth,
            language=language,
            topic=topic,
            candidate_limit=max(top_k * 10, 50),
        )

        aggregated: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            chunk_id = str(candidate.chunk.get("chunk_id") or "")
            content = str(candidate.chunk.get("content") or "")
            if not chunk_id or not content.strip():
                continue
            score = self._score(candidate)
            current = aggregated.get(chunk_id)
            if current is None:
                current = {
                    **candidate.chunk,
                    "graph_score": score,
                    "matched_entity_ids": set(),
                    "matched_entities": set(),
                    "relationships": set(),
                    "entity_path": list(candidate.entity_path),
                    "graph_depth": candidate.depth,
                }
                aggregated[chunk_id] = current
            match = match_by_id.get(candidate.start_entity_id)
            current["matched_entity_ids"].add(candidate.start_entity_id)
            current["matched_entities"].add(match.name if match else candidate.start_entity_id)
            current["relationships"].update(candidate.relationships)
            if score > current["graph_score"]:
                current["graph_score"] = score
                current["entity_path"] = list(candidate.entity_path)
                current["graph_depth"] = candidate.depth

        ranked = sorted(
            aggregated.values(),
            key=lambda row: (-row["graph_score"], str(row.get("chunk_id"))),
        )
        selected: list[dict[str, Any]] = []
        document_counts: defaultdict[str, int] = defaultdict(int)
        for row in ranked:
            document_id = str(row.get("document_id") or row["chunk_id"])
            if document_counts[document_id] >= self.max_per_document:
                continue
            row["matched_entity_ids"] = sorted(row["matched_entity_ids"])
            row["matched_entities"] = sorted(row["matched_entities"])
            row["relationships"] = sorted(row["relationships"])
            selected.append(row)
            document_counts[document_id] += 1
            if len(selected) == top_k:
                break
        return selected
