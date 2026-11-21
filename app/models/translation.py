"""Pydantic request/response models for the translation assistant API."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ProfanityAction = Literal["NoAction", "Marked", "Deleted"]
ProfanityMarker = Literal["Asterisk", "Tag"]
ToneOption = Literal["formal", "informal", "neutral"]
GenderOption = Literal["feminine", "masculine", "neutral"]
TextType = Literal["plain", "html"]


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Source text to translate")
    target_languages: list[str] = Field(..., min_length=1, description="BCP-47 target language codes, e.g. ['fr', 'de', 'uk']")
    source_language: str | None = Field(None, description="BCP-47 source language code. Omit to auto-detect.")
    profanity_action: ProfanityAction = "NoAction"
    profanity_marker: ProfanityMarker = "Asterisk"
    text_type: TextType = "plain"
    # Dynamic dictionary: {"cloud": "nube corporativa"} -> wraps phrase with <mstrans:dictionary> markup.
    # Only applied when source_language is explicitly set (API restriction).
    dynamic_dictionary: dict[str, str] | None = Field(
        default=None, description="Map of source phrase -> forced translation. Requires source_language to be set."
    )
    # Prevent translation: literal spans (e.g. brand names) passed through untouched via <mstrans:dictionary notranslate>.
    no_translate_terms: list[str] | None = Field(default=None, description="Phrases to leave untranslated, e.g. ['Microsoft Azure']")

    # LLM-based translation controls (require a Microsoft Foundry resource)
    use_llm: bool = Field(default=False, description="Use LLM-based translation instead of standard NMT")
    tone: ToneOption | None = None
    gender: GenderOption | None = None
    adaptive_references: list[dict[str, str]] | None = Field(
        default=None,
        description="Up to 5 reference translations: [{'source': '...', 'target': '...'}] to steer LLM style/terminology",
    )

    @field_validator("target_languages")
    @classmethod
    def _dedupe_targets(cls, v: list[str]) -> list[str]:
        seen: list[str] = []
        for lang in v:
            lang = lang.strip()
            if lang and lang not in seen:
                seen.append(lang)
        if not seen:
            raise ValueError("At least one target language is required")
        return seen

    @field_validator("adaptive_references")
    @classmethod
    def _limit_references(cls, v):
        if v and len(v) > 5:
            raise ValueError("adaptive_references supports at most 5 reference translations per request")
        return v


class DetectedLanguage(BaseModel):
    language: str
    score: float


class TranslateResponse(BaseModel):
    original_text: str
    detected_language: DetectedLanguage | None = None
    translations: dict[str, str]
    engine: Literal["nmt", "llm"] = "nmt"
    warnings: list[str] = Field(default_factory=list)


class DetectRequest(BaseModel):
    text: str = Field(..., min_length=1)


class DetectResponse(BaseModel):
    language: str
    score: float
    is_translation_supported: bool
    is_transliteration_supported: bool


class TransliterateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    language: str = Field(..., description="BCP-47 language code, e.g. 'uk'")
    from_script: str = Field(..., description="Source script code, e.g. 'Cyrl'")
    to_script: str = Field(..., description="Target script code, e.g. 'Latn'")


class TransliterateResponse(BaseModel):
    text: str
    script: str


class LanguageInfo(BaseModel):
    code: str
    name: str
    native_name: str
    dir: str = "ltr"


class LanguagesResponse(BaseModel):
    translation: dict[str, LanguageInfo] = Field(default_factory=dict)
    transliteration: dict[str, dict] = Field(default_factory=dict)
