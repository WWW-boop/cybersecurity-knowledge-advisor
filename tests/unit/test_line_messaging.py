"""LINE signature, message splitting, and reply-client behavior."""

import base64
import hashlib
import hmac
import json

import httpx
import pytest

from cybersecurity_advisor.integrations.line_messaging import (
    FLEX_ANSWER_PREVIEW_LIMIT,
    LineReplyClient,
    build_answer_flex_message,
    build_answer_reply_messages,
    split_line_text,
    verify_line_signature,
)


def signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def test_verifies_signature_against_unmodified_body() -> None:
    body = b'{"events":[]}'

    assert verify_line_signature(body, signature(body, "channel-secret"), "channel-secret")
    assert not verify_line_signature(
        body + b"\n",
        signature(body, "channel-secret"),
        "channel-secret",
    )


def test_splits_long_answers_within_line_limits() -> None:
    messages = split_line_text("alpha beta gamma delta", max_chars=10, max_messages=5)

    assert messages == ["alpha beta", "gamma", "delta"]
    assert all(len(message) <= 10 for message in messages)


def test_truncates_when_answer_exceeds_five_messages() -> None:
    messages = split_line_text("x" * 40, max_chars=5, max_messages=3)

    assert len(messages) == 3
    assert messages[-1].endswith("…")


def test_rejects_empty_reply_text() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        split_line_text("  ")


def test_builds_grounded_answer_flex_message_with_source_names_only() -> None:
    message = build_answer_flex_message(
        "How do I prevent phishing?",
        {
            "answer": "Check the sender and enable MFA [S1].",
            "sources": [
                {"url": "https://example.com/one", "citation": "Source one"},
                {"url": "javascript:alert(1)", "citation": "Unsafe source"},
                {"url": "https://example.com/two", "citation": "Source two"},
                {"url": "https://example.com/three", "citation": "Source three"},
            ],
        },
    )

    assert message["type"] == "flex"
    assert message["altText"] == "Cyber Care: How do I prevent phishing?"
    bubble = message["contents"]
    assert bubble["header"]["contents"][0]["text"] == "CYBER CARE"
    assert bubble["body"]["contents"][3]["text"] == "Check the sender and enable MFA."
    assert bubble["body"]["contents"][4]["text"] == (
        "อ้างอิง:\n• Source one\n• Unsafe source\n• Source two\n• Source three"
    )
    assert "footer" not in bubble
    assert "https://example.com/one" not in json.dumps(message)
    assert len(message["quickReply"]["items"]) == 3


def test_removes_all_supported_source_marker_styles_from_flex_answer() -> None:
    message = build_answer_flex_message(
        "Question",
        {"answer": "First [S1][S4], second S[2], and third [s 3].", "sources": []},
    )

    answer = message["contents"]["body"]["contents"][3]["text"]
    assert answer == "First, second, and third."


def test_keeps_answer_steps_on_separate_lines() -> None:
    message = build_answer_flex_message(
        "คำถาม",
        {"answer": "1. ปิด Wi-Fi  \n2. เปลี่ยนรหัสผ่าน\n\n3. ตรวจสอบบัญชี", "sources": []},
    )

    answer = message["contents"]["body"]["contents"][3]["text"]
    assert answer == "1. ปิด Wi-Fi\n2. เปลี่ยนรหัสผ่าน\n\n3. ตรวจสอบบัญชี"


def test_long_answer_is_returned_as_one_truncated_flex_card() -> None:
    answer = "a" * (FLEX_ANSWER_PREVIEW_LIMIT + 1)

    messages = build_answer_reply_messages(
        "Long question",
        {"answer": answer, "sources": []},
    )

    assert [message["type"] for message in messages] == ["flex"]
    assert messages[0]["contents"]["body"]["contents"][3]["text"].endswith("…")


def test_rejects_empty_flex_answer() -> None:
    with pytest.raises(ValueError, match="answer cannot be empty"):
        build_answer_flex_message("question", {"answer": ""})


def test_reply_client_sends_bearer_token_and_multiple_messages() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, request=request)

    client = LineReplyClient(
        "access-token",  # noqa: S106 - explicit fake credential
        transport=httpx.MockTransport(handler),
    )
    client.reply_text("reply-token", "a" * 5001)

    assert captured["authorization"] == "Bearer access-token"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["replyToken"] == "reply-token"
    assert len(payload["messages"]) == 2


def test_reply_client_sends_flex_message_object() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, request=request)

    client = LineReplyClient(
        "access-token",  # noqa: S106 - explicit fake credential
        transport=httpx.MockTransport(handler),
    )
    flex = build_answer_flex_message("Question", {"answer": "Answer", "sources": []})

    client.reply_messages("reply-token", [flex])

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["messages"][0]["type"] == "flex"


def test_reply_client_rejects_more_than_five_messages() -> None:
    client = LineReplyClient("access-token")  # noqa: S106 - explicit fake credential

    with pytest.raises(ValueError, match="between one and five"):
        client.reply_messages(
            "reply-token",
            [{"type": "text", "text": "test"}] * 6,
        )
