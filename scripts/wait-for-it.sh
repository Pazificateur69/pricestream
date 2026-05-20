#!/usr/bin/env bash
# Simple TCP wait — use `host:port [-t timeout]`.
set -e

TIMEOUT=30
HOSTPORT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -t) TIMEOUT="$2"; shift 2 ;;
    *) HOSTPORT="$1"; shift ;;
  esac
done

HOST="${HOSTPORT%:*}"
PORT="${HOSTPORT#*:}"

start_ts=$(date +%s)
while :; do
  if nc -z "$HOST" "$PORT" >/dev/null 2>&1; then
    exit 0
  fi
  now=$(date +%s)
  elapsed=$(( now - start_ts ))
  if (( elapsed >= TIMEOUT )); then
    echo "wait-for-it: timeout after ${TIMEOUT}s waiting for ${HOSTPORT}" >&2
    exit 1
  fi
  sleep 1
done
