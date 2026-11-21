"""Smart Multilingual Translation Assistant — FastAPI entrypoint."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.translation_routes import router as translation_router

app = FastAPI(
    title="Smart Multilingual Translation Assistant",
    description="A demo app covering Azure AI Translator: languages, translate, transliterate, "
    "auto-detect, profanity filtering, dynamic dictionary, prevent-translation, and LLM-based "
    "translation (tone/gender/adaptive) via Microsoft Foundry.",
    version="1.0.0",
)

app.include_router(translation_router, prefix="/api")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")
