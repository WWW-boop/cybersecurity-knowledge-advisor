"""Validated, versioned evaluation-question dataset."""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class EvaluationQuestion(BaseModel):
    """One labeled question shared by retrieval and answer evaluation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    question_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    question: str = Field(min_length=1)
    language: Literal["th", "en"]
    language_group: Literal["th", "en", "cross"]
    question_type: Literal[
        "definition",
        "phishing",
        "password_mfa",
        "malware",
        "privacy",
        "scam",
        "incident_response",
        "multi_hop",
        "comparison",
    ] = Field(alias="type")
    expected_topics: list[str] = Field(min_length=1)
    expected_entities: list[str] = Field(default_factory=list)
    relevant_documents: list[str] = Field(min_length=1)
    relevant_chunks: list[str] = Field(default_factory=list)
    reference_answer: str = Field(min_length=1)
    review_status: Literal["draft", "reviewed"] = "draft"
    reviewer: str | None = None
    dataset_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_complete_review(self) -> Self:
        if self.review_status == "reviewed" and (not self.reviewer or not self.relevant_chunks):
            raise ValueError("reviewed records require reviewer and relevant_chunks")
        return self


def load_evaluation_dataset(path: Path) -> list[EvaluationQuestion]:
    """Load JSONL records and reject invalid rows or duplicate question IDs."""
    questions: list[EvaluationQuestion] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            question = EvaluationQuestion.model_validate_json(line)
        except ValidationError as error:
            raise ValueError(f"{path}:{line_number}: invalid evaluation record") from error
        if question.question_id in seen:
            raise ValueError(f"{path}:{line_number}: duplicate question_id {question.question_id}")
        seen.add(question.question_id)
        questions.append(question)
    if not questions:
        raise ValueError(f"{path}: evaluation dataset is empty")
    return questions
