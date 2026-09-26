"""Deterministic entity, relation, and provenance extraction for the MVP graph."""

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EntityDefinition:
    entity_id: str
    entity_type: str
    name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class RelationRule:
    source_id: str
    relation: str
    target_id: str


@dataclass(frozen=True)
class GraphFact:
    fact_id: str
    source_id: str
    relation: str
    target_id: str
    source_chunk_id: str
    source_url: str
    confidence: float = 0.8


@dataclass(frozen=True)
class GraphRecord:
    chunk: dict[str, Any]
    entities: tuple[EntityDefinition, ...]
    facts: tuple[GraphFact, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk": self.chunk,
            "entities": [asdict(entity) for entity in self.entities],
            "facts": [asdict(fact) for fact in self.facts],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GraphRecord":
        return cls(
            chunk=value["chunk"],
            entities=tuple(EntityDefinition(**entity) for entity in value["entities"]),
            facts=tuple(GraphFact(**fact) for fact in value["facts"]),
        )


# ponytail: curated rules are the MVP ceiling; replace them with reviewed NER/RE only if
# evaluation shows that their recall is insufficient.
ENTITIES = (
    EntityDefinition("threat:phishing", "Threat", "Phishing", ("phishing", "ฟิชชิง")),
    EntityDefinition("threat:ransomware", "Threat", "Ransomware", ("ransomware", "แรนซัมแวร์")),
    EntityDefinition("threat:malware", "Threat", "Malware", ("malware", "มัลแวร์")),
    EntityDefinition(
        "threat:account-takeover",
        "Threat",
        "Account Takeover",
        ("account takeover", "hacked account", "บัญชีถูกยึด", "บัญชีถูกแฮ็ก"),
    ),
    EntityDefinition(
        "threat:identity-theft",
        "Threat",
        "Identity Theft",
        ("identity theft", "การขโมยข้อมูลส่วนบุคคล", "สวมรอย"),
    ),
    EntityDefinition(
        "control:mfa",
        "AuthenticationMethod",
        "Multi-Factor Authentication",
        (
            "multi-factor authentication",
            "multifactor authentication",
            "mfa",
            "2fa",
            "ยืนยันตัวตนสองชั้น",
        ),
    ),
    EntityDefinition(
        "control:offline-backup",
        "SecurityControl",
        "Offline Backup",
        ("offline backup", "offline backups", "สำรองข้อมูลแบบออฟไลน์"),
    ),
    EntityDefinition(
        "control:antivirus",
        "SecurityControl",
        "Antivirus",
        ("anti-virus", "antivirus", "โปรแกรมป้องกันไวรัส"),
    ),
    EntityDefinition(
        "control:password-manager",
        "SecurityControl",
        "Password Manager",
        ("password manager", "โปรแกรมจัดการรหัสผ่าน"),
    ),
    EntityDefinition(
        "control:software-update",
        "SecurityControl",
        "Software Update",
        ("software update", "update software", "อัปเดตซอฟต์แวร์"),
    ),
    EntityDefinition("asset:account", "Asset", "Account", ("account", "บัญชี")),
    EntityDefinition(
        "asset:credentials",
        "Asset",
        "Credentials",
        ("credential", "credentials", "password", "รหัสผ่าน"),
    ),
    EntityDefinition(
        "asset:personal-information",
        "Asset",
        "Personal Information",
        ("personal information", "personal data", "ข้อมูลส่วนบุคคล"),
    ),
    EntityDefinition("asset:device", "Asset", "Device", ("device", "computer", "อุปกรณ์")),
    EntityDefinition(
        "action:report-phishing",
        "Action",
        "Report Phishing",
        ("report phishing", "report the phish", "report a phish", "รายงานฟิชชิง"),
    ),
    EntityDefinition(
        "action:change-password",
        "Action",
        "Change Password",
        ("change password", "reset password", "เปลี่ยนรหัสผ่าน"),
    ),
    EntityDefinition(
        "action:scan-device",
        "Action",
        "Scan Device",
        ("run a scan", "scan your device", "สแกนอุปกรณ์"),
    ),
    EntityDefinition(
        "action:restore-backup",
        "Action",
        "Restore From Backup",
        ("restore from backup", "restore backups", "กู้คืนจากข้อมูลสำรอง"),
    ),
)

RELATIONS = (
    RelationRule("threat:phishing", "MITIGATED_BY", "control:mfa"),
    RelationRule("threat:phishing", "RESPONSE_ACTION", "action:report-phishing"),
    RelationRule("threat:phishing", "TARGETS", "asset:personal-information"),
    RelationRule("threat:ransomware", "MITIGATED_BY", "control:offline-backup"),
    RelationRule("threat:ransomware", "RESPONSE_ACTION", "action:restore-backup"),
    RelationRule("threat:malware", "MITIGATED_BY", "control:antivirus"),
    RelationRule("threat:malware", "TARGETS", "asset:device"),
    RelationRule("threat:account-takeover", "TARGETS", "asset:account"),
    RelationRule("threat:account-takeover", "RESPONSE_ACTION", "action:change-password"),
    RelationRule("threat:identity-theft", "TARGETS", "asset:personal-information"),
    RelationRule("control:mfa", "PROTECTS", "asset:account"),
    RelationRule("control:password-manager", "PROTECTS", "asset:credentials"),
    RelationRule("control:software-update", "PROTECTS", "asset:device"),
)

RELATION_TYPES = frozenset(rule.relation for rule in RELATIONS)


def _contains(text: str, alias: str) -> bool:
    if alias.isascii():
        return re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, re.IGNORECASE) is not None
    return alias in text


