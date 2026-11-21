"""Translate API — core translation + auto-detect logic, plus an LLM-based path.

Implements, per-request, no-training-required controls:
- Dynamic dictionary: <mstrans:dictionary translation="...">source</mstrans:dictionary> markup.
  Only works when `from` (source_language) is explicitly specified — API restriction.
- Prevent translation: <mstrans:dictionary translation="X" notranslate="true">X</mstrans:dictionary>
  (implemented here as a same-text dynamic-dictionary entry, which is the standard workaround
  since the service does not expose a separate "notranslate" markup keyword).
- Profanity handling: profanityAction / profanityMarker query parameters.

LLM-based translation (tone, gender, adaptive references) requires a Microsoft Foundry
resource (a chat-completions-style deployment), not a plain Translator resource.
"""
import html
import re

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import Settings, get_settings
from app.core.security import build_auth_headers
from app.models.translation import DetectedLanguage, TranslateRequest, TranslateResponse

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class TransientTranslatorError(RuntimeError):
    pass


class FoundryNotConfiguredError(RuntimeError):
    pass


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _apply_markup(text: str, dynamic_dictionary: dict[str, str] | None, no_translate_terms: list[str] | None) -> str:
    """Wraps requested phrases with <mstrans:dictionary> markup for forced translation
    or pass-through (notranslate) behavior. Longest phrases are applied first to avoid
    partial/overlapping replacements.
    """
    result = text
    replacements: list[tuple[str, str]] = []

    if dynamic_dictionary:
        for source_phrase, forced_translation in dynamic_dictionary.items():
            markup = f'<mstrans:dictionary translation="{_escape(forced_translation)}">{_escape(source_phrase)}</mstrans:dictionary>'
            replacements.append((source_phrase, markup))

    if no_translate_terms:
        for term in no_translate_terms:
            markup = f'<mstrans:dictionary translation="{_escape(term)}">{_escape(term)}</mstrans:dictionary>'
            replacements.append((term, markup))

    # Apply longest-phrase-first so overlapping terms don't break each other's markup.
    for phrase, markup in sorted(replacements, key=lambda p: len(p[0]), reverse=True):
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        result = pattern.sub(lambda _m, markup=markup: markup, result, count=1)

    return result


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(TransientTranslatorError),
)
async def _post_translate(client: httpx.AsyncClient, url: str, params: dict, headers: dict, body: list[dict]) -> list[dict]:
    resp = await client.post(url, params=params, headers=headers, json=body)
    if resp.status_code in _RETRYABLE_STATUS:
        raise TransientTranslatorError(f"Translator returned {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    return resp.json()


async def translate_nmt(req: TranslateRequest, settings: Settings | None = None) -> TranslateResponse:
    """Standard NMT translation via Translator v3.0 /translate."""
    settings = settings or get_settings()
    headers = build_auth_headers(settings)

    uses_markup = bool(req.dynamic_dictionary or req.no_translate_terms)
    warnings: list[str] = []
    if req.dynamic_dictionary and not req.source_language:
        warnings.append(
            "dynamic_dictionary requires an explicit source_language; the dictionary markup was skipped "
            "and plain text was sent instead."
        )
        uses_markup = bool(req.no_translate_terms)

    source_text = req.text
    if uses_markup:
        dyn_dict = req.dynamic_dictionary if req.source_language else None
        source_text = _apply_markup(req.text, dyn_dict, req.no_translate_terms)

    url = f"{settings.translator_endpoint}/translate"
    params: dict = {
        "api-version": "3.0",
        "to": req.target_languages,
        "textType": req.text_type,
        "profanityAction": req.profanity_action,
        "profanityMarker": req.profanity_marker,
    }
    if req.source_language:
        params["from"] = req.source_language
    if uses_markup:
        params["textType"] = "html"  # dictionary markup requires textType=html

    body = [{"text": source_text}]

    async with httpx.AsyncClient(timeout=15.0) as client:
        payload = await _post_translate(client, url, params, headers, body)

    first = payload[0]
    detected = None
    if "detectedLanguage" in first:
        detected = DetectedLanguage(language=first["detectedLanguage"]["language"], score=first["detectedLanguage"]["score"])

    translations = {t["to"]: t["text"] for t in first["translations"]}

    return TranslateResponse(
        original_text=req.text,
        detected_language=detected,
        translations=translations,
        engine="nmt",
        warnings=warnings,
    )


async def detect_language(text: str, settings: Settings | None = None) -> dict:
    """Detects the source language via /detect."""
    settings = settings or get_settings()
    headers = build_auth_headers(settings)

    url = f"{settings.translator_endpoint}/detect"
    params = {"api-version": "3.0"}
    body = [{"text": text}]

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, params=params, headers=headers, json=body)
        resp.raise_for_status()
        payload = resp.json()

    return payload[0]


def _build_llm_system_prompt(req: TranslateRequest, target_language: str) -> str:
    tone_txt = f" Use a {req.tone} tone." if req.tone else ""
    gender_txt = f" Use {req.gender} grammatical gender/phrasing where the target language requires it." if req.gender else ""
    no_translate_txt = ""
    if req.no_translate_terms:
        terms = ", ".join(req.no_translate_terms)
        no_translate_txt = f" Do not translate these terms, keep them exactly as-is: {terms}."
    dict_txt = ""
    if req.dynamic_dictionary:
        pairs = "; ".join(f'"{k}" -> "{v}"' for k, v in req.dynamic_dictionary.items())
        dict_txt = f" Use these forced terminology mappings: {pairs}."
    adaptive_txt = ""
    if req.adaptive_references:
        examples = "\n".join(f'- "{r.get("source", "")}" -> "{r.get("target", "")}"' for r in req.adaptive_references)
        adaptive_txt = f"\nMatch the style/terminology of these approved reference translations:\n{examples}"

    return (
        f"You are a professional translator. Translate the user's text into {target_language} "
        f"(BCP-47 code).{tone_txt}{gender_txt}{no_translate_txt}{dict_txt}{adaptive_txt}\n"
        "Return ONLY the translated text, no explanations, no quotes."
    )


async def translate_llm(req: TranslateRequest, settings: Settings | None = None) -> TranslateResponse:
    """LLM-based translation via a Microsoft Foundry chat-completions deployment.

    Enables tone/gender controls and per-request adaptive custom translation
    (reference examples) — capabilities not available in standard NMT.
    """
    settings = settings or get_settings()
    if not settings.has_foundry_credentials:
        raise FoundryNotConfiguredError(
            "LLM-based translation requires a Microsoft Foundry resource. Set FOUNDRY_ENDPOINT and "
            "FOUNDRY_KEY (see .env.example)."
        )

    url = f"{settings.foundry_endpoint.rstrip('/')}/openai/deployments/{settings.foundry_deployment}/chat/completions"
    params = {"api-version": "2024-10-21"}
    headers = {"api-key": settings.foundry_key, "Content-Type": "application/json"}

    translations: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for target_language in req.target_languages:
            system_prompt = _build_llm_system_prompt(req, target_language)
            body = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": req.text},
                ],
                "temperature": 0.2,
            }
            resp = await client.post(url, params=params, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            translations[target_language] = data["choices"][0]["message"]["content"].strip()

    return TranslateResponse(original_text=req.text, detected_language=None, translations=translations, engine="llm")
