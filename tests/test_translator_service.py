import pytest
import respx
from httpx import Response
from pydantic import ValidationError

from app.config import Settings
from app.models.translation import TranslateRequest
from app.services import translator_service


def make_settings(**overrides):
    base = {
        "translator_key": "test-key",
        "translator_region": "westeurope",
        "translator_endpoint": "https://api.cognitive.microsofttranslator.com",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.mark.asyncio
@respx.mock
async def test_translate_nmt_multi_target():
    settings = make_settings()
    route = respx.post("https://api.cognitive.microsofttranslator.com/translate").mock(
        return_value=Response(
            200,
            json=[
                {
                    "translations": [
                        {"text": "Bonjour", "to": "fr"},
                        {"text": "Hallo", "to": "de"},
                    ]
                }
            ],
        )
    )
    req = TranslateRequest(text="Hello", target_languages=["fr", "de"], source_language="en")
    result = await translator_service.translate_nmt(req, settings=settings)

    assert route.called
    assert result.translations == {"fr": "Bonjour", "de": "Hallo"}
    assert result.engine == "nmt"


@pytest.mark.asyncio
@respx.mock
async def test_translate_nmt_auto_detect():
    settings = make_settings()
    respx.post("https://api.cognitive.microsofttranslator.com/translate").mock(
        return_value=Response(
            200,
            json=[
                {
                    "detectedLanguage": {"language": "en", "score": 0.95},
                    "translations": [{"text": "Привіт", "to": "uk"}],
                }
            ],
        )
    )
    req = TranslateRequest(text="Hello", target_languages=["uk"])
    result = await translator_service.translate_nmt(req, settings=settings)

    assert result.detected_language.language == "en"
    assert result.detected_language.score == 0.95
    assert result.translations["uk"] == "Привіт"


@pytest.mark.asyncio
@respx.mock
async def test_translate_dynamic_dictionary_requires_source_language():
    settings = make_settings()
    route = respx.post("https://api.cognitive.microsofttranslator.com/translate").mock(
        return_value=Response(200, json=[{"translations": [{"text": "x", "to": "fr"}]}])
    )
    req = TranslateRequest(
        text="The customer uses our premium cloud solution.",
        target_languages=["fr"],
        dynamic_dictionary={"premium cloud solution": "solution cloud premium"},
    )
    result = await translator_service.translate_nmt(req, settings=settings)

    assert route.called
    sent_body = route.calls.last.request.content
    assert b"mstrans:dictionary" not in sent_body  # skipped because source_language missing
    assert any("dynamic_dictionary requires" in w for w in result.warnings)


@pytest.mark.asyncio
@respx.mock
async def test_translate_prevent_translation_markup_applied():
    settings = make_settings()
    route = respx.post("https://api.cognitive.microsofttranslator.com/translate").mock(
        return_value=Response(200, json=[{"translations": [{"text": "x", "to": "fr"}]}])
    )
    req = TranslateRequest(
        text="Microsoft Azure provides cloud computing services.",
        target_languages=["fr"],
        no_translate_terms=["Microsoft Azure"],
    )
    await translator_service.translate_nmt(req, settings=settings)

    sent_body = route.calls.last.request.content.decode()
    assert "mstrans:dictionary" in sent_body
    assert "Microsoft Azure" in sent_body


def test_target_languages_deduped_and_required():
    req = TranslateRequest(text="hi", target_languages=["fr", "fr", "de"])
    assert req.target_languages == ["fr", "de"]

    with pytest.raises(ValidationError):
        TranslateRequest(text="hi", target_languages=[])


def test_adaptive_references_limit():
    refs = [{"source": "a", "target": "b"}] * 6
    with pytest.raises(ValidationError):
        TranslateRequest(text="hi", target_languages=["fr"], adaptive_references=refs)
