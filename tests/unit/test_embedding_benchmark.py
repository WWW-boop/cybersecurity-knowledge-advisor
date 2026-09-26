from scripts.benchmark_embeddings import rank_metrics, write_chart


def test_metrics_and_chart(tmp_path) -> None:
    assert rank_metrics(["wrong", "expected"], ["expected"]) == (1.0, 0.5)
    assert rank_metrics(["wrong"], ["expected"]) == (0.0, 0.0)

    output = tmp_path / "chart.png"
    write_chart(
        [
            {
                "name": name,
                "recall_at_5": score,
                "macro_recall_at_5": score,
                "mrr_at_5": score,
                "p95_query_latency_ms": 10 + index,
                "corpus_encode_seconds": 20 + index,
                "peak_device_memory_mib": 100 + index,
                "hardware": "Test GPU",
                "recall_at_5_by_language": {"th": score, "en": score, "cross": score},
                "chunks": 999,
                "questions": 15,
            }
            for index, (name, score) in enumerate(
                [("first", 1.0), ("second", 0.5), ("third", 0.25)]
            )
        ],
        output,
    )

    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
