# Data source selection

No source document is enabled until all three team members agree on its scope and a reviewer
records the decision. This prevents the retrieval and evaluation design from silently adapting
to a convenient but low-quality corpus.

## Selection checklist

For each source or document, record:

- stable ID, title, publisher, canonical URL, language, and retrieval date;
- authority and direct relevance to guidance for general users;
- publication/update date and a policy for detecting stale content;
- copyright, license, robots policy, and permission to store derived text;
- supported topics, expected audience, and geographic scope;
- available format and extraction difficulty;
- duplication or conflict with sources already selected;
- one named reviewer and an explicit approved/rejected status.

## Suggested decision process

1. Collect candidate URLs only; do not ingest them yet.
2. Review authority, scope, rights, freshness, and extraction quality.
3. Choose a small representative pilot set in both Thai and English.
4. Freeze corpus version `v0.1` and compute a SHA-256 hash per downloaded document.
5. Build and test ingestion against `v0.1` before expanding the corpus.
6. Split evaluation questions independently from retrieval implementation decisions.

## Manifest lifecycle

Copy `data/source_manifest.example.json` to a versioned manifest only after review. Source
definitions start with `enabled: false`; enabling a source is a reviewable pull-request change.
Raw files and generated artifacts remain local or in an agreed artifact store, not in Git.
