# Ollama model benchmark analysis

## Setup

- Hardware: NVIDIA GeForce RTX 3050 Laptop GPU, 6 GB VRAM
- Models: `qwen3.5:4b`, `gemma3:4b`, `llama3.2:3b`
- Questions: 6 total (2 Thai, 2 English, 2 cross-language)
- Retrieval: identical Hybrid RAG context, RRF, Top-K 5, JEV disabled for this baseline
- Generation: temperature 0, seed 42, context 4096, maximum output 300 tokens

## System results

| Model | Avg latency | Tokens/s | Model VRAM | Completed | Valid citation |
|---|---:|---:|---:|---:|---:|
| qwen3.5:4b | 7.16 s | 36.9 | 2,983 MiB | 5/6 | 6/6 |
| gemma3:4b | 7.04 s | 41.0 | 2,742 MiB | 6/6 | 6/6 |
| llama3.2:3b | 5.48 s | 52.7 | 2,436 MiB | 3/6 | 6/6 |

All three models ran fully in GPU memory and answered in the language of the question.

## Qualitative review

`qwen3.5:4b` gave the strongest overall answers and preserved actionable meaning most
consistently. One long backup answer reached the 300-token limit, and some answers included more
background than the question needed.

`gemma3:4b` was concise and slightly faster, but one Thai incident-response answer inverted a
safety-critical instruction: it said to turn airplane mode off instead of turning it on. This
single error prevents selecting it as the default without a larger review.

`llama3.2:3b` was fastest and used the least VRAM, but three of six answers reached the output
limit and ended incomplete. It is a good low-latency fallback, not the best default for this RAG
workflow at the tested settings.

## Decision

Use `qwen3.5:4b` as the provisional local baseline. Confirm the decision on a reviewed 20–30
question generation set before treating it as final project evidence. Keep `llama3.2:3b` as the
speed baseline and `gemma3:4b` as a comparison model.
