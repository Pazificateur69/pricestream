# pricestream

[![CI](https://github.com/Pazificateur69/pricestream/actions/workflows/ci.yml/badge.svg)](https://github.com/Pazificateur69/pricestream/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Django 5.0](https://img.shields.io/badge/django-5.0-green.svg)](https://docs.djangoproject.com/en/5.0/)
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](#tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A simplified institutional crypto pricing & liquidity service — inspired by what liquidity providers like B2C2 operate.**

pricestream aggregates real-time crypto prices from multiple exchanges (Binance, Coinbase, Kraken), computes a consolidated mid-price, exposes it via REST + WebSocket, and streams every quote through Kafka for downstream event-driven consumers (OHLC builder, analytics, risk).

This repo demonstrates a production-shaped architecture: Django 5 + DRF + Celery + Channels + Kafka + PostgreSQL + Redis, containerised with Docker Compose and shipped with Kubernetes manifests + CI.

---

## Architecture

```
                 ┌────────────────────────────────────────────────────────────┐
                 │  Public Exchange APIs (Binance / Coinbase / Kraken)        │
                 └─────────────────────┬──────────────────────────────────────┘
                                       │ HTTP polling every 5s
                                       ▼
                            ┌────────────────────┐
                            │  Celery Beat       │   schedules
                            │  Celery Worker     │   fetch_quotes()
                            └─────────┬──────────┘
                                      │ writes Quote rows
                                      ▼
        ┌─────────────────┐    ┌──────────────┐    ┌───────────────┐
        │  PostgreSQL     │◄───┤  Django app  ├───►│  Redis cache  │
        │  (Quote, OHLC…) │    │  (DRF + WS)  │    │  (mid-price)  │
        └─────────────────┘    └──────┬───────┘    └───────────────┘
                                      │ produces
                                      ▼
                            ┌────────────────────┐
                            │  Kafka topic       │
                            │  "quotes"          │
                            └─────────┬──────────┘
                                      │ consumes
                                      ▼
                            ┌────────────────────┐
                            │  Kafka consumer    │  builds OHLCBar
                            │  (separate svc)    │  rolling buckets
                            └────────────────────┘

      ┌──────────────────────────────────────────────────────────┐
      │  Clients: REST /api/quotes/  or  WebSocket /ws/quotes/.. │
      └──────────────────────────────────────────────────────────┘
```

## Stack

| Layer | Tech |
|---|---|
| Web framework | Django 5.0 + Django REST Framework |
| Realtime | Django Channels (ASGI / Daphne) + Redis channel layer |
| Task queue | Celery 5 + Celery Beat |
| Messaging | Apache Kafka (`confluent-kafka` client) |
| Storage | PostgreSQL 16 |
| Cache | Redis 7 |
| Tests | pytest + pytest-django + factory_boy |
| Lint | Ruff |
| CI | GitHub Actions |
| Packaging | Docker + Docker Compose |
| Orchestration | Kubernetes manifests (`k8s/`) |

## Data model

- **Instrument** — tradable pair (e.g. `BTC-USD`).
- **Quote** — `bid`, `ask`, `source` (exchange), `timestamp`.
- **ConsolidatedPrice** — mid-price aggregated across exchanges, with the snapshot of inputs.
- **OHLCBar** — open / high / low / close / volume for a given interval.

See [`apps/pricing/models.py`](apps/pricing/models.py).

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/instruments/` | List supported instruments |
| GET | `/api/quotes/?instrument=BTC-USD` | Quote history for an instrument |
| GET | `/api/quotes/latest/?instrument=BTC-USD` | Latest consolidated mid-price |
| GET | `/api/ohlc/?instrument=BTC-USD&interval=1m` | OHLC bars |
| POST | `/api/auth/token/` | Obtain a DRF token |

Auth: DRF token (`Authorization: Token <token>`).

### WebSocket

```
ws://localhost:8000/ws/quotes/BTC-USD/
```

The client receives a JSON payload `{instrument, mid, bid, ask, ts, sources}` every time a new consolidated price is computed.

## Quickstart

```bash
git clone https://github.com/Pazificateur69/pricestream.git
cd pricestream
cp .env.example .env

docker compose up --build
# wait ~30s for Kafka to be ready, the worker starts polling exchanges
```

Then:

```bash
# create a superuser + token
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py drf_create_token <username>

# hit the API
curl -H "Authorization: Token <token>" http://localhost:8000/api/quotes/latest/?instrument=BTC-USD

# subscribe via WebSocket
websocat ws://localhost:8000/ws/quotes/BTC-USD/
```

## Tests

```bash
docker compose run --rm web pytest -v --cov=apps --cov-report=term-missing
```

Covers:
- Model invariants (Quote, ConsolidatedPrice, OHLCBar)
- DRF endpoints (auth, filtering, pagination)
- The `fetch_quotes` Celery task (mocked exchange clients)
- Mid-price aggregator
- Kafka producer (mocked)

Fixtures are generated with `factory_boy` (see `apps/pricing/tests/factories.py`).

## Kubernetes

The `k8s/` folder ships manifests (Deployment / Service / ConfigMap) for every component (web, postgres, redis, celery worker, celery beat, kafka consumer). They are not auto-deployed by CI — they document the intended topology on EKS / GKE.

```bash
kubectl apply -f k8s/
```

## Project layout

```
pricestream/
├── apps/pricing/        # Django app: models, API, tasks, kafka, WS consumers
├── pricestream/         # Django project: settings, urls, asgi, celery
├── k8s/                 # Kubernetes manifests
├── scripts/             # entrypoint + wait-for-it
├── docs/                # architecture notes
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## Why this exists

This is a portfolio project that mirrors the kind of infrastructure an institutional liquidity provider runs at a small scale: aggregate, normalise, cache, broadcast. Every moving part (Kafka, Channels, Celery, K8s) is wired end-to-end on a single laptop with `docker compose up`.

## License

MIT — see [LICENSE](LICENSE).
