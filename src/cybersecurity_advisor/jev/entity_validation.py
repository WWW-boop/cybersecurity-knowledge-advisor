"""JEV-backed validation of query mentions against curated graph entities."""

from typing import Any

import httpx

from cybersecurity_advisor.graph.retrieval import EntityMatch, EntityValidation


class JevError(RuntimeError):
    """Base error for unavailable or invalid JEV decisions."""


class JevUnavailableError(JevError):
    """The JEV service could not return a successful response."""


class JevResponseError(JevError):
    """The JEV response did not match the requested typed decision."""


class JevEntityValidator:
    """Validate all matched entities in one TypeSafe System One request."""

    _CRITERIA = {
        "same": (
            "The mention in the query refers to this specific candidate graph entity in context."
        ),
        "different": (
            "The mention refers to another concept, or the candidate conflicts "
            "with the query context."
        ),
        "uncertain": "The context is insufficient or genuinely ambiguous.",
    }

    def __init__(self, client: httpx.Client, model: str = "jev-latest") -> None:
        if not model.strip():
            raise ValueError("JEV model must not be empty")
        self.client = client
        self.model = model

    def close(self) -> None:
        """Release the owned HTTP connection pool."""
        self.client.close()

    @staticmethod
    def _question(match: EntityMatch) -> dict[str, Any]:
        return {
            "type": "choice",
            "instructions": {
                "task": "Validate whether the query mention maps to the candidate entity.",
                "mention": match.mention,
                "candidate": {
                    "entity_id": match.entity_id,
                    "name": match.name,
                    "type": match.entity_type,
                },
            },
            "criteria": JevEntityValidator._CRITERIA,
        }

    @staticmethod
    def _parse_probability(value: Any, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise JevResponseError(f"JEV returned a non-numeric {field}")
        probability = float(value)
        if not 0 <= probability <= 1:
            raise JevResponseError(f"JEV returned {field} outside 0..1")
        return probability

    def validate(self, query: str, matches: list[EntityMatch]) -> list[EntityValidation]:
        """Return one typed same/different/uncertain decision per candidate."""
        if not matches:
            return []
        payload = {
            "state": {"query": query},
            "model": self.model,
            "questions": {
                f"entity_{index}": self._question(match) for index, match in enumerate(matches)
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
            answers = body["answers"]
            decisions = []
            for index, match in enumerate(matches):
                answer = answers[f"entity_{index}"]
                if answer["type"] != "choice":
                    raise JevResponseError("JEV returned a non-choice entity decision")
                decision = answer["choice"]
                if decision not in self._CRITERIA:
                    raise JevResponseError("JEV returned an unsupported entity decision")
                probabilities = {
                    label: self._parse_probability(answer["probabilities"][label], label)
                    for label in self._CRITERIA
                }
                decisions.append(
                    EntityValidation(
                        match=match,
                        decision=decision,
                        confidence=self._parse_probability(answer["confidence"], "confidence"),
                        probabilities=probabilities,
                        model=model,
                    )
                )
        except (KeyError, TypeError) as error:
            raise JevResponseError("JEV returned an incomplete entity decision") from error
        return decisions
