"""Kafka producer for raw quote events.

We use a module-level singleton because `confluent_kafka.Producer` is thread-safe
and intentionally long-lived: it batches messages internally.
"""
from __future__ import annotations

import json
import logging
from threading import Lock

from django.conf import settings

from .models import Quote

logger = logging.getLogger(__name__)

_producer = None
_lock = Lock()


def _get_producer():
    global _producer
    if _producer is not None:
        return _producer
    with _lock:
        if _producer is None:
            from confluent_kafka import Producer

            _producer = Producer(
                {
                    "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                    "client.id": "pricestream-producer",
                    "enable.idempotence": True,
                    "acks": "all",
                    "linger.ms": 50,
                }
            )
    return _producer


def _delivery_report(err, msg) -> None:
    if err is not None:
        logger.warning("Kafka delivery failed: %s", err)


def publish_quote(symbol: str, quote: Quote) -> None:
    producer = _get_producer()
    payload = {
        "instrument": symbol,
        "source": quote.source,
        "bid": str(quote.bid),
        "ask": str(quote.ask),
        "ts": quote.timestamp.isoformat(),
    }
    producer.produce(
        topic=settings.KAFKA_QUOTES_TOPIC,
        key=symbol.encode("utf-8"),
        value=json.dumps(payload).encode("utf-8"),
        on_delivery=_delivery_report,
    )
    producer.poll(0)


def flush(timeout: float = 5.0) -> None:
    if _producer is not None:
        _producer.flush(timeout)
