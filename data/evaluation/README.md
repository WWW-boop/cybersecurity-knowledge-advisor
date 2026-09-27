# Evaluation data

Store only reviewed, intentionally versioned evaluation records here. Each record should
identify its reviewer, language, expected evidence, and dataset version.

`retrieval_questions.seed.jsonl` is a draft smoke-test set, not final project evidence. A human
reviewer must verify every expected source and change `review_status` before its scores are used
in the report.

`questions.v0.1.jsonl` is the 30-question Phase 12 labeled-dataset draft. It covers every planned
question category and adds expected topics and entities, relevant documents/chunks, and a
reference answer. Records are validated by
`cybersecurity_advisor.evaluation.dataset.load_evaluation_dataset`. A record may be changed to
`review_status: "reviewed"` only after a reviewer is named and its relevant chunks are verified.

Run the no-JEV document-retrieval baseline after starting the API:

```powershell
$env:EMBEDDING_DEVICE = "cpu"  # omit when the project PyTorch build supports CUDA
uv run --no-sync uvicorn cybersecurity_advisor.api.main:app
# In another terminal:
uv run --no-sync python scripts/run_eval.py
```

The runner compares Dense, Graph, and Hybrid retrieval at K=5 and writes per-question results plus
Dynamic Hybrid results, JSON/CSV summaries, a Matplotlib chart, and a Markdown report. It performs
an untimed warm-up before measuring latency. Current scores use draft document labels and must not
be reported as final research results.

Run Local/API generation, Fixed/Dynamic, and JEV ablations with:

```powershell
uv run --no-sync python scripts/run_generation_eval.py
```

The runner exports automatic generation/system metrics, claim-groundedness metrics, token and
resource usage, API cost when price arguments are supplied, a manual-review sheet, and a Matplotlib
chart. JEV ablation overrides are rejected when `APP_ENV=production`.

Prepare the evidence-label review queue and combine the experiment artifacts with:

```powershell
uv run --no-sync python scripts/prepare_eval_review.py
uv run --no-sync python scripts/build_phase12_report.py
```

The review queue must be completed by a named human reviewer before changing dataset records from
`draft` to `reviewed`. Missing API credentials are recorded as `skipped`; the runner never invents
provider results.

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
