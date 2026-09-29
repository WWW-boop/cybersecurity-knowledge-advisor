"""Create and install the default Cyber Care LINE rich menu."""

from pathlib import Path

import httpx

from cybersecurity_advisor.config.settings import get_settings

MENU_WIDTH = 2500
MENU_HEIGHT = 1686
MENU_IMAGE_PATH = Path(__file__).resolve().parents[1] / "assets/line-rich-menu.png"


def menu_payload() -> dict:
    """Make typing a question the primary action, with three supporting actions."""
    areas = [
        {
            "bounds": {"x": 0, "y": 0, "width": MENU_WIDTH, "height": 843},
            "action": {
                "type": "postback",
                "label": "ถาม AI",
                "data": "menu=ask",
                "inputOption": "openKeyboard",
            },
        },
        {
            "bounds": {"x": 0, "y": 843, "width": 834, "height": 843},
            "action": {
                "type": "postback",
                "label": "เล่าเหตุการณ์",
                "data": "menu=incident",
                "inputOption": "openKeyboard",
                "fillInText": "ฉันเจอเหตุการณ์: ",
            },
        },
        {
            "bounds": {"x": 834, "y": 843, "width": 833, "height": 843},
            "action": {"type": "message", "label": "ตัวอย่างคำถาม", "text": "ตัวอย่างคำถาม"},
        },
        {
            "bounds": {"x": 1667, "y": 843, "width": 833, "height": 843},
            "action": {"type": "message", "label": "เริ่มแชตใหม่", "text": "เริ่มแชตใหม่"},
        },
    ]
    return {
        "size": {"width": MENU_WIDTH, "height": MENU_HEIGHT},
        "selected": True,
        "name": "Cyber Care AI",
        "chatBarText": "Cyber Care AI",
        "areas": areas,
    }


def menu_image() -> bytes:
    """Load the checked-in Thai menu artwork for upload."""
    content = MENU_IMAGE_PATH.read_bytes()
    if len(content) > 1_000_000:
        raise RuntimeError("LINE rich menu image exceeds 1 MB")
    return content


def install_menu(client: httpx.Client, token: str) -> str:
    """Create, upload, and set a default menu, removing failed new menus."""
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "https://api.line.me/v2/bot/richmenu",
        headers=headers,
        json=menu_payload(),
    )
    response.raise_for_status()
    menu_id = response.json()["richMenuId"]
    try:
        upload = client.post(
            f"https://api-data.line.me/v2/bot/richmenu/{menu_id}/content",
            headers={**headers, "Content-Type": "image/png"},
            content=menu_image(),
        )
        upload.raise_for_status()
        selected = client.post(
            f"https://api.line.me/v2/bot/user/all/richmenu/{menu_id}", headers=headers
        )
        selected.raise_for_status()
    except Exception:
        client.delete(f"https://api.line.me/v2/bot/richmenu/{menu_id}", headers=headers)
        raise
    return menu_id


def main() -> None:
    settings = get_settings()
    token = (
        settings.line_channel_access_token.get_secret_value()
        if settings.line_channel_access_token is not None
        else ""
    )
    if not token:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN is required")
    with httpx.Client(timeout=30) as client:
        menu_id = install_menu(client, token)
    print(f"LINE rich menu installed: {menu_id}")


if __name__ == "__main__":
    main()
