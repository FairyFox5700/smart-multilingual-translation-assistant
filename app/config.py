"""Application configuration loaded from environment variables / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Azure AI Translator (resource-key auth)
    translator_key: str = ""
    translator_region: str = ""
    translator_endpoint: str = "https://api.cognitive.microsofttranslator.com"

    # Microsoft Foundry (for LLM-based translation: tone, gender, adaptive)
    foundry_endpoint: str = ""
    foundry_key: str = ""
    foundry_deployment: str = "gpt-5.1"

    app_env: str = "development"
    cache_ttl_seconds: int = 3600

    @property
    def has_translator_credentials(self) -> bool:
        return bool(self.translator_key and self.translator_region)

    @property
    def has_foundry_credentials(self) -> bool:
        return bool(self.foundry_endpoint and self.foundry_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
