# Smart Multilingual Translation Assistant

![CI](https://github.com/FairyFox5700/smart-multilingual-translation-assistant/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A hands-on FastAPI project demonstrating Azure AI Translator's core capabilities:
languages, translate (multi-target + auto-detect), transliterate, profanity filtering,
dynamic dictionary, "prevent translation", and an LLM-based translation path (tone,
gender, adaptive references) via a Microsoft Foundry deployment.

## Project structure

```
translation-assistant/
├── app/
│   ├── main.py                     FastAPI app + static frontend mount
│   ├── config.py                   Settings (env/.env)
│   ├── api/translation_routes.py   /languages /translate /detect /transliterate /health
│   ├── services/
│   │   ├── translator_service.py   Translate + detect (NMT) and LLM path (Foundry)
│   │   ├── language_service.py     Cached /languages lookup (no auth required)
│   │   └── transliteration_service.py
│   ├── models/translation.py       Pydantic request/response schemas
│   └── core/security.py            Resource-key auth header builder
├── static/                         Minimal HTML/CSS/JS frontend
├── tests/                          pytest + respx (mocked HTTP) unit tests
├── requirements.txt
└── .env.example
```

## Setup

```powershell
cd translation-assistant
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env and set TRANSLATOR_KEY / TRANSLATOR_REGION (create an Azure AI Translator
# resource in the portal to get these)
```

## Run

```powershell
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 for the UI, or http://localhost:8000/docs for the OpenAPI
explorer.

## Run tests

```powershell
pytest -v
```

Tests mock the Translator HTTP calls with `respx`, so they run without real Azure
credentials.

## API summary

| Endpoint | Method | Notes |
|---|---|---|
| `/api/health` | GET | Reports whether Translator/Foundry credentials are configured |
| `/api/languages` | GET | No auth required; cached for `CACHE_TTL_SECONDS` |
| `/api/translate` | POST | Multi-target, auto-detect, profanity action, dynamic dictionary, prevent-translation, optional LLM engine with tone/gender/adaptive references |
| `/api/detect` | POST | Language auto-detection only |
| `/api/transliterate` | POST | Script conversion (e.g. Cyrillic → Latin), distinct from translation |

### Example `/api/translate` request

```json
{
  "text": "The customer uses our premium cloud solution.",
  "target_languages": ["fr", "de", "uk"],
  "source_language": "en",
  "profanity_action": "Marked",
  "no_translate_terms": ["Microsoft Azure"],
  "dynamic_dictionary": {"premium cloud solution": "solution cloud premium"}
}
```

### Notes on per-request controls (no model training needed)

- **Dynamic dictionary** and **prevent translation** are implemented via
  `<mstrans:dictionary>` markup and require `textType=html`. The dictionary markup is
  **only applied when `source_language` is explicit** — this mirrors the real API
  restriction (a warning is returned otherwise).
- **LLM-based translation** (`use_llm: true`) requires `FOUNDRY_ENDPOINT` /
  `FOUNDRY_KEY` in `.env` — it calls a chat-completions-style deployment and supports
  `tone`, `gender`, and up to 5 `adaptive_references` per request.
- This implementation targets the **v3.0 GA** REST surface
  (`?api-version=3.0`, repeated `to=` params, root-array responses). The service layer
  is structured so a second provider implementing the 2026-06-06 `inputs`/`value`
  schema could be added behind the same `TranslateRequest`/`TranslateResponse` models.

## Testing & quality

- **Unit tests** (`tests/`) use `pytest` + `pytest-asyncio` and mock all outbound HTTP
  calls with `respx`, so the suite runs offline with no Azure credentials.
- **Linting** via `ruff` (`ruff check app tests`).
- **CI**: GitHub Actions (`.github/workflows/ci.yml`) runs lint + tests on every push
  and PR against Python 3.11 and 3.12.
- Run everything locally before pushing:

  ```powershell
  pytest -v
  ruff check app tests
  ```

## Architecture notes

- **Layered design**: `api/` (HTTP concerns) → `services/` (business logic, framework-
  agnostic) → `core/` (auth) — this keeps the Azure integration unit-testable without
  spinning up FastAPI.
- **Config via environment**: `pydantic-settings` loads from `.env`/env vars; secrets
  are never hardcoded or committed (`.env` is gitignored, only `.env.example` ships).
- **Resilience**: transient Translator errors (429/5xx) are retried with exponential
  backoff via `tenacity`.
- **Extensibility**: adding the 2026-06-06 API or a new provider means adding a new
  function in `services/`, not touching routes or models.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup, test/lint commands, and PR
guidelines.

## License

[MIT](LICENSE)

