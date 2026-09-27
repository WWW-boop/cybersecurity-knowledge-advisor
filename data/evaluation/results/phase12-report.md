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

## API comparison: GPT-4o Mini + Dynamic Hybrid + all JEV

- Questions completed: 30
- Reference token F1: 0.294
- JEV groundedness: 0.517
- Citation coverage: 0.656
- Unsupported claim rate: 0.389
- Average latency: 4.699 seconds
- P95 latency: 6.231 seconds
- Average context: 539.2 tokens / 2.30 chunks
- API cost remains N/A until project-approved per-token rates are supplied.

## Selected API: Qwen 3.6 Flash (3,000-token ceiling)

- Questions completed: 30
- Reference token F1: 0.218
- JEV groundedness: 0.658
- Citation coverage: 0.792
- Unsupported claim rate: 0.221
- Average latency: 15.072 seconds
- P95 latency: 20.743 seconds
- Average output tokens: 1789.8
- Runs at or above the 3,000-token ceiling: 0/30

## Preliminary interpretation

- Hybrid Dynamic had the highest Recall@5 and improved MRR over fixed Hybrid, but used more retrieval latency.
- Pre-generation JEV sharply reduced context in the smoke case, while citation JEV made claim-level groundedness measurable.
- The GPT-4o Mini comparator was about 3.3x faster and had slightly higher reference-token F1, but lower citation groundedness and coverage than the local baseline.
- The selected Qwen 3.6 API improved citation metrics over GPT-4o Mini but used about 7.7x more output tokens and had latency close to Local Qwen.
- Final quality conclusions remain blocked by incomplete human review, not by missing evaluation code or API execution.
