"""Bounded per-session conversation memory."""

from cybersecurity_advisor.generation import conversation


def test_conversations_are_isolated_bounded_and_expire(monkeypatch) -> None:
    now = [0.0]
    monkeypatch.setattr(conversation, "monotonic", lambda: now[0])
    store = conversation.ConversationStore()

    for number in range(4):
        store.add("alice", f"question {number}", f"answer {number}")
    store.add("bob", "different", "reply")

    assert [question for question, _ in store.get("alice")] == [
        "question 1",
        "question 2",
        "question 3",
    ]
    assert store.get("bob") == (("different", "reply"),)
    store.clear("bob")
    assert store.get("bob") == ()

    now[0] = 1800.0
    assert store.get("alice") == ()


def test_conversation_store_limits_sessions() -> None:
    store = conversation.ConversationStore()
    for number in range(1001):
        store.add(f"user-{number}", "question", "answer")

    assert store.get("user-0") == ()
    assert store.get("user-1000") == (("question", "answer"),)
