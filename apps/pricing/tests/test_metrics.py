from rest_framework.test import APIClient


def test_metrics_endpoint_returns_prometheus_format():
    r = APIClient().get("/metrics/")
    assert r.status_code == 200
    body = r.content.decode("utf-8")
    assert "pricestream_quotes_fetched_total" in body
    assert "pricestream_fetch_round_duration_seconds" in body
    assert r["Content-Type"].startswith("text/plain")


def test_openapi_schema_endpoint():
    r = APIClient().get("/api/schema/?format=json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["openapi"].startswith("3.")
    paths = schema["paths"]
    assert "/api/instruments/" in paths
    assert "/api/quotes/" in paths
    assert "/api/arbitrage/" in paths
