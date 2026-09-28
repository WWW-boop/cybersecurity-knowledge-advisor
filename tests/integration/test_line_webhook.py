"""LINE webhook behavior without external LINE or retrieval services."""

import base64
import hashlib
import hmac
import json
from typing import Any

from fastapi.testclient import TestClient

from cybersecurity_advisor.api.routers.line import (
    get_line_answerer,
    get_line_reply_sender,
)
from cybersecurity_advisor.config.settings import Settings, get_settings
from cybersecurity_advisor.integrations.line_messaging import LineMessage

CHANNEL_SECRET = "test-channel-secret"  # noqa: S105 - explicit test credential


class FakeAnswerer:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def __call__(self, query: str, settings: Settings) -> dict[str, Any]:
        self.queries.append(query)
        assert settings.line_provider == "openai"
        return {
            "answer": "ใช้ MFA และเปลี่ยนรหัสผ่าน [S1]",
            "sources": [
                {
                    "url": "https://example.com/security-guide",
                    "citation": "Security guide",
                }
            ],
        }


class FakeSender:
    def __init__(self) -> None:
        self.replies: list[tuple[str, list[LineMessage]]] = []

    def __call__(self, reply_token: str, messages: list[LineMessage]) -> None:
        self.replies.append((reply_token, messages))


def signed_headers(body: bytes) -> dict[str, str]:
    digest = hmac.new(CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()
    return {
        "Content-Type": "application/json",
        "X-Line-Signature": base64.b64encode(digest).decode(),
    }


def line_settings(*, with_access_token: bool = True) -> Settings:
    return Settings(
        _env_file=None,
        line_channel_secret=CHANNEL_SECRET,
        line_channel_access_token="test-access-token" if with_access_token else None,
    )


def empty_access_token_settings() -> Settings:
    return Settings(
        _env_file=None,
        line_channel_secret=CHANNEL_SECRET,
        line_channel_access_token="",
    )


def test_accepts_line_verification_webhook_without_loading_answer_service(
    client: TestClient,
) -> None:
    client.app.dependency_overrides[get_settings] = lambda: line_settings(with_access_token=False)
    body = b'{"destination":"test","events":[]}'

    response = client.post("/api/v1/line/webhook", content=body, headers=signed_headers(body))

    assert response.status_code == 200
    assert response.json() == {"accepted_events": 0}


def test_rejects_invalid_line_signature(client: TestClient) -> None:
    client.app.dependency_overrides[get_settings] = line_settings

    response = client.post(
        "/api/v1/line/webhook",
        content=b'{"events":[]}',
        headers={"Content-Type": "application/json", "X-Line-Signature": "invalid"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid LINE webhook signature"


def test_rejects_text_event_when_access_token_is_empty(client: TestClient) -> None:
    client.app.dependency_overrides[get_settings] = empty_access_token_settings
    body = json.dumps(
        {
            "events": [
                {
                    "type": "message",
                    "replyToken": "reply-1",
                    "message": {"type": "text", "text": "test"},
                }
            ]
        },
        separators=(",", ":"),
    ).encode()

    response = client.post("/api/v1/line/webhook", content=body, headers=signed_headers(body))

    assert response.status_code == 503
    assert response.json()["detail"] == "LINE channel access token is not configured"


def test_answers_active_text_message_in_background(client: TestClient) -> None:
    answerer = FakeAnswerer()
    sender = FakeSender()
    client.app.dependency_overrides[get_settings] = line_settings
    client.app.dependency_overrides[get_line_answerer] = lambda: answerer
    client.app.dependency_overrides[get_line_reply_sender] = lambda: sender
    body = json.dumps(
        {
            "destination": "test",
            "events": [
                {
                    "type": "message",
                    "mode": "active",
                    "webhookEventId": "event-1",
                    "replyToken": "reply-1",
                    "message": {"id": "message-1", "type": "text", "text": "บัญชีถูกแฮ็ก"},
                }
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()

    response = client.post("/api/v1/line/webhook", content=body, headers=signed_headers(body))

    assert response.status_code == 200
    assert response.json() == {"accepted_events": 1}
    assert answerer.queries == ["บัญชีถูกแฮ็ก"]
    assert len(sender.replies) == 1
    reply_token, messages = sender.replies[0]
    assert reply_token == "reply-1"  # noqa: S105 - explicit fake token
    assert len(messages) == 1
    assert messages[0]["type"] == "flex"
    assert messages[0]["contents"]["body"]["contents"][3]["text"] == ("ใช้ MFA และเปลี่ยนรหัสผ่าน")
    assert messages[0]["contents"]["footer"]["contents"][0]["action"]["uri"] == (
        "https://example.com/security-guide"
    )


def test_replies_with_supported_type_message_for_non_text_input(client: TestClient) -> None:
    answerer = FakeAnswerer()
    sender = FakeSender()
    client.app.dependency_overrides[get_settings] = line_settings
    client.app.dependency_overrides[get_line_answerer] = lambda: answerer
    client.app.dependency_overrides[get_line_reply_sender] = lambda: sender
    body = json.dumps(
        {
            "events": [
                {
                    "type": "message",
                    "replyToken": "reply-image",
                    "message": {"id": "image-1", "type": "image"},
                }
            ]
        },
        separators=(",", ":"),
    ).encode()

    response = client.post("/api/v1/line/webhook", content=body, headers=signed_headers(body))

    assert response.status_code == 200
    assert response.json() == {"accepted_events": 1}
    assert answerer.queries == []
    assert sender.replies == [
        (
            "reply-image",
            [{"type": "text", "text": "ขณะนี้รองรับเฉพาะข้อความตัวอักษรเท่านั้นครับ"}],
        )
    ]
