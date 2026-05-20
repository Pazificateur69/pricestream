from unittest.mock import patch

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestHealth:
    def test_alive_endpoint(self):
        r = APIClient().get("/alive/")
        assert r.status_code == 200
        assert r.json() == {"status": "alive"}

    def test_health_all_up(self):
        with patch("apps.pricing.health._check_database", return_value=("up", None)), patch(
            "apps.pricing.health._check_redis", return_value=("up", None)
        ), patch("apps.pricing.health._check_kafka", return_value=("up", None)):
            r = APIClient().get("/health/")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_database_down_returns_503(self):
        with patch(
            "apps.pricing.health._check_database", return_value=("down", "boom")
        ), patch("apps.pricing.health._check_redis", return_value=("up", None)), patch(
            "apps.pricing.health._check_kafka", return_value=("up", None)
        ):
            r = APIClient().get("/health/")
        assert r.status_code == 503
        assert r.json()["status"] == "critical"

    def test_health_redis_down_is_degraded_not_critical(self):
        with patch("apps.pricing.health._check_database", return_value=("up", None)), patch(
            "apps.pricing.health._check_redis", return_value=("down", "no route")
        ), patch("apps.pricing.health._check_kafka", return_value=("up", None)):
            r = APIClient().get("/health/")
        assert r.status_code == 200
        assert r.json()["status"] == "degraded"
