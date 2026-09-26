# Knowledge graph artifacts

Generated graph imports and exports belong here and are ignored by Git.

Extract deterministic MVP graph records from the reviewed chunk corpus:

```powershell
uv run python scripts/build_graph.py extract
```

After starting Neo4j and configuring `NEO4J_PASSWORD`, create constraints and ingest the records:

```powershell
uv run python scripts/build_graph.py ingest
```

Each semantic relationship stores `source_chunk_id`, `source_url`, and extraction confidence.
`graph_records.jsonl` is generated runtime data and is intentionally ignored by Git.

Schema:

- nodes: `Source`, `Document`, `Chunk`, and `Entity` with an `entity_type` such as `Threat`,
  `SecurityControl`, `AuthenticationMethod`, `Asset`, or `Action`;
- provenance: `Source-[:PUBLISHED]->Document-[:HAS_CHUNK]->Chunk` and
  `Entity-[:MENTIONED_IN]->Chunk`;
- semantic relationships: `MITIGATED_BY`, `PROTECTS`, `TARGETS`, and `RESPONSE_ACTION`.

Example verification query:

```cypher
MATCH (source:Entity)-[relation]->(target:Entity)
RETURN source.name, type(relation), target.name, relation.source_chunk_id
LIMIT 25;
```
