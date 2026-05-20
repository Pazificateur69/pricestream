# Architecture

## Why this shape

pricestream models a stripped-down version of what a market-making / liquidity
provider operates internally. Three concerns drive the design:

1. **Latency-bounded ingest** — quotes from N exchanges must be pulled, normalised,
   and made queryable on a sub-second budget. Celery + Redis is good enough for
   a 5s polling cadence; in production this would be replaced by exchange
   WebSocket feeds running inside `aiokafka` / `asyncio` consumers.
2. **Event-driven downstream** — every raw quote is published to Kafka so any
   number of independent consumers (OHLC builder, risk engine, P&L attribution,
   compliance audit log) can subscribe without coupling to the writer.
3. **Real-time dissemination** — internal clients (a trader UI, an algo) connect
   over WebSocket and receive the consolidated mid-price as soon as it's
   recomputed. This is handled by Django Channels with a Redis channel layer.

## Components

| Service | Role |
|---|---|
| `web` (Daphne / ASGI) | DRF REST API, admin, WebSocket endpoints |
| `celery-worker` | Executes `fetch_quotes` and any future tasks |
| `celery-beat` | Schedules `fetch_quotes` every `FETCH_INTERVAL_SECONDS` |
| `kafka-consumer` | Builds 1m / 5m / 1h OHLC bars from the `quotes` topic |
| `postgres` | Source of truth for Instruments, Quotes, ConsolidatedPrices, OHLCBars |
| `redis` | Celery broker, cache for last mid-price, Channels layer |
| `kafka` | Event bus for raw quote events |

## Aggregation logic

`apps.pricing.aggregator.consolidate` computes:

```
best_bid = max(bid_i)            # tightest bid across venues
best_ask = min(ask_i)            # tightest ask across venues
mid       = (best_bid + best_ask) / 2
```

When the resulting book is crossed (i.e. `best_bid > best_ask`, possible during
volatile moves when one feed lags), we fall back to a mid-of-mids to remain
publishable. A production system would also reject venues whose timestamps lag
by more than a threshold (staleness gate) and weight by depth.

## Trade-offs

- **Polling vs streaming:** polling is simpler and cross-exchange uniform; the
  cost is 5s of staleness vs WebSocket feeds. For demo purposes that's fine.
- **Postgres for time series:** at higher volumes we would partition by day or
  move history to a column store (ClickHouse, TimescaleDB). The codebase keeps
  the model layer small so swapping the backend is cheap.
- **Kafka in-process producer:** we use the synchronous `confluent_kafka`
  producer with `linger.ms=50` to batch messages. The worker is fire-and-forget
  on the result — broker outages do not block the ingest path.

## Failure modes

- **Exchange API down:** the client returns `None`; aggregation proceeds with
  the remaining venues. If all venues fail, no consolidated price is written.
- **Kafka broker unreachable:** the producer logs and continues. Quotes are
  still persisted to Postgres; OHLC bars will lag until the consumer reconnects.
- **Redis down:** the cache layer is degraded; the WS layer will reject
  group_send. The REST API stays up.
