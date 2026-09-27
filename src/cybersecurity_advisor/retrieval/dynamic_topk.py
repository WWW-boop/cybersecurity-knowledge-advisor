"""Deterministic query analysis and Dynamic Top-K context selection."""

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

Intent = Literal["definition", "education", "prevention", "incident_response", "comparison"]

_DEFINITION = ("what is", "what are", "define", "meaning", "คืออะไร", "หมายถึง")
_COMPARISON = ("compare", "difference", " versus ", " vs ", "ต่างกัน", "เปรียบเทียบ")
_INCIDENT = (
    "after clicking",
    "compromised",
    "hacked",
    "recover",
    "respond",
    "ถูกแฮก",
    "โดนแฮก",
    "ถูกยึด",
    "กดลิงก์",
    "กู้คืน",
    "รับมือ",
)
_PREVENTION = ("prevent", "protect", "avoid", "secure", "ป้องกัน", "หลีกเลี่ยง", "ปลอดภัย")
_MULTI_HOP = (
    "relationship",
    "related",
    "why does",
    "how does",
    "เกี่ยวข้อง",
    "สัมพันธ์",
    "ทำไม",
    "เพราะเหตุใด",
)
_TOPICS = (
    "phishing",
    "mfa",
    "password",
    "malware",
    "ransomware",
    "privacy",
    "backup",
    "ฟิชชิง",
    "รหัสผ่าน",
    "มัลแวร์",
    "ความเป็นส่วนตัว",
)
_TOKEN = re.compile(r"[A-Za-z0-9_]+|[\u0E00-\u0E7F]|[^\s]")


@dataclass(frozen=True)
class QueryAnalysis:
    intent: Intent
    complexity: float
    multi_topic: bool
    multi_hop: bool


@dataclass(frozen=True)
class RetrievalBudget:
    intent: Intent
    complexity: float
    dense_k: int
    graph_k: int
    graph_depth: int
    fusion_k: int
    context_k_min: int
    context_k_max: int
    context_token_budget: int
    score_gap: float
    score_threshold: float

    def metadata(self, *, selected_context_k: int, estimated_context_tokens: int) -> dict[str, Any]:
        return {
            **asdict(self),
            "selected_context_k": selected_context_k,
            "estimated_context_tokens": estimated_context_tokens,
        }


def analyze_query(query: str) -> QueryAnalysis:
    """Classify enough query shape to choose a reproducible retrieval budget."""
    text = f" {query.casefold().strip()} "
    if any(marker in text for marker in _COMPARISON):
        intent: Intent = "comparison"
    elif any(marker in text for marker in _INCIDENT):
        intent = "incident_response"
    elif any(marker in text for marker in _DEFINITION):
        intent = "definition"
    elif any(marker in text for marker in _PREVENTION):
        intent = "prevention"
    else:
        intent = "education"

    topic_count = sum(marker in text for marker in _TOPICS)
    multi_topic = topic_count > 1 or text.count(" and ") + text.count(" และ") > 0
    multi_hop = intent == "comparison" or any(marker in text for marker in _MULTI_HOP)
    complexity = 0.2
    complexity += 0.25 if intent in {"comparison", "incident_response"} else 0
    complexity += 0.25 if multi_hop else 0
    complexity += 0.15 if multi_topic else 0
    complexity += 0.15 if len(query) > 100 else 0
    return QueryAnalysis(intent, min(complexity, 1.0), multi_topic, multi_hop)


def choose_retrieval_budget(query: str) -> RetrievalBudget:
    """Return bounded Dense, Graph, fusion, and final-context budgets."""
    analysis = analyze_query(query)
    common = {"intent": analysis.intent, "complexity": analysis.complexity}
    if analysis.multi_hop or analysis.complexity >= 0.75:
        return RetrievalBudget(
            **common,
            dense_k=20,
            graph_k=15,
            graph_depth=3,
            fusion_k=25,
            context_k_min=2,
            context_k_max=6,
            context_token_budget=5000,
            score_gap=0.30,
            score_threshold=0.15,
        )
    if analysis.intent in {"comparison", "incident_response"}:
        return RetrievalBudget(
            **common,
            dense_k=15,
            graph_k=12,
            graph_depth=2,
            fusion_k=25,
            context_k_min=2,
            context_k_max=6,
            context_token_budget=4000,
            score_gap=0.28,
            score_threshold=0.15,
        )
    if analysis.intent == "definition":
        return RetrievalBudget(
            **common,
            dense_k=5,
            graph_k=5,
            graph_depth=1,
            fusion_k=10,
            context_k_min=2,
            context_k_max=3,
            context_token_budget=1600,
            score_gap=0.20,
            score_threshold=0.20,
        )
    return RetrievalBudget(
        **common,
        dense_k=10,
        graph_k=8,
        graph_depth=2,
        fusion_k=18,
        context_k_min=2,
        context_k_max=5,
        context_token_budget=3000,
        score_gap=0.25,
        score_threshold=0.15,
    )


def estimate_tokens(text: str) -> int:
    """Conservatively estimate multilingual tokens without loading another tokenizer."""
    return len(_TOKEN.findall(text))


def select_dynamic_context(
    rows: list[dict[str, Any]], budget: RetrievalBudget
) -> list[dict[str, Any]]:
    """Apply minimum/maximum K, score threshold/gap, and a context token budget."""
    selected: list[dict[str, Any]] = []
    used_tokens = 0
    for row in rows[: budget.context_k_max]:
        row_tokens = estimate_tokens(str(row.get("content") or ""))
        enough = len(selected) >= budget.context_k_min
        previous_score = float(selected[-1]["hybrid_score"]) if selected else 1.0
        current_score = float(row["hybrid_score"])
        if enough and (
            current_score < budget.score_threshold
            or previous_score - current_score > budget.score_gap
            or used_tokens + row_tokens > budget.context_token_budget
        ):
            break
        selected.append(row)
        used_tokens += row_tokens

    metadata = budget.metadata(
        selected_context_k=len(selected), estimated_context_tokens=used_tokens
    )
    for row in selected:
        row["retrieval_budget"] = metadata
    return selected
