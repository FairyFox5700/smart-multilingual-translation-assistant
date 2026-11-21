"""FastAPI routes exposing the translation assistant's REST API."""
import httpx
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.core.security import TranslatorAuthError
from app.models.translation import (
    DetectRequest,
    DetectResponse,
    LanguagesResponse,
    TranslateRequest,
    TranslateResponse,
    TransliterateRequest,
    TransliterateResponse,
)
from app.services import language_service, translator_service, transliteration_service
from app.services.translator_service import FoundryNotConfiguredError

router = APIRouter()


@router.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "translator_configured": settings.has_translator_credentials,
        "foundry_configured": settings.has_foundry_credentials,
    }


@router.get("/languages", response_model=LanguagesResponse)
async def languages():
    try:
        return await language_service.get_languages()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Translator /languages: {exc}") from exc


@router.post("/translate", response_model=TranslateResponse)
async def translate(req: TranslateRequest):
    try:
        if req.use_llm:
            return await translator_service.translate_llm(req)
        return await translator_service.translate_nmt(req)
    except TranslatorAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except FoundryNotConfiguredError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Translator request failed: {exc}") from exc


@router.post("/detect", response_model=DetectResponse)
async def detect(req: DetectRequest):
    try:
        result = await translator_service.detect_language(req.text)
    except TranslatorAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Translator request failed: {exc}") from exc

    return DetectResponse(
        language=result["language"],
        score=result["score"],
        is_translation_supported=result.get("isTranslationSupported", True),
        is_transliteration_supported=result.get("isTransliterationSupported", False),
    )


@router.post("/transliterate", response_model=TransliterateResponse)
async def transliterate(req: TransliterateRequest):
    try:
        return await transliteration_service.transliterate(
            text=req.text, language=req.language, from_script=req.from_script, to_script=req.to_script
        )
    except TranslatorAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Translator request failed: {exc}") from exc
