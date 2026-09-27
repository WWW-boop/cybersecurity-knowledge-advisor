"""Create human-review queues for retrieval labels and generated answers."""

import argparse
import csv
import json
from pathlib import Path

from cybersecurity_advisor.evaluation.dataset import load_evaluation_dataset


def source_from_chunk(chunk_id: str) -> str:
    parts = chunk_id.split("-")
    return "-".join(parts[:2]).upper() if len(parts) >= 3 else ""


def build_rows(dataset: Path, retrieval_results: Path) -> list[dict[str, str]]:
    questions = load_evaluation_dataset(dataset)
    results = json.loads(retrieval_results.read_text(encoding="utf-8"))
    retrieved_by_question: dict[str, list[str]] = {}
    for result in results:
        retrieved_by_question.setdefault(result["question_id"], []).extend(
            result["retrieved_chunks"]
        )
    rows = []
    for question in questions:
        expected = set(question.relevant_documents)
        suggestions = list(
            dict.fromkeys(
                chunk_id
                for chunk_id in retrieved_by_question.get(question.question_id, [])
                if source_from_chunk(chunk_id) in expected
            )
        )
        rows.append(
            {
                "question_id": question.question_id,
                "question": question.question,
                "reference_answer": question.reference_answer,
                "expected_documents": "|".join(question.relevant_documents),
                "current_relevant_chunks": "|".join(question.relevant_chunks),
                "suggested_chunks_to_inspect": "|".join(suggestions),
                "approved_relevant_chunks": "",
                "reviewer": "",
                "decision": "",
                "notes": "",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/evaluation/questions.v0.1.jsonl")
    )
    parser.add_argument(
        "--retrieval-results",
        type=Path,
        default=Path("data/evaluation/results/retrieval-phase12/results.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/evaluation/results/dataset-review.csv")
    )
    args = parser.parse_args()
    rows = build_rows(args.dataset, args.retrieval_results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} review rows to {args.output}")


if __name__ == "__main__":
    main()
