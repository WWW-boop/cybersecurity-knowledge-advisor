"""LINE Messaging API webhook adapter for the grounded-answer service."""

import json
from collections.abc import Callable
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from cybersecurity_advisor.api.dependencies import (
    SettingsDependency,
    get_answer_service,
    get_conversation_store,
    get_hybrid_retriever,
)
from cybersecurity_advisor.config.settings import Settings
from cybersecurity_advisor.integrations.line_messaging import (
    LineMessage,
    LineMessagingError,
    LineReplyClient,
    build_answer_reply_messages,
    verify_line_signature,
)

router = APIRouter(prefix="/api/v1/line", tags=["line"])
logger = structlog.get_logger(__name__)

LineAnswerer = Callable[[str, Settings, str | None], dict[str, Any]]
LineReplySender = Callable[[str, list[LineMessage]], None]

UNSUPPORTED_MESSAGE = "ขณะนี้รองรับเฉพาะข้อความตัวอักษรเท่านั้นครับ"
ERROR_MESSAGE = "ขออภัย ระบบไม่สามารถตอบคำถามได้ในขณะนี้ กรุณาลองใหม่ภายหลังครับ"
RESET_MESSAGE = "เริ่มแชตใหม่"
RESET_CONFIRMATION = "เริ่มแชตใหม่แล้วครับ ถามเรื่องที่ต้องการได้เลย"
EXAMPLES_MESSAGE = "ตัวอย่างคำถาม"
EXAMPLES_REPLY = (
    "ลองถาม Cyber Care AI ได้เลย เช่น\n"
    "• เพื่อนเผลอกดลิงก์แปลก ๆ ต้องทำอย่างไร?\n"
    "• บัญชีถูกแฮ็ก ควรเริ่มแก้จากตรงไหน?\n"
    "• โดน ransomware ต้องทำอะไรทันที?\n\n"
    "พิมพ์คำถามต่อได้เลย ผมจำบริบทการคุยล่าสุดให้ครับ"
)


class LineWebhookResponse(BaseModel):
    """Number of message events accepted for background processing."""

    accepted_events: int = Field(ge=0)


def answer_line_query(query: str, settings: Settings, session_key: str | None) -> dict[str, Any]:
    """Lazily construct the existing answer pipeline for one LINE query."""
    service = get_answer_service(get_hybrid_retriever(), settings)
    conversations = get_conversation_store()
    result = service.answer(
        query,
        "openai",
        history=conversations.get(session_key) if session_key else (),
        top_k=5,
        dense_k=10,
        graph_k=10,
        max_depth=2,
        language=None,
        topic=None,
        score_threshold=None,
        method=None,
        dynamic_k=settings.line_dynamic_k,
        generate_follow_ups=True,
    )
    if session_key and result.get("provider") != "policy":
        conversations.add(session_key, query, result["answer"])
    return result


def _line_session_key(source: Any) -> str | None:
    if not isinstance(source, dict) or not isinstance(source.get("userId"), str):
        return None
    kind = source.get("type")
    if kind == "group":
        scope = source.get("groupId")
    elif kind == "room":
        scope = source.get("roomId")
    else:
        scope = "direct"
    if not isinstance(scope, str) or not scope:
        return None
    return f"line:{scope}:{source['userId']}"


def get_line_answerer() -> LineAnswerer:
    """Return a lightweight callable so verification webhooks do not load ML models."""
    return answer_line_query


def get_line_reply_sender(settings: SettingsDependency) -> LineReplySender:
    """Build a lightweight sender that opens the HTTP client only in a background task."""

    def send(reply_token: str, messages: list[LineMessage]) -> None:
        access_token = (
            settings.line_channel_access_token.get_secret_value()
            if settings.line_channel_access_token is not None
            else ""
        )
        if not access_token:
            raise LineMessagingError("LINE channel access token is not configured")
        LineReplyClient(
            access_token,
            timeout_seconds=settings.line_reply_timeout_seconds,
        ).reply_messages(reply_token, messages)

    return send


