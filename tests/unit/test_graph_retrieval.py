"""Graph entity linking, bounded traversal, and ranking tests."""

from cybersecurity_advisor.graph.retrieval import (
    EntityValidation,
    GraphCandidate,
    GraphRetriever,
    InMemoryGraphRepository,
    Neo4jGraphRepository,
    match_query_entities,
)


def candidate(
    chunk_id: str,
    document_id: str,
    *,
    start_entity_id: str = "threat:phishing",
    depth: int = 1,
    confidence: float = 0.8,
) -> GraphCandidate:
    return GraphCandidate(
        chunk={
            "chunk_id": chunk_id,
            "document_id": document_id,
            "content": f"Evidence for {chunk_id}",
            "citation": f"Citation {chunk_id}",
            "url": f"https://example.com/{chunk_id}",
            "language": "en",
            "topic": "phishing",
        },
        start_entity_id=start_entity_id,
        entity_path=("threat:phishing", "control:mfa"),
        relationships=("MITIGATED_BY",),
        depth=depth,
        confidence=confidence,
    )


class FakeRepository:
    def __init__(self, candidates: list[GraphCandidate]) -> None:
        self.candidates = candidates
        self.call = None

    def find_candidates(self, entity_ids: list[str], **kwargs) -> list[GraphCandidate]:
        self.call = (entity_ids, kwargs)
        return self.candidates


class FakeEntityValidator:
    def __init__(self, decisions: dict[str, tuple[str, float]]) -> None:
        self.decisions = decisions

    def validate(self, query, matches):
        assert query
        return [
            EntityValidation(
                match=match,
                decision=self.decisions[match.entity_id][0],
                confidence=self.decisions[match.entity_id][1],
                probabilities={"same": 0.8, "different": 0.1, "uncertain": 0.1},
                model="jev-test",
            )
            for match in matches
        ]


class FakeDriver:
    def __init__(self) -> None:
        self.calls = []

    def execute_query(self, query: str, **kwargs):
        self.calls.append((query, kwargs))
        if "MENTIONED_IN" in query:
            return ([], None, None)
        return (
            [
                {
                    "chunk": {
                        "chunk_id": "en-01-0001",
                        "document_id": "en-01",
                        "content": "Enable MFA after phishing.",
                        "citation": "CISA, MFA",
                        "url": "https://example.com/mfa",
                    },
                    "start_entity_id": "threat:phishing",
                    "entity_path": ["threat:phishing", "control:mfa"],
                    "relationships": ["MITIGATED_BY"],
                    "depth": 1,
                    "confidence": 0.8,
                }
            ],
            None,
            None,
        )


def test_matches_explicit_thai_and_english_entities() -> None:
    matches = match_query_entities("ถ้าโดน phishing แล้ว MFA ช่วยได้ไหม")

    assert {match.entity_id for match in matches} >= {"threat:phishing", "control:mfa"}
    assert all(match.mention for match in matches)


def test_returns_no_evidence_when_query_has_no_known_entity() -> None:
    repository = FakeRepository([])

    assert GraphRetriever(repository).search("อธิบายเรื่องที่ไม่อยู่ในกราฟ") == []
    assert repository.call is None


def test_validates_entities_before_traversal_and_exposes_decision() -> None:
    repository = FakeRepository(
        [
            candidate("phish-1", "document-a"),
            candidate("mfa-1", "document-b", start_entity_id="control:mfa"),
        ]
    )
    validator = FakeEntityValidator(
        {
            "threat:phishing": ("different", 0.95),
            "control:mfa": ("same", 0.91),
        }
    )

    rows = GraphRetriever(repository, entity_validator=validator).search("phishing and MFA")

    assert repository.call[0] == ["control:mfa"]
    assert [row["chunk_id"] for row in rows] == ["mfa-1"]
    assert rows[0]["entity_validations"] == [
        {
            "entity_id": "control:mfa",
            "name": "Multi-Factor Authentication",
            "entity_type": "AuthenticationMethod",
            "mention": "MFA",
            "decision": "same",
            "confidence": 0.91,
            "probabilities": {"same": 0.8, "different": 0.1, "uncertain": 0.1},
            "model": "jev-test",
        }
    ]


def test_skips_traversal_when_same_decision_is_below_threshold() -> None:
    repository = FakeRepository([])
    validator = FakeEntityValidator({"threat:phishing": ("same", 0.49)})

    rows = GraphRetriever(
        repository,
        entity_validator=validator,
        entity_min_confidence=0.7,
    ).search("phishing")

    assert rows == []
    assert repository.call is None


def test_ranks_deduplicates_and_limits_each_document() -> None:
    repository = FakeRepository(
        [
            candidate("a-1", "document-a", confidence=0.9),
            candidate("a-1", "document-a", depth=2, confidence=0.7),
            candidate("a-2", "document-a", confidence=0.8),
            candidate("a-3", "document-a", confidence=0.7),
            candidate("b-1", "document-b", depth=0, confidence=0.35),
        ]
    )

    rows = GraphRetriever(repository, max_per_document=2).search(
        "phishing",
        top_k=4,
        max_depth=2,
        language="en",
    )

    assert [row["chunk_id"] for row in rows] == ["a-1", "a-2", "b-1"]
    assert rows[0]["graph_score"] == 0.9
    assert rows[0]["relationships"] == ["MITIGATED_BY"]
    assert rows[0]["matched_entities"] == ["Phishing"]
    assert repository.call == (
        ["threat:phishing"],
        {
            "max_depth": 2,
            "language": "en",
            "topic": None,
            "candidate_limit": 50,
        },
    )


def test_neo4j_repository_uses_bounded_semantic_relationships() -> None:
    driver = FakeDriver()
    repository = Neo4jGraphRepository(driver)

    rows = repository.find_candidates(
        ["threat:phishing"],
        max_depth=2,
        language="en",
        topic="phishing",
        candidate_limit=20,
    )

    assert len(rows) == 1
    assert rows[0].chunk["chunk_id"] == "en-01-0001"
    assert len(driver.calls) == 2
    semantic_query, kwargs = driver.calls[0]
    assert "*1..2" in semantic_query
    assert "MITIGATED_BY" in semantic_query
    assert kwargs["parameters_"]["language"] == "en"
    assert kwargs["parameters_"]["candidate_limit"] == 20


def test_in_memory_repository_traverses_real_graph_records() -> None:
    from cybersecurity_advisor.graph.construction import extract_graph_record

    record = extract_graph_record(
        {
            "chunk_id": "en-01-0007",
            "document_id": "en-01",
            "source_id": "EN-01",
            "source": "CISA",
            "title": "Recognize and Report Phishing",
            "section": "Protection",
            "language": "en",
            "topic": "phishing",
            "citation": "CISA, Protection",
            "url": "https://example.com/phishing",
            "content": "Multi-factor authentication protects your account from phishing.",
        }
    )

    rows = GraphRetriever(InMemoryGraphRepository([record])).search(
        "phishing",
        top_k=3,
        max_depth=2,
    )

    assert rows[0]["chunk_id"] == "en-01-0007"
    assert rows[0]["relationships"] == ["MITIGATED_BY", "PROTECTS"]
    assert rows[0]["graph_depth"] == 1
