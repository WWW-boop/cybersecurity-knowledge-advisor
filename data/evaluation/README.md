# Evaluation data

Store only reviewed, intentionally versioned evaluation records here. Each record should
identify its reviewer, language, expected evidence, and dataset version.

`retrieval_questions.seed.jsonl` is a draft smoke-test set, not final project evidence. A human
reviewer must verify every expected source and change `review_status` before its scores are used
in the report.

Run the three-model comparison and generate JSON, CSV, and a Matplotlib PNG with:

```powershell
uv run python scripts/benchmark_embeddings.py
```

To use the repository-local CUDA PyTorch installation:

```powershell
$env:PYTHONPATH = ".training-site"
uv run python scripts/benchmark_embeddings.py --device cuda --resume
```

The generated `model-benchmark/comparison.png`, `summary.csv`, and `results.json` contain the
GPU comparison. `--resume` reuses compatible per-model checkpoints.

Compare Ollama answer-generation models on the exact same Hybrid RAG context with:

```powershell
uv run uvicorn cybersecurity_advisor.api.main:app
# In another terminal:
uv run python scripts/benchmark_ollama_models.py
```

The benchmark writes `ollama-benchmark/results.json`, `summary.csv`, `manual_review.csv`, and a
Matplotlib `comparison.png`. Automatic metrics cover latency, throughput, language matching, and
citation syntax. Fill in the manual review scores before deciding which answer is most correct.
