import importlib
import os
import io
import numpy as np
from fastapi.testclient import TestClient


class DummyModel:
    def forecast(self, horizon, series_batch):
        batch_size = len(series_batch)
        point = np.zeros((batch_size, horizon), dtype=float)
        quantiles = np.zeros((batch_size, horizon, 3), dtype=float)
        for i in range(batch_size):
            point[i] = np.arange(1, horizon + 1, dtype=float)
            quantiles[i, :, 1] = point[i]
        return point, quantiles


def setup_app(monkeypatch, key_value=None):
    if key_value is None:
        monkeypatch.delenv("TIMESFM_API_KEY", raising=False)
    else:
        monkeypatch.setenv("TIMESFM_API_KEY", key_value)

    import server.app as app_module
    importlib.reload(app_module)
    app_module.app.router.on_startup.clear()
    app_module.MODEL = DummyModel()
    return app_module.app


def test_forecast_allowed_when_api_key_not_set(monkeypatch):
    app = setup_app(monkeypatch, key_value=None)
    client = TestClient(app)
    response = client.post("/forecast", json={"horizon": 3, "series": [1, 2, 3]})
    assert response.status_code == 200
    data = response.json()
    assert data["point"] == [1.0, 2.0, 3.0]


def test_forecast_requires_api_key_when_configured(monkeypatch):
    app = setup_app(monkeypatch, key_value="secret-key")
    client = TestClient(app)

    no_header = client.post("/forecast", json={"horizon": 3, "series": [1, 2, 3]})
    assert no_header.status_code == 401

    bad_header = client.post(
        "/forecast",
        headers={"X-API-Key": "wrong-key"},
        json={"horizon": 3, "series": [1, 2, 3]},
    )
    assert bad_header.status_code == 401

    ok_header = client.post(
        "/forecast",
        headers={"X-API-Key": "secret-key"},
        json={"horizon": 3, "series": [1, 2, 3]},
    )
    assert ok_header.status_code == 200
    assert ok_header.json()["point"] == [1.0, 2.0, 3.0]


def test_forecast_accepts_authorization_bearer(monkeypatch):
    app = setup_app(monkeypatch, key_value="secret-key")
    client = TestClient(app)
    response = client.post(
        "/forecast",
        headers={"Authorization": "Bearer secret-key"},
        json={"horizon": 2, "series": [1, 2]},
    )
    assert response.status_code == 200
    assert response.json()["point"] == [1.0, 2.0]


def test_forecast_csv_requires_api_key_when_configured(monkeypatch):
    app = setup_app(monkeypatch, key_value="secret-key")
    client = TestClient(app)
    csv_body = "date,value\n2026-01-01,1\n2026-01-02,2\n"

    response = client.post(
        "/forecast_csv",
        files={"file": ("test.csv", csv_body, "text/csv")},
        data={"horizon": 2},
    )
    assert response.status_code == 401

    response = client.post(
        "/forecast_csv",
        headers={"X-API-Key": "secret-key"},
        files={"file": ("test.csv", csv_body, "text/csv")},
        data={"horizon": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("point"), list)
    assert isinstance(data.get("quantiles"), list)
