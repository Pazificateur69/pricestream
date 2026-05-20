# Changelog

All notable changes to pricestream are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Live dashboard** at `/` — every configured instrument streams a consolidated
  mid via WebSocket; up/down colour transitions, source pills, dark theme.
- **Prometheus metrics** at `/metrics/` — counters for quotes fetched/failed/stale,
  consolidated prices, arbitrage opportunities, Kafka publishes; histograms for
  fetch-round duration; gauges for last mid-price and spread (bps).
- **OpenAPI 3 schema** via `drf-spectacular` — Swagger UI at `/api/docs/`, Redoc
  at `/api/redoc/`, machine-readable schema at `/api/schema/`.
- **ArbitrageOpportunity** model and `/api/arbitrage/` endpoint. The aggregator
  now scans for cross-venue bid > ask situations after each fetch round.
- **Staleness gate** in `consolidate()` — quotes older than
  `MAX_QUOTE_AGE_SECONDS` are dropped before computing the mid.
- **Deep health checks** at `/health/` that probe DB / Redis / Kafka; cheap
  liveness probe at `/alive/`.
- **Rate limiting** via DRF throttling (anon: 60/min, user: 600/min).
- **DX**: `Makefile`, `.pre-commit-config.yaml`, `CHANGELOG.md`, expanded README.
- **Observability**: Grafana dashboard JSON in `docs/grafana-dashboard.json`.

### Changed
- `fetch_quotes` now instruments every step with Prometheus counters and an
  end-to-end histogram of the round duration.
- README updated with the new endpoints, screenshots-ready dashboard, and an
  expanded architecture diagram.

## [0.1.0] — 2026-05-20

### Added
- Initial release: Django 5 + DRF + Celery + Celery Beat + Kafka + Channels +
  PostgreSQL + Redis.
- Polled exchange clients for Binance, Coinbase, Kraken.
- Consolidated mid-price aggregation with best-bid / best-ask logic.
- DRF endpoints for Instruments, Quotes (`/latest/`), OHLC bars.
- WebSocket subscription per instrument at `/ws/quotes/<symbol>/`.
- Kafka pipeline: producer publishes every quote; a separate consumer service
  builds 1m / 5m / 1h OHLC bars.
- Docker Compose for the full local stack; Kubernetes manifests under `k8s/`.
- GitHub Actions CI: ruff lint + pytest with coverage report.
- pytest suite covering models, API, Celery task, aggregator, Kafka consumer.
