"""Kafka consumer that turns raw quote events into OHLCBar rows.

Runs as a dedicated service (`kafka-consumer` in docker-compose / its own K8s
Deployment). Bucketing is done in pure Python — no Kafka Streams / KSQL.
"""
from __future__ import annotations

import json
import logging
import signal
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Instrument, OHLCBar

logger = logging.getLogger(__name__)

INTERVAL_TO_DELTA = {
    OHLCBar.Interval.M1: timedelta(minutes=1),
    OHLCBar.Interval.M5: timedelta(minutes=5),
    OHLCBar.Interval.H1: timedelta(hours=1),
}


def _bucket_start(ts: datetime, interval: str) -> datetime:
    delta = INTERVAL_TO_DELTA[interval]
    epoch = datetime(1970, 1, 1, tzinfo=ts.tzinfo)
    seconds = int((ts - epoch).total_seconds())
    bucket_seconds = int(delta.total_seconds())
    floored = (seconds // bucket_seconds) * bucket_seconds
    return epoch + timedelta(seconds=floored)


def _update_bar(instrument: Instrument, interval: str, ts: datetime, price: Decimal) -> None:
    bucket = _bucket_start(ts, interval)
    with transaction.atomic():
        bar, created = OHLCBar.objects.select_for_update().get_or_create(
            instrument=instrument,
            interval=interval,
            bucket_start=bucket,
            defaults={
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": Decimal(0),
                "tick_count": 1,
            },
        )
        if not created:
            bar.high = max(bar.high, price)
            bar.low = min(bar.low, price)
            bar.close = price
            bar.tick_count += 1
            bar.save(update_fields=("high", "low", "close", "tick_count"))


def run_consumer(*, stop_after: int | None = None) -> int:
    """Run the consumer loop. `stop_after` is used in tests to bound runs."""
    from confluent_kafka import Consumer

    consumer = Consumer(
        {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": "pricestream-ohlc-builder",
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
        }
    )
    consumer.subscribe([settings.KAFKA_QUOTES_TOPIC])

    running = True

    def _stop(*_args) -> None:
        nonlocal running
        running = False
        logger.info("Kafka consumer received stop signal.")

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    processed = 0
    try:
        while running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.warning("Kafka error: %s", msg.error())
                continue
            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except Exception as exc:
                logger.warning("Bad kafka payload: %s", exc)
                continue
            handle_event(payload)
            processed += 1
            if stop_after is not None and processed >= stop_after:
                break
    finally:
        consumer.close()
    return processed


def handle_event(payload: dict) -> None:
    """Consume one event payload and update bars for every configured interval."""
    symbol = payload.get("instrument")
    if not symbol:
        return
    try:
        instrument = Instrument.objects.get(symbol=symbol)
    except Instrument.DoesNotExist:
        return

    try:
        bid = Decimal(payload["bid"])
        ask = Decimal(payload["ask"])
    except Exception:
        return
    mid = (bid + ask) / Decimal(2)

    import contextlib

    ts_str = payload.get("ts")
    ts = timezone.now()
    if ts_str:
        with contextlib.suppress(ValueError):
            ts = datetime.fromisoformat(ts_str)

    for interval in (OHLCBar.Interval.M1, OHLCBar.Interval.M5, OHLCBar.Interval.H1):
        _update_bar(instrument, interval, ts, mid)
