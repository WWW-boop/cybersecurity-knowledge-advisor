"""Versioned evaluation-dataset contract and loader."""

import json
from pathlib import Path

import pytest

from cybersecurity_advisor.evaluation.dataset import load_evaluation_dataset

DATASET = Path(__file__).parents[2] / "data" / "evaluation" / "questions.v0.1.jsonl"


def test_loader_validates_records_and_rejects_duplicate_ids(tmp_path) -> None:
    row = {
        "question_id": "q001",
        "question": "How does MFA protect a stolen password?",
        "language": "en",
        "language_group": "en",
        "type": "password_mfa",
        "expected_topics": ["mfa"],
        "expected_entities": ["Multi-Factor Authentication"],
        "relevant_documents": ["EN-03"],
        "relevant_chunks": ["en-03-0001"],
        "reference_answer": "MFA requires another factor after the password.",
        "review_status": "reviewed",
        "reviewer": "reviewer@example.com",
        "dataset_version": "v0.1",
    }
    path = tmp_path / "questions.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    assert load_evaluation_dataset(path)[0].question_id == "q001"

    path.write_text("\n".join((json.dumps(row), json.dumps(row))), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate question_id q001"):
        load_evaluation_dataset(path)


def test_phase12_draft_has_30_questions_and_every_planned_category() -> None:
    questions = load_evaluation_dataset(DATASET)

    assert len(questions) == 30
    assert {question.language_group for question in questions} == {"th", "en", "cross"}
    assert {question.question_type for question in questions} == {
        "definition",
        "phishing",
        "password_mfa",
        "malware",
        "privacy",
        "scam",
        "incident_response",
        "multi_hop",
        "comparison",
    }