LineAnswererDependency = Annotated[LineAnswerer, Depends(get_line_answerer)]
LineReplySenderDependency = Annotated[LineReplySender, Depends(get_line_reply_sender)]


def _answer_and_reply(
    query: str,
    reply_token: str,
    settings: Settings,
    answerer: LineAnswerer,
    sender: LineReplySender,
    webhook_event_id: str | None,
    session_key: str | None,
) -> None:
    try:
        if query == RESET_MESSAGE:
            if session_key:
                get_conversation_store().clear(session_key)
            messages = [{"type": "text", "text": RESET_CONFIRMATION}]
        elif query == EXAMPLES_MESSAGE:
            messages = [{"type": "text", "text": EXAMPLES_REPLY}]
        else:
            result = answerer(query, settings, session_key)
            messages = build_answer_reply_messages(query, result)
    except Exception:
        logger.exception("line_answer_failed", webhook_event_id=webhook_event_id)
        messages = [{"type": "text", "text": ERROR_MESSAGE}]

    try:
        sender(reply_token, messages)
    except LineMessagingError:
        logger.exception("line_reply_failed", webhook_event_id=webhook_event_id)


def _reply_without_answer(
    reply_token: str,
    sender: LineReplySender,
    webhook_event_id: str | None,
) -> None:
    try:
        sender(reply_token, [{"type": "text", "text": UNSUPPORTED_MESSAGE}])
    except LineMessagingError:
        logger.exception("line_reply_failed", webhook_event_id=webhook_event_id)


@router.post("/webhook", response_model=LineWebhookResponse)
async def line_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: SettingsDependency,
    answerer: LineAnswererDependency,
    sender: LineReplySenderDependency,
) -> LineWebhookResponse:
    """Verify and accept active LINE text-message events."""
    channel_secret = (
        settings.line_channel_secret.get_secret_value()
        if settings.line_channel_secret is not None
        else ""
    )
    if not channel_secret:
        raise HTTPException(status_code=503, detail="LINE channel secret is not configured")

    body = await request.body()
    signature = request.headers.get("x-line-signature")
    if not signature or not verify_line_signature(
        body,
        signature,
        channel_secret,
    ):
        raise HTTPException(status_code=400, detail="Invalid LINE webhook signature")

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=400, detail="Invalid LINE webhook payload") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise HTTPException(status_code=400, detail="Invalid LINE webhook payload")

    jobs: list[tuple[str, str | None, str | None, str | None]] = []
    for event in payload["events"]:
        if not isinstance(event, dict) or event.get("mode", "active") != "active":
            continue
        if event.get("type") != "message":
            continue
        reply_token = event.get("replyToken")
        if not isinstance(reply_token, str) or not reply_token:
            continue
        event_id = event.get("webhookEventId")
        event_id = event_id if isinstance(event_id, str) else None
        session_key = _line_session_key(event.get("source"))
        message = event.get("message")
        if not isinstance(message, dict) or message.get("type") != "text":
            jobs.append((reply_token, None, event_id, session_key))
            continue
        text = message.get("text")
        if isinstance(text, str) and text.strip():
            jobs.append((reply_token, text.strip(), event_id, session_key))

    access_token = (
        settings.line_channel_access_token.get_secret_value()
        if settings.line_channel_access_token is not None
        else ""
    )
    if jobs and not access_token:
        raise HTTPException(status_code=503, detail="LINE channel access token is not configured")

    for reply_token, query, event_id, session_key in jobs:
        if query is None:
            background_tasks.add_task(_reply_without_answer, reply_token, sender, event_id)
        else:
            background_tasks.add_task(
                _answer_and_reply,
                query,
                reply_token,
                settings,
                answerer,
                sender,
                event_id,
                session_key,
            )
    return LineWebhookResponse(accepted_events=len(jobs))
