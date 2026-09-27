"""Dynamic Top-K policy and cutoff behavior."""

from cybersecurity_advisor.retrieval.dynamic_topk import (
    choose_retrieval_budget,
    select_dynamic_context,
)


def test_query_types_receive_different_bounded_budgets() -> None:
    definition = choose_retrieval_budget("What is phishing?")
    incident = choose_retrieval_budget("My account was hacked; how do I recover it?")
    multi_hop = choose_retrieval_budget(
        "Compare phishing and malware and explain how MFA protects against each"
    )

    assert (definition.dense_k, definition.graph_depth, definition.context_k_max) == (5, 1, 3)
    assert (incident.dense_k, incident.graph_depth) == (15, 2)
    assert (multi_hop.dense_k, multi_hop.graph_depth, multi_hop.context_k_max) == (20, 3, 6)


def test_dynamic_context_keeps_minimum_then_stops_at_score_gap() -> None:
    budget = choose_retrieval_budget("What is phishing?")
    rows = [
        {"content": "one", "hybrid_score": 0.95},
        {"content": "two", "hybrid_score": 0.90},
        {"content": "three", "hybrid_score": 0.40},
    ]

    selected = select_dynamic_context(rows, budget)

    assert len(selected) == 2
    assert selected[0]["retrieval_budget"]["selected_context_k"] == 2
