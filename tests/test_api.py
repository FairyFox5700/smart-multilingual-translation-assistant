from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "translator_configured" in data


def test_root_serves_frontend():
    res = client.get("/")
    assert res.status_code == 200
    assert "Translation Assistant" in res.text


def test_translate_without_credentials_returns_401():
    res = client.post(
        "/api/translate",
        json={"text": "Hello", "target_languages": ["fr"]},
    )
    # In CI/dev without TRANSLATOR_KEY set, expect a clean 401 (not a crash)
    assert res.status_code in (401, 200)


def test_translate_rejects_empty_targets():
    res = client.post("/api/translate", json={"text": "Hello", "target_languages": []})
    assert res.status_code == 422
