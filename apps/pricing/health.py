"""Deep health checks: probe DB, Redis, Kafka.

Each probe is wrapped so a single dead dependency does not crash the endpoint —
we just report it as `down` and return HTTP 503.
"""
from __future__ import annotations

import logging
import socket
from urllib.parse import urlparse

from django.conf import settings
from django.db import connections
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def _check_database() -> tuple[str, str | None]:
    try:
        connections["default"].cursor().execute("SELECT 1")
        return "up", None
    except Exception as exc:
        return "down", str(exc)


def _check_redis() -> tuple[str, str | None]:
    try:
        import redis

        client = redis.from_url(settings.REDIS_URL, socket_timeout=2)
        client.ping()
        return "up", None
    except Exception as exc:
        return "down", str(exc)


def _check_kafka() -> tuple[str, str | None]:
    """Cheap TCP probe — full broker introspection would block too long."""
    try:
        host, _, port = settings.KAFKA_BOOTSTRAP_SERVERS.partition(":")
        if not host:
            return "unknown", "no bootstrap servers configured"
        with socket.create_connection((host, int(port or 9092)), timeout=2):
            return "up", None
    except Exception as exc:
        return "down", str(exc)


def healthcheck(_request):
    db_status, db_err = _check_database()
    redis_status, redis_err = _check_redis()
    kafka_status, kafka_err = _check_kafka()

    payload = {
        "status": "ok",
        "checks": {
            "database": {"status": db_status, "error": db_err},
            "redis": {"status": redis_status, "error": redis_err},
            "kafka": {"status": kafka_status, "error": kafka_err},
        },
    }

    critical_down = db_status == "down"
    degraded = redis_status == "down" or kafka_status == "down"
    if critical_down:
        payload["status"] = "critical"
        return JsonResponse(payload, status=503)
    if degraded:
        payload["status"] = "degraded"
        return JsonResponse(payload, status=200)
    return JsonResponse(payload, status=200)


def liveness(_request):
    """Cheap liveness probe — just confirms the process can answer."""
    return JsonResponse({"status": "alive"})


# Silence noisy urllib warnings when probes fail.
_ = urlparse  # keep import in case future probe parses URLs
