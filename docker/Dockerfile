# Hermetic test image (Ubuntu) with Xvfb + fake CLI
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-tk \
    xvfb \
    xauth \
    curl \
    ca-certificates \
    shellcheck \
    imagemagick \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
COPY scripts ./scripts
COPY assets ./assets
COPY packaging ./packaging
COPY --chmod=0755 install.sh uninstall.sh Makefile ./

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -e ".[dev]"

ENV PATH="/opt/venv/bin:/app/scripts/docker-bin:${PATH}"

# Fake CLI on PATH for hermetic tests
RUN mkdir -p /app/scripts/docker-bin \
    && printf '#!/bin/sh\nexec python3 /app/scripts/fake_hotspotshield.py "$@"\n' > /app/scripts/docker-bin/hotspotshield \
    && chmod +x /app/scripts/docker-bin/hotspotshield /app/scripts/fake_hotspotshield.py \
    && chmod +x /app/install.sh /app/uninstall.sh

COPY docker/entrypoint-test.sh /entrypoint-test.sh
RUN chmod +x /entrypoint-test.sh

# Ensure secrets are never present in the image
RUN test ! -e /app/.secrets

ENTRYPOINT ["/entrypoint-test.sh"]
