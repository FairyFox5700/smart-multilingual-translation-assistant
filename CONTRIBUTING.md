# Contributing

Thanks for your interest in improving the Smart Multilingual Translation Assistant!

## Development setup

```powershell
git clone https://github.com/FairyFox5700/smart-multilingual-translation-assistant.git
cd smart-multilingual-translation-assistant
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

## Running locally

```powershell
uvicorn app.main:app --reload --port 8000
```

## Tests and linting

All HTTP calls to Azure AI Translator are mocked with `respx`, so tests run without
real credentials.

```powershell
pytest -v
ruff check app tests
```

Please keep tests passing and lint-clean before opening a PR. CI (`.github/workflows/ci.yml`)
runs both on every push and pull request against Python 3.11 and 3.12.

## Guidelines

- Keep the service layer (`app/services/`) free of FastAPI-specific types so it stays
  testable in isolation.
- Add/extend tests under `tests/` for any new endpoint, markup behavior, or provider.
- Favor small, focused pull requests with a clear description of the change and why.
- Do not commit secrets — `.env` is gitignored; use `.env.example` to document new
  required variables.
