# Agent base image — what the evaluated agent runs inside. Contains generic tooling
# ONLY: no solvers, no flags, no Docker API access, no host mounts, no internet
# (the bench network is --internal). The agent's only inputs: /etc/bench/manifest.json
# (CTFd URL + its own token + challenge endpoints) and /workspace (operator-shared dir).
FROM python:3.11.15-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PUPPETEER_SKIP_DOWNLOAD=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl netcat-openbsd jq socat chromium nodejs npm git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pwntools z3-solver capstone requests wasmtime==44.0.0 angr
RUN npm install -g puppeteer-core@23 >/dev/null 2>&1
ENV CHROME_BIN=/usr/bin/chromium
WORKDIR /workspace
CMD ["sleep", "infinity"]
