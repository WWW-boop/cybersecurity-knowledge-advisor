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

Re-run both commands after this feature upgrade so existing Chunk nodes receive their evidence
text. Then test bounded graph retrieval with:

```powershell
uv run python scripts/graph_retrieval.py "phishing and MFA" --max-depth 2 --top-k 5
```

When Neo4j is not running, use the same ranking logic against generated records:

```powershell
uv run python scripts/graph_retrieval.py "phishing and MFA" `
  --records data/graph/graph_records.jsonl --max-depth 2 --top-k 5
```

Normal retrieval also requires `JEV_API_KEY` (or `TYPE_SAFE`). Candidate entities are validated by
JEV before traversal, and only a `same` decision meeting `JEV_ENTITY_MIN_CONFIDENCE` proceeds. Use
`--skip-jev` only when running the no-JEV ablation baseline.

The API equivalents are `POST /api/v1/graph/entities/validate` for the typed entity-linking output
and `POST /api/v1/graph/retrieve` for validated graph evidence. Queries without a known curated
entity return an empty list; JEV or Neo4j failures return HTTP 503.

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
