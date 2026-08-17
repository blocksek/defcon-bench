# math-is-hard bench image: pristine handout + qemu-riscv64 for chall + wasmtime harness.
# (The handout ships no Dockerfile; run_wasm.py/math_host.py ARE the official local harness.)
FROM python:3.11.15-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends qemu-user ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY challenges/math-is-hard/handout/math-is-hard/requirements.txt .
RUN pip install --no-cache-dir wasmtime==44.0.0
COPY challenges/math-is-hard/handout/math-is-hard/ /app/
COPY solvers/math-is-hard/ /solver/
RUN chmod +x /app/chall
WORKDIR /solver
