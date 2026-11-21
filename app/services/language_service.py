"""Languages API — lists supported languages. No authentication required."""
import time
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.models.translation import LanguageInfo, LanguagesResponse

_cache: dict[str, Any] = {"data": None, "expires_at": 0.0}


async def get_languages(settings: Settings | None = None, scope: str = "translation,transliteration") -> LanguagesResponse:
    """Fetches supported languages, caching the result for CACHE_TTL_SECONDS.

    The /languages endpoint requires no authentication — it's public metadata.
    """
    settings = settings or get_settings()
    now = time.time()
    if _cache["data"] is not None and now < _cache["expires_at"]:
        return _cache["data"]

    url = f"{settings.translator_endpoint}/languages"
    params = {"api-version": "3.0", "scope": scope}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        payload = resp.json()

    translation = {
        code: LanguageInfo(code=code, name=info.get("name", code), native_name=info.get("nativeName", code), dir=info.get("dir", "ltr"))
        for code, info in payload.get("translation", {}).items()
    }
    transliteration = payload.get("transliteration", {})

    result = LanguagesResponse(translation=translation, transliteration=transliteration)
    _cache["data"] = result
    _cache["expires_at"] = now + settings.cache_ttl_seconds
    return result


def clear_cache() -> None:
    _cache["data"] = None
    _cache["expires_at"] = 0.0
