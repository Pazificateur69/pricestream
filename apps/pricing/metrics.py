"""Prometheus metrics exposed by the pricing service.

The naming convention is `pricestream_<resource>_<unit>_<aggregator>` to play nicely
with Grafana panels that auto-suggest based on naming conventions.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

quotes_fetched_total = Counter(
    "pricestream_quotes_fetched_total",
    "Number of Quote rows persisted from an exchange poll.",
    labelnames=("instrument", "source"),
)

quotes_failed_total = Counter(
    "pricestream_quotes_failed_total",
    "Number of failed exchange fetches.",
    labelnames=("instrument", "source"),
)

consolidated_total = Counter(
    "pricestream_consolidated_total",
    "Number of ConsolidatedPrice rows produced.",
    labelnames=("instrument",),
)

stale_quotes_total = Counter(
    "pricestream_stale_quotes_total",
    "Number of quotes dropped by the staleness gate during aggregation.",
    labelnames=("instrument", "source"),
)

arbitrage_detected_total = Counter(
    "pricestream_arbitrage_detected_total",
    "Number of cross-venue arbitrage opportunities recorded.",
    labelnames=("instrument", "buy_venue", "sell_venue"),
)

kafka_published_total = Counter(
    "pricestream_kafka_published_total",
    "Quote messages produced to Kafka.",
    labelnames=("topic",),
)

kafka_publish_failed_total = Counter(
    "pricestream_kafka_publish_failed_total",
    "Quote messages whose Kafka produce call raised.",
)

fetch_round_duration_seconds = Histogram(
    "pricestream_fetch_round_duration_seconds",
    "End-to-end duration of a fetch_quotes round (all instruments, all venues).",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)

last_mid_price = Gauge(
    "pricestream_last_mid_price",
    "Latest consolidated mid-price written to the database.",
    labelnames=("instrument",),
)

last_spread_bps = Gauge(
    "pricestream_last_spread_bps",
    "Latest consolidated spread expressed in basis points.",
    labelnames=("instrument",),
)

ws_clients = Gauge(
    "pricestream_ws_clients",
    "Number of currently connected WebSocket clients.",
    labelnames=("instrument",),
)
