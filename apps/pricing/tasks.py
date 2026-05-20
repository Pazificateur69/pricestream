"""Celery tasks — the only one that matters is `fetch_quotes`, scheduled by Beat."""
from __future__ import annotations

import logging
import time
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from . import metrics
from .aggregator import consolidate, detect_arbitrage
from .exchanges import all_clients
from .models import ArbitrageOpportunity, ConsolidatedPrice, Instrument, Quote

logger = logging.getLogger(__name__)

CACHE_KEY_FMT = "pricestream:mid:{symbol}"


@shared_task(name="apps.pricing.tasks.fetch_quotes")
def fetch_quotes() -> dict:
    """Poll every configured exchange for every active instrument."""
    start = time.perf_counter()
    clients = all_clients()
    Instrument.objects.bulk_create(
        [
            Instrument(
                symbol=s,
                base=Instrument.parse_symbol(s)[0],
                quote=Instrument.parse_symbol(s)[1],
            )
            for s in settings.INSTRUMENTS
        ],
        ignore_conflicts=True,
    )

    written = 0
    consolidated_written = 0
    arbs = 0

    for instrument in Instrument.objects.filter(
        is_active=True, symbol__in=settings.INSTRUMENTS
    ):
        round_quotes: list[Quote] = []
        for client in clients:
            result = client.fetch(instrument.symbol)
            if result is None:
                metrics.quotes_failed_total.labels(
                    instrument=instrument.symbol, source=client.name
                ).inc()
                continue
            bid, ask = result
            quote = Quote.objects.create(
                instrument=instrument,
                source=client.name,
                bid=bid,
                ask=ask,
                timestamp=timezone.now(),
            )
            round_quotes.append(quote)
            written += 1
            metrics.quotes_fetched_total.labels(
                instrument=instrument.symbol, source=client.name
            ).inc()
            _publish_to_kafka(instrument.symbol, quote)

        consolidated = consolidate(round_quotes)
        if consolidated is None:
            continue

        cp = ConsolidatedPrice.objects.create(
            instrument=instrument,
            mid=consolidated.mid,
            bid=consolidated.bid,
            ask=consolidated.ask,
            sources=consolidated.sources,
        )
        consolidated_written += 1
        metrics.consolidated_total.labels(instrument=instrument.symbol).inc()
        metrics.last_mid_price.labels(instrument=instrument.symbol).set(float(cp.mid))
        if cp.mid > 0:
            spread_bps = float((cp.ask - cp.bid) / cp.mid) * 10000
            metrics.last_spread_bps.labels(instrument=instrument.symbol).set(spread_bps)

        cache.set(
            CACHE_KEY_FMT.format(symbol=instrument.symbol),
            {
                "mid": str(cp.mid),
                "bid": str(cp.bid),
                "ask": str(cp.ask),
                "sources": cp.sources,
                "ts": cp.timestamp.isoformat(),
            },
            timeout=60,
        )
        _broadcast_ws(instrument.symbol, cp)

        # Cross-venue arbitrage detection.
        arb = detect_arbitrage(round_quotes)
        if arb is not None:
            ArbitrageOpportunity.objects.create(
                instrument=instrument,
                buy_venue=arb.buy_venue,
                buy_price=arb.buy_price,
                sell_venue=arb.sell_venue,
                sell_price=arb.sell_price,
                spread=arb.spread,
                spread_bps=arb.spread_bps.quantize(Decimal("0.0001")),
            )
            metrics.arbitrage_detected_total.labels(
                instrument=instrument.symbol,
                buy_venue=arb.buy_venue,
                sell_venue=arb.sell_venue,
            ).inc()
            arbs += 1

    metrics.fetch_round_duration_seconds.observe(time.perf_counter() - start)
    return {"quotes": written, "consolidated": consolidated_written, "arbitrages": arbs}


def _publish_to_kafka(symbol: str, quote: Quote) -> None:
    """Fire-and-forget Kafka publish — errors are logged, never raised."""
    try:
        from .kafka_producer import publish_quote
    except Exception as exc:  # pragma: no cover - import-time guard
        logger.warning("Kafka producer unavailable: %s", exc)
        return
    try:
        publish_quote(symbol, quote)
        metrics.kafka_published_total.labels(topic=settings.KAFKA_QUOTES_TOPIC).inc()
    except Exception as exc:
        metrics.kafka_publish_failed_total.inc()
        logger.warning("Kafka publish failed for %s: %s", symbol, exc)


def _broadcast_ws(symbol: str, cp: ConsolidatedPrice) -> None:
    """Push the consolidated price to subscribers of the matching WS group."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except Exception:  # pragma: no cover
        return
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"quotes.{symbol}",
        {
            "type": "quote.update",
            "payload": {
                "instrument": symbol,
                "mid": str(cp.mid),
                "bid": str(cp.bid),
                "ask": str(cp.ask),
                "sources": cp.sources,
                "ts": cp.timestamp.isoformat(),
            },
        },
    )
