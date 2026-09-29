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

LineAnswerer = Callable[[str, Settings], dict[str, Any]]
LineReplySender = Callable[[str, list[LineMessage]], None]

UNSUPPORTED_MESSAGE = "ขณะนี้รองรับเฉพาะข้อความตัวอักษรเท่านั้นครับ"
ERROR_MESSAGE = "ขออภัย ระบบไม่สามารถตอบคำถามได้ในขณะนี้ กรุณาลองใหม่ภายหลังครับ"


class LineWebhookResponse(BaseModel):
    """Number of message events accepted for background processing."""

    accepted_events: int = Field(ge=0)


def answer_line_query(query: str, settings: Settings) -> dict[str, Any]:
    """Lazily construct the existing answer pipeline for one LINE query."""
    service = get_answer_service(get_hybrid_retriever(), settings)
    return service.answer(
        query,
        "openai",
        top_k=5,
        dense_k=10,
        graph_k=10,
        max_depth=2,
        language=None,
        topic=None,
        score_threshold=None,
        method=None,
        dynamic_k=settings.line_dynamic_k,
    )


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
) -> None:
    try:
        result = answerer(query, settings)
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

    jobs: list[tuple[str, str | None, str | None]] = []
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
        message = event.get("message")
        if not isinstance(message, dict) or message.get("type") != "text":
            jobs.append((reply_token, None, event_id))
            continue
        text = message.get("text")
        if isinstance(text, str) and text.strip():
            jobs.append((reply_token, text.strip(), event_id))

    access_token = (
        settings.line_channel_access_token.get_secret_value()
        if settings.line_channel_access_token is not None
        else ""
    )
    if jobs and not access_token:
        raise HTTPException(status_code=503, detail="LINE channel access token is not configured")

    for reply_token, query, event_id in jobs:
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
            )
    return LineWebhookResponse(accepted_events=len(jobs))
