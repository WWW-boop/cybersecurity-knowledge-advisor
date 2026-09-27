"""Evaluation review-queue helpers."""

from scripts.prepare_eval_review import source_from_chunk


def test_source_from_chunk_maps_chunk_to_dataset_document_label() -> None:
    assert source_from_chunk("en-10-0003") == "EN-10"
    assert source_from_chunk("invalid") == ""
