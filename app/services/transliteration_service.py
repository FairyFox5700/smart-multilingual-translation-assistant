"""Transliteration API — converts text between writing systems/scripts.

Distinct from translation: this changes script/phonetics only, not meaning.
E.g. Ukrainian Cyrillic ("Привіт") -> Latin ("Pryvit").
"""
import httpx

from app.config import Settings, get_settings
from app.core.security import build_auth_headers
from app.models.translation import TransliterateResponse


async def transliterate(text: str, language: str, from_script: str, to_script: str, settings: Settings | None = None) -> TransliterateResponse:
    settings = settings or get_settings()
    headers = build_auth_headers(settings)

    url = f"{settings.translator_endpoint}/transliterate"
    params = {
        "api-version": "3.0",
        "language": language,
        "fromScript": from_script,
        "toScript": to_script,
    }
    body = [{"text": text}]

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, params=params, headers=headers, json=body)
        resp.raise_for_status()
        payload = resp.json()

    first = payload[0]
    return TransliterateResponse(text=first["text"], script=first["script"])
