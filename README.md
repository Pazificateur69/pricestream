# pricestream

[![CI](https://github.com/Pazificateur69/pricestream/actions/workflows/ci.yml/badge.svg)](https://github.com/Pazificateur69/pricestream/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Django 5.0](https://img.shields.io/badge/django-5.0-green.svg)](https://docs.djangoproject.com/en/5.0/)
[![Tests](https://img.shields.io/badge/tests-47%20passing-brightgreen.svg)](#tests)
[![Coverage](https://img.shields.io/badge/coverage-78%25-brightgreen.svg)](#tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A simplified institutional crypto pricing & liquidity service — inspired by what liquidity providers like B2C2 operate.**

pricestream aggregates real-time crypto prices from multiple exchanges (Binance, Coinbase, Kraken), computes a consolidated mid-price with a staleness gate, detects cross-venue arbitrage, exposes everything via REST + WebSocket + Prometheus, and streams every quote through Kafka for downstream consumers.

It is built as a portfolio piece that mirrors the shape (not the scale) of an LP's internal stack: ingest → normalise → consolidate → broadcast → roll up → observe.

---

## What's in the box

| Capability | Surface |
|---|---|
| Live dashboard | `GET /` — every instrument ticks via WebSocket, up/down colour transitions |
| REST API | `GET /api/{instruments,quotes,ohlc,arbitrage}/` |
| OpenAPI / Swagger | `GET /api/docs/` (Swagger UI), `GET /api/redoc/`, `GET /api/schema/` |
| Token auth | `POST /api/auth/token/` |
| WebSocket | `ws://.../ws/quotes/<symbol>/` — consolidated mid pushed on every tick |
| Prometheus | `GET /metrics/` — counters, histograms, gauges (see `docs/grafana-dashboard.json`) |
| Health | `GET /health/` deep probe (DB / Redis / Kafka), `GET /alive/` cheap liveness |
| Admin | `GET /admin/` |

## Architecture

```
                ┌────────────────────────────────────────────────────────────┐
                │  Public Exchange APIs (Binance / Coinbase / Kraken)        │
                └─────────────────────┬──────────────────────────────────────┘
                                      │ HTTP polling every 5s
                                      ▼
                    ┌────────────────────────────────────┐
                    │  Celery Beat → Celery Worker       │
                    │  fetch_quotes(): N venues × M sym  │
                    └─┬───────────────┬──────────────────┘
                      │ raw Quote     │ Consolidated mid
                      ▼               ▼                       ┌─────────────────┐
        ┌─────────────────────┐  ┌─────────────────┐          │  Prometheus     │
        │ PostgreSQL          │  │  Redis cache    │◄─metrics─┤  /metrics       │
        │ Quote / Consolidated│  │  + channel layer│          └─────────────────┘
        │ OHLCBar / Arbitrage │  └────────┬────────┘
        └────────┬────────────┘           │ group_send
                 │                        ▼
                 │            ┌──────────────────────────┐
                 │            │  Django Channels (Daphne)│  ws://…/ws/quotes/SYMBOL/
                 │            │  REST API (DRF)          │  /api/…/
                 │            │  Dashboard               │  /
                 │            └──────────────────────────┘
                 │
                 │ producer
                 ▼
        ┌──────────────────────┐
        │  Kafka topic         │
        │  "quotes"            │
        └─────────┬────────────┘
                  │ consumer
                  ▼
        ┌──────────────────────┐
        │  ohlc-builder svc    │  → OHLCBar 1m / 5m / 1h
        └──────────────────────┘
```

## Stack

| Layer | Tech |
|---|---|
| Web framework | Django 5.0 + Django REST Framework + drf-spectacular |
| Realtime | Django Channels + Daphne (ASGI), Redis channel layer |
| Task queue | Celery 5 + Celery Beat |
| Messaging | Apache Kafka via `confluent-kafka` |
| Storage | PostgreSQL 16 |
| Cache | Redis 7 |
| Observability | Prometheus + Grafana dashboard JSON |
| Tests | pytest + pytest-django + pytest-asyncio + factory_boy + channels.testing |
| Lint | Ruff |
| CI | GitHub Actions |
| Packaging | Docker + Docker Compose |
| Orchestration | Kubernetes manifests (`k8s/`) |

## Data model

- **Instrument** — tradable pair, e.g. `BTC-USD`.
- **Quote** — raw bid/ask from one exchange.
- **ConsolidatedPrice** — cross-venue best-bid / best-ask / mid snapshot.
- **OHLCBar** — 1m / 5m / 1h bucket built by the Kafka consumer.
- **ArbitrageOpportunity** — detected when bid on venue A > ask on venue B.

See [`apps/pricing/models.py`](apps/pricing/models.py).

## Domain logic

### Consolidation

`apps.pricing.aggregator.consolidate` drops any quote older than
`MAX_QUOTE_AGE_SECONDS` (the **staleness gate**), then takes the best bid (max)
and best ask (min) across the remaining venues. The mid is `(best_bid + best_ask) / 2`.
If the cross-venue book is crossed (unusual, but happens in volatile moves) we
fall back to a mid-of-mids so the consolidated tape never gaps.

### Arbitrage detection

`apps.pricing.aggregator.detect_arbitrage` scans every pair of venues in the
current round: if `bid_on_venue_A > ask_on_venue_B`, that's a risk-free spread
modulo fees, latency and withdrawal time. The largest opportunity is persisted
as an `ArbitrageOpportunity` row and counted in
`pricestream_arbitrage_detected_total`.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/instruments/` | List supported instruments |
| GET | `/api/quotes/?instrument=BTC-USD` | Raw quote history |
| GET | `/api/quotes/latest/?instrument=BTC-USD` | Latest consolidated mid |
| GET | `/api/ohlc/?instrument=BTC-USD&interval=1m` | OHLC bars |
| GET | `/api/arbitrage/?instrument=BTC-USD` | Detected arbitrage opportunities |
| GET | `/api/docs/` | Swagger UI |
| POST | `/api/auth/token/` | Obtain a DRF token |

Auth: DRF token (`Authorization: Token <token>`).
Rate limits: anon 60/min, user 600/min.

### WebSocket

```
ws://localhost:8000/ws/quotes/BTC-USD/
```

On connect, the client receives the last cached snapshot (no waiting for the
next tick). Subsequent updates are pushed every time `fetch_quotes` computes a
new consolidated mid.

## Quickstart

```bash
git clone https://github.com/Pazificateur69/pricestream.git
cd pricestream
cp .env.example .env
make up                 # docker compose up --build
```

Open http://localhost:8000/ — the live dashboard ticks within ~5 seconds.

```bash
# get a token
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py drf_create_token <username>

# hit the API
curl -H "Authorization: Token <token>" \
  http://localhost:8000/api/quotes/latest/?instrument=BTC-USD

# subscribe via WebSocket
websocat ws://localhost:8000/ws/quotes/BTC-USD/

# scrape metrics
curl http://localhost:8000/metrics/ | grep pricestream_
```

## Tests

```bash
make test               # 47 tests via pytest
make test-cov           # coverage report
```

47 tests covering models, DRF endpoints, the Celery task, the aggregator
(consolidation + arbitrage + staleness gate), the Kafka consumer, every
exchange client, the WebSocket consumer (via `channels.testing`), the deep
health check, the Prometheus endpoint and the OpenAPI schema.

## Observability

- Prometheus scrape endpoint at `/metrics/` exposes:
  - `pricestream_quotes_{fetched,failed,stale}_total{instrument,source}`
  - `pricestream_consolidated_total{instrument}`
  - `pricestream_arbitrage_detected_total{instrument,buy_venue,sell_venue}`
  - `pricestream_kafka_{published,publish_failed}_total`
  - `pricestream_fetch_round_duration_seconds` (Histogram)
  - `pricestream_last_{mid_price,spread_bps}{instrument}` (Gauges)
- Grafana dashboard JSON in [`docs/grafana-dashboard.json`](docs/grafana-dashboard.json).

## Kubernetes

Manifests for every component live under `k8s/`. They are not auto-deployed by
CI — they document the intended topology on EKS / GKE.

```bash
kubectl apply -f k8s/
```

## Project layout

```
pricestream/
├── apps/pricing/        # models, API, tasks, kafka, WS consumers, aggregator
│   ├── metrics.py       # Prometheus instrumentation
│   ├── health.py        # deep health checks
│   ├── aggregator.py    # consolidation + arbitrage detection
│   ├── exchanges.py     # Binance / Coinbase / Kraken clients
│   └── templates/       # dashboard.html
├── pricestream/         # Django project: settings, urls, asgi, celery
├── k8s/                 # Deployment / Service / ConfigMap / Ingress
├── scripts/             # entrypoint + wait-for-it
├── docs/                # architecture, grafana dashboard JSON
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── pyproject.toml
```

## Why this exists

This is a portfolio project that mirrors the shape of a real LP's pricing
stack at a single-laptop scale: aggregate, normalise, cache, broadcast,
roll-up, observe. Every moving part — Kafka, Channels, Celery, Prometheus,
K8s — is wired end-to-end via `make up`.

## License

MIT — see [LICENSE](LICENSE).
