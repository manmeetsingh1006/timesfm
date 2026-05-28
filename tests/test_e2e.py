from fastapi.testclient import TestClient
import server.app as app_module


def test_forecast_e2e():
    # Force model load (uses cached weights if present)
    app_module.load_model()
    client = TestClient(app_module.app)
    health = client.get('/health')
    assert health.status_code == 200
    assert 'model_loaded' in health.json()

    payload = {'horizon': 6, 'series': list(range(1, 51))}
    headers = {}
    api_key = getattr(app_module, 'API_KEY', None)
    if api_key:
        headers['X-API-Key'] = api_key
    resp = client.post('/forecast', json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert 'point' in data and 'quantiles' in data
    assert len(data['point']) == payload['horizon']
    assert len(data['quantiles']) == payload['horizon']
