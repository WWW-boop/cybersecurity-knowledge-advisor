"""Small, testable LINE Messaging API primitives."""

import base64
import hashlib
import hmac
import re
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

LINE_REPLY_ENDPOINT = "https://api.line.me/v2/bot/message/reply"
LINE_TEXT_LIMIT = 5000
LINE_REPLY_MESSAGE_LIMIT = 5
FLEX_ANSWER_PREVIEW_LIMIT = 1200
FLEX_ALT_TEXT_LIMIT = 400
FLEX_SOURCE_LABEL_LIMIT = 5
SOURCE_MARKER_PATTERN = re.compile(r"(?:\[\s*S\s*\d+\s*\]|S\s*\[\s*\d+\s*\])", re.IGNORECASE)

type LineMessage = dict[str, Any]


class LineMessagingError(RuntimeError):
    """The LINE Messaging API rejected or could not receive a request."""


def verify_line_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    """Verify an unmodified webhook body using LINE's HMAC-SHA256 scheme."""
    digest = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature)


def split_line_text(
    text: str,
    *,
    max_chars: int = LINE_TEXT_LIMIT,
    max_messages: int = LINE_REPLY_MESSAGE_LIMIT,
) -> list[str]:
    """Split an answer into LINE-sized messages while preferring natural boundaries."""
    if max_chars < 2 or max_messages < 1:
        raise ValueError("LINE message limits must be positive")
    remaining = text.strip()
    if not remaining:
        raise ValueError("LINE reply text cannot be empty")

    messages: list[str] = []
    while remaining and len(messages) < max_messages:
        if len(remaining) <= max_chars:
            messages.append(remaining)
            remaining = ""
            break

        newline = remaining.rfind("\n", 0, max_chars + 1)
        space = remaining.rfind(" ", 0, max_chars + 1)
        boundary = max(newline, space)
        if boundary < max_chars // 2:
            boundary = max_chars
        part = remaining[:boundary].rstrip()
        if not part:
            part = remaining[:max_chars]
            boundary = max_chars
        messages.append(part)
        remaining = remaining[boundary:].lstrip()

    if remaining:
        suffix = "…"
        messages[-1] = messages[-1][: max_chars - len(suffix)].rstrip() + suffix
    return messages


def _truncate(text: str, limit: int, *, preserve_lines: bool = False) -> str:
    """Return compact card text without exceeding its component budget."""
    normalized = (
        "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()
        if preserve_lines
        else " ".join(text.split())
    )
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def strip_source_markers(text: str) -> str:
    """Remove internal source labels while keeping the answer readable in LINE."""
    cleaned = SOURCE_MARKER_PATTERN.sub("", text)
    cleaned = re.sub(r"[ \t]+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def build_answer_flex_message(query: str, result: Mapping[str, Any]) -> LineMessage:
    """Build a deterministic Flex Message from one grounded-answer result."""
    question = query.strip()
    answer = strip_source_markers(str(result.get("answer") or ""))
    if not question:
        raise ValueError("LINE Flex Message query cannot be empty")
    if not answer:
        raise ValueError("LINE Flex Message answer cannot be empty")

    raw_sources = result.get("sources")
    sources = (
        [source for source in raw_sources if isinstance(source, Mapping)]
        if isinstance(raw_sources, list)
        else []
    )
    source_labels = list(
        dict.fromkeys(str(source.get("citation") or "").strip() for source in sources)
    )
    source_labels = [label for label in source_labels if label]

    body_contents: list[LineMessage] = [
        {
            "type": "text",
            "text": "คำถามของคุณ",
            "size": "xs",
            "color": "#607D8B",
            "weight": "bold",
        },
        {
            "type": "text",
            "text": _truncate(question, 300),
            "size": "md",
            "weight": "bold",
            "wrap": True,
            "margin": "sm",
            "maxLines": 3,
        },
        {"type": "separator", "margin": "lg"},
        {
            "type": "text",
            "text": _truncate(answer, FLEX_ANSWER_PREVIEW_LIMIT, preserve_lines=True),
            "size": "sm",
            "color": "#263238",
            "wrap": True,
            "margin": "lg",
        },
    ]
    if source_labels:
        labels = source_labels[:FLEX_SOURCE_LABEL_LIMIT]
        references = "อ้างอิง:\n" + "\n".join(f"• {_truncate(label, 160)}" for label in labels)
        if len(source_labels) > FLEX_SOURCE_LABEL_LIMIT:
            references += f"\n• และอีก {len(source_labels) - FLEX_SOURCE_LABEL_LIMIT} แหล่งข้อมูล"
        body_contents.append(
            {
                "type": "text",
                "text": references,
                "size": "xs",
                "color": "#607D8B",
                "margin": "lg",
                "wrap": True,
            }
        )

    bubble: LineMessage = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#0B3B60",
            "paddingAll": "18px",
            "contents": [
                {
                    "type": "text",
                    "text": "CYBER CARE",
                    "color": "#FFFFFF",
                    "size": "lg",
                    "weight": "bold",
                },
                {
                    "type": "text",
                    "text": "คำแนะนำด้านความปลอดภัยไซเบอร์",
                    "color": "#BFE3F2",
                    "size": "xs",
                    "margin": "sm",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "18px",
            "contents": body_contents,
        },
    }
    return {
        "type": "flex",
        "altText": _truncate(f"Cyber Care: {question}", FLEX_ALT_TEXT_LIMIT),
        "contents": bubble,
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "ป้องกันฟิชชิง",
                        "text": "ควรป้องกันฟิชชิงอย่างไร?",
                    },
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "บัญชีถูกแฮ็ก",
                        "text": "บัญชีถูกแฮ็กควรทำอย่างไร?",
                    },
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "รหัสผ่านปลอดภัย",
                        "text": "ตั้งรหัสผ่านอย่างไรให้ปลอดภัย?",
                    },
                },
            ]
        },
    }


def build_answer_reply_messages(
    query: str,
    result: Mapping[str, Any],
) -> list[LineMessage]:
    """Build the single Flex card used for one grounded answer."""
    return [build_answer_flex_message(query, result)]


class LineReplyClient:
    """Send LINE reply message objects with a short-lived HTTP client."""

    def __init__(
        self,
        channel_access_token: str,
        *,
        timeout_seconds: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.channel_access_token = channel_access_token
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def reply_text(self, reply_token: str, text: str, *, max_chars: int = LINE_TEXT_LIMIT) -> None:
        """Reply once with up to LINE's five text-message objects."""
        self.reply_messages(
            reply_token,
            [{"type": "text", "text": part} for part in split_line_text(text, max_chars=max_chars)],
        )

    def reply_messages(
        self,
        reply_token: str,
        messages: Sequence[Mapping[str, Any]],
    ) -> None:
        """Reply once with one to five text, Flex, or other LINE message objects."""
        if not reply_token.strip():
            raise ValueError("LINE reply token cannot be empty")
        if not 1 <= len(messages) <= LINE_REPLY_MESSAGE_LIMIT:
            raise ValueError("LINE reply must contain between one and five messages")
        normalized = [dict(message) for message in messages]
        if any(not message.get("type") for message in normalized):
            raise ValueError("Every LINE reply message must have a type")
        payload = {"replyToken": reply_token, "messages": normalized}
        headers = {
            "Authorization": f"Bearer {self.channel_access_token}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(LINE_REPLY_ENDPOINT, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise LineMessagingError("LINE Reply API request failed") from error
