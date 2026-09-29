"""Rich menu layout and install protocol without LINE network access."""

from io import BytesIO

import httpx
import pytest
from PIL import Image

from scripts.setup_line_rich_menu import (
    MENU_HEIGHT,
    MENU_WIDTH,
    install_menu,
    menu_image,
    menu_payload,
)


def test_rich_menu_prioritizes_questions_and_supports_conversation() -> None:
    payload = menu_payload()
    assert payload["size"] == {"width": MENU_WIDTH, "height": MENU_HEIGHT}
    assert [(area["bounds"]["x"], area["bounds"]["y"]) for area in payload["areas"]] == [
        (0, 0),
        (0, 843),
        (834, 843),
        (1667, 843),
    ]
    assert payload["areas"][0]["bounds"]["width"] == MENU_WIDTH
    assert payload["areas"][0]["action"]["inputOption"] == "openKeyboard"
    assert payload["areas"][1]["action"]["fillInText"] == "ฉันเจอเหตุการณ์: "
    assert payload["areas"][2]["action"]["text"] == "ตัวอย่างคำถาม"
    assert payload["areas"][-1]["action"]["text"] == "เริ่มแชตใหม่"


def test_rich_menu_image_meets_line_limits() -> None:
    content = menu_image()
    assert len(content) < 1_000_000
    assert Image.open(BytesIO(content)).size == (MENU_WIDTH, MENU_HEIGHT)


def test_rich_menu_is_uploaded_before_becoming_default() -> None:
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.host, request.url.path))
        if request.url.path == "/v2/bot/richmenu":
            return httpx.Response(200, json={"richMenuId": "richmenu-test"})
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert install_menu(client, "test-token") == "richmenu-test"

    assert calls == [
        ("POST", "api.line.me", "/v2/bot/richmenu"),
        ("POST", "api-data.line.me", "/v2/bot/richmenu/richmenu-test/content"),
        ("POST", "api.line.me", "/v2/bot/user/all/richmenu/richmenu-test"),
    ]


def test_failed_upload_removes_new_menu_without_replacing_default() -> None:
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/v2/bot/richmenu":
            return httpx.Response(200, json={"richMenuId": "richmenu-test"})
        if request.url.path.endswith("/content"):
            return httpx.Response(400, json={"message": "Invalid image"})
        return httpx.Response(200, json={})

    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        install_menu(client, "test-token")

    assert calls[-1] == ("DELETE", "/v2/bot/richmenu/richmenu-test")
    assert not any("/user/all/richmenu" in path for _, path in calls)
