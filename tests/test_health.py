from app.extensions import db


def test_health_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "status": "ok",
        "database": "ok",
        "fcm_configured": False,
        "app_env": "development",
    }
    body = response.get_data(as_text=True)
    assert "DATABASE_URL" not in body
    assert "SECRET_KEY" not in body
    assert "FCM_SERVICE_ACCOUNT_PATH" not in body


def test_health_db_failure_returns_503(client, monkeypatch):
    original_execute = db.session.execute

    def broken_execute(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(db.session, "execute", broken_execute)

    response = client.get("/health")

    monkeypatch.setattr(db.session, "execute", original_execute)
    assert response.status_code == 503
    assert response.get_json() == {
        "status": "degraded",
        "database": "error",
        "fcm_configured": False,
        "app_env": "development",
    }
