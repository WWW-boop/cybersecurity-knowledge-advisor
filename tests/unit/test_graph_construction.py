"""Knowledge-graph extraction and persistence tests."""

from cybersecurity_advisor.graph.construction import Neo4jGraphStore, extract_graph_record


class FakeDriver:
    def __init__(self) -> None:
        self.calls = []

    def execute_query(self, query: str, **parameters) -> None:
        self.calls.append((query, parameters))


def test_extracts_semantic_facts_with_chunk_provenance() -> None:
    record = extract_graph_record(
        {
            "chunk_id": "en-01-0007",
            "document_id": "en-01",
            "source_id": "EN-01",
            "source": "CISA",
            "title": "Recognize and Report Phishing",
            "section": "Response",
            "language": "en",
            "topic": "phishing",
            "citation": "CISA, Response",
            "url": "https://example.com/phishing",
            "content": "Report the phish and enable multi-factor authentication on your account.",
        }
    )

    assert {entity.entity_id for entity in record.entities} >= {
        "threat:phishing",
        "control:mfa",
        "asset:account",
        "action:report-phishing",
    }
    assert {(fact.relation, fact.target_id) for fact in record.facts} == {
        ("MITIGATED_BY", "control:mfa"),
        ("RESPONSE_ACTION", "action:report-phishing"),
        ("PROTECTS", "asset:account"),
    }
    assert all(fact.source_chunk_id == "en-01-0007" for fact in record.facts)


def test_store_creates_schema_and_typed_relationships() -> None:
    record = extract_graph_record(
        {
            "chunk_id": "en-12-0009",
            "document_id": "en-12",
            "source_id": "EN-12",
            "source": "CISA",
            "title": "Ransomware Guide",
            "section": "Backups",
            "language": "en",
            "topic": "ransomware",
            "citation": "CISA, Backups",
            "url": "https://example.com/ransomware",
            "content": "Maintain offline backups to reduce ransomware risk.",
        }
    )
    driver = FakeDriver()
    store = Neo4jGraphStore(driver)

    store.ensure_schema()
    counts = store.ingest([record])

    assert counts == (1, 1)
    assert len(driver.calls) == len(store.CONSTRAINTS) + 2
    relation_query, parameters = driver.calls[-1]
    assert "MITIGATED_BY" in relation_query
    assert parameters["facts"][0]["source_chunk_id"] == "en-12-0009"
