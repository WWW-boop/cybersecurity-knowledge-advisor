# Data workspace

The team has not approved the source-document set yet. Keep this directory as a controlled
boundary rather than a general file dump.

- `source_manifest.example.json`: copy and review before enabling real sources.
- `raw/`: downloaded originals; ignored by Git.
- `processed/`: normalized documents; ignored by Git.
- `chunks/`: generated chunks; ignored by Git.
- `graph/`: graph export/intermediate files; ignored by Git.
- `evaluation/`: small, reviewed evaluation records that may be versioned deliberately.

Every real document must have a stable `document_id`, canonical URL, organization, language,
retrieval date, content hash, rights/licensing note, and review status. Do not ingest a source
merely because it appears in the implementation plan.
