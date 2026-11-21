"""Authentication helpers for Azure AI Translator.

Supports the simplest auth path (resource key via Ocp-Apim-Subscription-Key header).
The functions below are structured so a time-limited bearer token or Microsoft Entra ID
(managed identity / service principal) flow can be dropped in later without touching
callers — they all go through `build_auth_headers()`.
"""
import uuid

from app.config import Settings


class TranslatorAuthError(RuntimeError):
    """Raised when Translator credentials are missing or invalid."""


def build_auth_headers(settings: Settings) -> dict[str, str]:
    """Builds request headers using resource-key authentication.

    Future auth modes (bearer token, Entra ID) can be added as alternate branches
    here, selected by settings, without changing calling code.
    """
    if not settings.has_translator_credentials:
        raise TranslatorAuthError(
            "Translator credentials are not configured. Set TRANSLATOR_KEY and TRANSLATOR_REGION "
            "(see .env.example)."
        )
    return {
        "Ocp-Apim-Subscription-Key": settings.translator_key,
        "Ocp-Apim-Subscription-Region": settings.translator_region,
        "Content-type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
