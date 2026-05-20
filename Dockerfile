FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        netcat-openbsd \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt /app/
ARG INSTALL_DEV=0
RUN pip install -r requirements.txt && \
    if [ "$INSTALL_DEV" = "1" ]; then pip install -r requirements-dev.txt; fi

COPY . /app/

RUN chmod +x /app/scripts/entrypoint.sh /app/scripts/wait-for-it.sh

EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["web"]
