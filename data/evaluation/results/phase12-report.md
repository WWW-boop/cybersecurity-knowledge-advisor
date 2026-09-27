# Phase 12 evaluation report

> PRELIMINARY: retrieval labels and generated answers still require independent human review.

## Dataset

- Questions: 30 (Thai/English/cross-language)
- Human-reviewed records: 0/30
- Automatic reference-token F1 is a transparent proxy, not a human correctness score.

## Retrieval

| Method | Recall@5 | Precision@5 | MRR@5 | NDCG@5 | Avg latency (s) |
|---|---:|---:|---:|---:|---:|
| dense | 0.822 | 0.240 | 0.917 | 0.831 | 0.061 |
| graph | 0.256 | 0.087 | 0.256 | 0.220 | 0.253 |
| hybrid | 0.844 | 0.253 | 0.833 | 0.796 | 0.300 |
| hybrid_dynamic | 0.850 | 0.253 | 0.872 | 0.824 | 0.584 |

## Local generation: Qwen 3.5 4B + Dynamic Hybrid + all JEV

- Questions completed: 30
- Reference token F1: 0.263
- JEV groundedness: 0.752
- Citation coverage: 0.874
- Unsupported claim rate: 0.176
- Average latency: 15.298 seconds
- P95 latency: 22.061 seconds
- Average context: 544.1 tokens / 2.37 chunks
- Process RAM: 1917.2 MiB
- Ollama model VRAM: 2983.1 MiB

## JEV ablation smoke test

The eight Fixed/Dynamic x JEV configurations completed on one question. This proves the experiment paths run, but n=1 is not evidence of superiority.

| Experiment | Ref F1 | Groundedness | Context tokens | Latency (s) |
|---|---:|---:|---:|---:|
| ollama-none-fixed | 0.413 | N/A | 2640.000 | 10.356 |
| ollama-none-dynamic | 0.361 | N/A | 2640.000 | 9.807 |
| ollama-pregen-fixed | 0.373 | N/A | 901.000 | 11.730 |
| ollama-pregen-dynamic | 0.580 | N/A | 901.000 | 8.176 |
| ollama-entity_pregen-fixed | 0.563 | N/A | 901.000 | 8.327 |
| ollama-entity_pregen-dynamic | 0.544 | N/A | 901.000 | 8.415 |
| ollama-all-fixed | 0.590 | 1.000 | 901.000 | 8.398 |
| ollama-all-dynamic | 0.590 | 1.000 | 901.000 | 8.487 |

## API LLM status

- skipped: HTTP 503: OpenAI credentials and model are not configured
- The runner supports API token/cost metrics once credentials and per-million-token prices are supplied.

## Preliminary interpretation

- Hybrid Dynamic had the highest Recall@5 and improved MRR over fixed Hybrid, but used more retrieval latency.
- Pre-generation JEV sharply reduced context in the smoke case, while citation JEV made claim-level groundedness measurable.
- Final Local-vs-API and ablation conclusions are blocked by missing API credentials and incomplete human review, not by missing evaluation code.
