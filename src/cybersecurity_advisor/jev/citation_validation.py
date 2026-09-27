"""Deterministic citation checks plus batched JEV semantic validation."""

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from cybersecurity_advisor.jev.entity_validation import (
    JevResponseError,
    JevUnavailableError,
)

Verdict = Literal["supports", "contradicts", "says_nothing", "uncertain"]
ClaimStatus = Literal[
    "verified", "reject", "unsupported", "review", "uncited", "invalid_citation"
]

_CITATION = re.compile(r"\[([A-Za-z]+\d+)\]", re.IGNORECASE)
_SPLIT = re.compile(r"(?<=[.!?。！？])(?:\s+|$)|\n+")
_LIST_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
_META = ("insufficient evidence", "not enough evidence", "ไม่มีข้อมูลเพียงพอ")
_VERDICTS: dict[Verdict, str] = {
    "supports": "The source directly supports the factual claim.",
    "contradicts": "The source directly conflicts with the factual claim.",
    "says_nothing": "The source does not address the factual claim.",
    "uncertain": "The relationship cannot be determined from the source alone.",
}


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    citation_ids: list[str]


@dataclass(frozen=True)
class CitationJudgment:
    source_id: str
    verdict: Verdict
    confidence: float
    probabilities: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "probabilities": self.probabilities,
        }


@dataclass(frozen=True)
class ValidatedClaim:
    claim_id: str
    claim: str
    citation_ids: list[str]
    status: ClaimStatus
    judgments: list[CitationJudgment]
    errors: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim": self.claim,
            "citation_ids": self.citation_ids,
            "status": self.status,
            "judgments": [judgment.as_dict() for judgment in self.judgments],
            "errors": self.errors,
        }


@dataclass(frozen=True)
class CitationValidationResult:
    claims: list[ValidatedClaim]
    model: str

    def summary(self) -> dict[str, Any]:
        counts = Counter(claim.status for claim in self.claims)
        total = len(self.claims)
        cited = sum(bool(claim.citation_ids) for claim in self.claims)
        verified = counts["verified"]
        return {
            "model": self.model,
            "total_claims": total,
            "cited_claims": cited,
            "verified_claims": verified,
            "unsupported_claims": (
                counts["unsupported"] + counts["uncited"] + counts["invalid_citation"]
            ),
            "contradiction_count": counts["reject"],
            "citation_coverage": cited / total if total else 1.0,
            "groundedness": verified / total if total else 1.0,
            "status_counts": dict(counts),
            "claims": [claim.as_dict() for claim in self.claims],
        }


def extract_claims(answer: str) -> list[Claim]:
    """Extract citation-bearing sentence/line claims without another model call."""
    claims: list[Claim] = []
    for segment in _SPLIT.split(answer):
        original = _LIST_PREFIX.sub("", segment).strip()
        citation_ids = list(dict.fromkeys(item.upper() for item in _CITATION.findall(original)))
        text = re.sub(r"\s+([.!?,;:。！？])", r"\1", _CITATION.sub("", original)).strip()
        if not text or original.startswith("#") or (not citation_ids and text.endswith(":")):
            continue
        if any(marker in text.casefold() for marker in _META):
            continue
        # ponytail: rule-based segmentation is the MVP ceiling; replace only if evals miss claims.
        claims.append(Claim(f"claim-{len(claims) + 1:03d}", text, citation_ids))
    return claims


