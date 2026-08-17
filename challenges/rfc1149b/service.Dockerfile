# rfc1149b verifier = OFFICIAL handout image (runner.py gunicorn) + flag-release shim.
FROM python:3.11.15-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 USE_NSJAIL=0
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY challenges/rfc1149b/handout/rfc1149b/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY challenges/rfc1149b/handout/rfc1149b/sim.py challenges/rfc1149b/handout/rfc1149b/sim_runner.py challenges/rfc1149b/handout/rfc1149b/runner.py ./
COPY challenges/rfc1149b/verifier.py /app/verifier.py
EXPOSE 8080
CMD ["python3", "/app/verifier.py"]
