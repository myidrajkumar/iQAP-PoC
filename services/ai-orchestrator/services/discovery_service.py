"""Discovery Service Client"""

import httpx
import json
import logging
from fastapi import HTTPException
from core.config import settings

logger = logging.getLogger(__name__)


async def get_ui_blueprint(url: str) -> str:
    """
    Contacts the Discovery Service to get the UI blueprint for a given URL.
    """
    logger.info("Contacting Discovery Service at %s", settings.DISCOVERY_SERVICE_URL)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.DISCOVERY_SERVICE_URL, json={"url": url}, timeout=60.0
            )
            response.raise_for_status()
            logger.info("Discovery Service returned blueprint successfully.")
            # Ensure the output is a compact JSON string
            return json.dumps(response.json())
    except httpx.RequestError as e:
        logger.error(f"Error contacting Discovery Service: {e}")
        raise HTTPException(status_code=503, detail="Discovery Service unavailable.")
    except httpx.HTTPStatusError as e:
        logger.error(f"Discovery Service returned an error: {e.response.status_code}")
        raise HTTPException(
            status_code=e.response.status_code, detail="Error from Discovery Service."
        )
