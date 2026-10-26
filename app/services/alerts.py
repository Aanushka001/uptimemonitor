import logging

import httpx

from app.config import settings

logger = logging.getLogger("vigil.alerts")


def send_telegram(text: str) -> bool:
    """Send a Telegram message. Returns True only if Telegram accepted it.

    Never raises: a failed alert must not crash the worker.
    """
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.info("Telegram not configured; alert not sent: %s", text)
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        response = httpx.post(
            url, json={"chat_id": settings.telegram_chat_id, "text": text}, timeout=10
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("Telegram alert failed: %s", type(exc).__name__)
        return False


def down_message(name: str, url: str, error: str | None) -> str:
    return f"DOWN: {name}\n{url}\nReason: {error or 'unknown'}"


def recovered_message(name: str, url: str) -> str:
    return f"RECOVERED: {name}\n{url}"
