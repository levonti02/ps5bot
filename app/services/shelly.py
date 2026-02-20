import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def _send_command(ip: str, action: str) -> bool:
    """Send ON/OFF command to Shelly Plug 2. Returns True on success."""
    url = f"http://{ip}/relay/0?turn={action}"
    timeout = settings.SHELLY_TIMEOUT_SECONDS

    for attempt in range(1, settings.SHELLY_RETRY_COUNT + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                logger.info("Shelly %s %s — OK (attempt %d)", ip, action, attempt)
                return True
        except Exception as exc:
            logger.warning(
                "Shelly %s %s — attempt %d failed: %s", ip, action, attempt, exc,
            )
    logger.error("Shelly %s %s — all %d attempts failed", ip, action, settings.SHELLY_RETRY_COUNT)
    return False


async def turn_on(ip: str) -> bool:
    return await _send_command(ip, "on")


async def turn_off(ip: str) -> bool:
    return await _send_command(ip, "off")