class JevCitationValidator:
    """Validate cited claim/source pairs in one typed System One request."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        model: str = "jev-latest",
        min_confidence: float = 0.7,
    ) -> None:
        if not model.strip():
            raise ValueError("JEV model must not be empty")
        if not 0 <= min_confidence <= 1:
            raise ValueError("JEV citation confidence must be between 0 and 1")
        self.client = client
        self.model = model
        self.min_confidence = min_confidence

    def close(self) -> None:
        self.client.close()

    @staticmethod
    def _probability(value: Any, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise JevResponseError(f"JEV returned a non-numeric {field}")
        probability = float(value)
        if not 0 <= probability <= 1:
            raise JevResponseError(f"JEV returned {field} outside 0..1")
        return probability

    @staticmethod
    def _source_is_valid(source: dict[str, Any]) -> bool:
        return all(source.get(field) for field in ("source_id", "chunk_id", "url", "evidence_text"))

    @staticmethod
    def _question(claim: Claim, source: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "choice",
            "instructions": {
                "task": "Determine whether the cited source supports the factual claim.",
                "claim": claim.text,
                "source": {
                    "source_id": source["source_id"],
                    "text": source["evidence_text"],
                },
            },
            "criteria": _VERDICTS,
        }

    def _status(self, judgments: list[CitationJudgment]) -> ClaimStatus:
        if any(judgment.verdict == "contradicts" for judgment in judgments):
            return "reject"
        if any(
            judgment.verdict == "supports" and judgment.confidence >= self.min_confidence
            for judgment in judgments
        ):
            return "verified"
        if judgments and all(judgment.verdict == "says_nothing" for judgment in judgments):
            return "unsupported"
        return "review"

    def validate(
        self, answer: str, sources: list[dict[str, Any]]
    ) -> CitationValidationResult:
        """Give every extracted claim a deterministic or semantic validation status."""
        claims = extract_claims(answer)
        source_by_id = {str(source.get("source_id")): source for source in sources}
        pending: list[tuple[Claim, str]] = []
        completed: dict[str, ValidatedClaim] = {}
        for claim in claims:
            if not claim.citation_ids:
                completed[claim.claim_id] = ValidatedClaim(
                    claim.claim_id, claim.text, [], "uncited", [], ["missing_citation"]
                )
                continue
            invalid = [
                source_id
                for source_id in claim.citation_ids
                if source_id not in source_by_id
                or not self._source_is_valid(source_by_id[source_id])
            ]
            if invalid:
                completed[claim.claim_id] = ValidatedClaim(
                    claim.claim_id,
                    claim.text,
                    claim.citation_ids,
                    "invalid_citation",
                    [],
                    [f"invalid_source:{source_id}" for source_id in invalid],
                )
                continue
            pending.extend((claim, source_id) for source_id in claim.citation_ids)

        if not pending:
            ordered = [completed[claim.claim_id] for claim in claims]
            return CitationValidationResult(ordered, self.model)

        payload = {
            "state": {"answer": answer},
            "model": self.model,
            "questions": {
                f"pair_{index}": self._question(claim, source_by_id[source_id])
                for index, (claim, source_id) in enumerate(pending)
            },
        }
        try:
            response = self.client.post("/v1/systemone", json=payload)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as error:
            raise JevUnavailableError(
                f"JEV request failed with status {error.response.status_code}"
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise JevUnavailableError("JEV service is unavailable") from error

        try:
            model = str(body["model"])
            judgments_by_claim: dict[str, list[CitationJudgment]] = {}
            for index, (claim, source_id) in enumerate(pending):
                answer_data = body["answers"][f"pair_{index}"]
                verdict = answer_data["choice"]
                if answer_data["type"] != "choice" or verdict not in _VERDICTS:
                    raise JevResponseError("JEV returned an invalid citation verdict")
                judgment = CitationJudgment(
                    source_id=source_id,
                    verdict=verdict,
                    confidence=self._probability(answer_data["confidence"], "confidence"),
                    probabilities={
                        label: self._probability(answer_data["probabilities"][label], label)
                        for label in _VERDICTS
                    },
                )
                judgments_by_claim.setdefault(claim.claim_id, []).append(judgment)
        except (KeyError, TypeError) as error:
            raise JevResponseError("JEV returned an incomplete citation verdict") from error

        for claim in claims:
            if claim.claim_id not in completed:
                judgments = judgments_by_claim[claim.claim_id]
                completed[claim.claim_id] = ValidatedClaim(
                    claim.claim_id,
                    claim.text,
                    claim.citation_ids,
                    self._status(judgments),
                    judgments,
                    [],
                )
        return CitationValidationResult(
            [completed[claim.claim_id] for claim in claims], model
        )