def extract_graph_record(chunk: dict[str, Any]) -> GraphRecord:
    """Extract normalized entities and supported semantic facts from one chunk."""
    content = str(chunk.get("content") or "")
    text = "\n".join(
        str(chunk.get(field) or "") for field in ("topic", "title", "section", "content")
    )
    entities = tuple(
        entity for entity in ENTITIES if any(_contains(text, alias) for alias in entity.aliases)
    )
    content_entity_ids = {
        entity.entity_id
        for entity in entities
        if any(_contains(content, alias) for alias in entity.aliases)
    }
    topic_threat_id = f"threat:{str(chunk.get('topic') or '').replace('_', '-')}"
    facts = tuple(
        GraphFact(
            fact_id=f"{rule.source_id}|{rule.relation}|{rule.target_id}|{chunk['chunk_id']}",
            source_id=rule.source_id,
            relation=rule.relation,
            target_id=rule.target_id,
            source_chunk_id=chunk["chunk_id"],
            source_url=chunk["url"],
        )
        for rule in RELATIONS
        if rule.target_id in content_entity_ids
        and (rule.source_id in content_entity_ids or rule.source_id == topic_threat_id)
    )
    return GraphRecord(
        chunk={
            key: chunk.get(key)
            for key in (
                "chunk_id",
                "document_id",
                "source_id",
                "source",
                "title",
                "section",
                "language",
                "topic",
                "citation",
                "url",
            )
        },
        entities=entities,
        facts=facts,
    )


class Neo4jGraphStore:
    """Persist graph records through an official Neo4j driver."""

    CONSTRAINTS = (
        "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.entity_id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.chunk_id IS UNIQUE",
        "CREATE CONSTRAINT document_id IF NOT EXISTS "
        "FOR (n:Document) REQUIRE n.document_id IS UNIQUE",
        "CREATE CONSTRAINT source_id IF NOT EXISTS FOR (n:Source) REQUIRE n.source_id IS UNIQUE",
        "CREATE INDEX entity_name IF NOT EXISTS FOR (n:Entity) ON (n.name)",
        "CREATE INDEX chunk_topic IF NOT EXISTS FOR (n:Chunk) ON (n.topic)",
    )

    RECORD_QUERY = """
    UNWIND $records AS record
    MERGE (source:Source {source_id: record.chunk.source_id})
      SET source.name = record.chunk.source
    MERGE (document:Document {document_id: record.chunk.document_id})
      SET document.title = record.chunk.title, document.url = record.chunk.url
    MERGE (chunk:Chunk {chunk_id: record.chunk.chunk_id})
      SET chunk += record.chunk
    MERGE (source)-[:PUBLISHED]->(document)
    MERGE (document)-[:HAS_CHUNK]->(chunk)
    WITH record, chunk
    UNWIND record.entities AS entity
    MERGE (node:Entity {entity_id: entity.entity_id})
      SET node.name = entity.name, node.entity_type = entity.entity_type
    MERGE (node)-[:MENTIONED_IN]->(chunk)
    """

    def __init__(self, driver: Any) -> None:
        self.driver = driver

    def ensure_schema(self) -> None:
        for query in self.CONSTRAINTS:
            self.driver.execute_query(query)

    def ingest(self, records: list[GraphRecord]) -> tuple[int, int]:
        values = [record.to_dict() for record in records]
        self.driver.execute_query(self.RECORD_QUERY, records=values)
        facts_by_type = {
            relation: [
                asdict(fact)
                for record in records
                for fact in record.facts
                if fact.relation == relation
            ]
            for relation in RELATION_TYPES
        }
        for relation, facts in facts_by_type.items():
            if not facts:
                continue
            self.driver.execute_query(
                f"""
                UNWIND $facts AS fact
                MATCH (source:Entity {{entity_id: fact.source_id}})
                MATCH (target:Entity {{entity_id: fact.target_id}})
                MERGE (source)-[edge:{relation} {{fact_id: fact.fact_id}}]->(target)
                  SET edge.source_chunk_id = fact.source_chunk_id,
                      edge.source_url = fact.source_url,
                      edge.confidence = fact.confidence
                """,
                facts=facts,
            )
        return len(records), sum(len(record.facts) for record in records)
