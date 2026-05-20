# Contributing

## Local setup

```bash
cp .env.example .env
make up           # full docker compose stack
make test         # pytest in the web container
make lint         # ruff
```

## Pre-commit

```bash
pip install pre-commit
pre-commit install
```

`ruff` and `ruff-format` are run on every commit.

## Commit hygiene

- Subject line: ≤72 chars, imperative ("Add foo", not "Added foo")
- Reference the affected area when relevant: `aggregator:`, `kafka:`, `ws:` …
- Keep one concern per commit when possible.

## Testing convention

- `apps/pricing/tests/test_<module>.py` mirrors `apps/pricing/<module>.py`.
- Use `factory_boy` factories from `apps/pricing/tests/factories.py` for DB rows.
- External dependencies (HTTP, Kafka, Redis) must be mocked in unit tests.
