#!/usr/bin/env bash
set -euo pipefail

CMD="${1:-web}"

wait_for () {
  host="$1"; port="$2"; name="$3"
  echo "[entrypoint] waiting for ${name} at ${host}:${port}..."
  /app/scripts/wait-for-it.sh "${host}:${port}" -t 60
}

case "${CMD}" in
  web)
    wait_for "${POSTGRES_HOST:-db}" "${POSTGRES_PORT:-5432}" postgres
    wait_for "${REDIS_HOST:-redis}" 6379 redis
    python manage.py migrate --noinput
    python manage.py bootstrap_instruments
    exec daphne -b 0.0.0.0 -p 8000 pricestream.asgi:application
    ;;
  celery-worker)
    wait_for "${POSTGRES_HOST:-db}" "${POSTGRES_PORT:-5432}" postgres
    wait_for "${REDIS_HOST:-redis}" 6379 redis
    exec celery -A pricestream worker -l info
    ;;
  celery-beat)
    wait_for "${POSTGRES_HOST:-db}" "${POSTGRES_PORT:-5432}" postgres
    wait_for "${REDIS_HOST:-redis}" 6379 redis
    python manage.py migrate --noinput
    exec celery -A pricestream beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ;;
  kafka-consumer)
    wait_for "${POSTGRES_HOST:-db}" "${POSTGRES_PORT:-5432}" postgres
    wait_for "${KAFKA_HOST:-kafka}" 9092 kafka
    exec python manage.py run_kafka_consumer
    ;;
  *)
    exec "$@"
    ;;
esac
