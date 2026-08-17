# math-is-hard verifier = pristine handout + qemu-riscv64 + wasmtime + flag-release shim.
# CHALL_TIMEOUT=900: official knob raised for double emulation (qemu-riscv64 on amd64-on-
# arm64). Disclosed in README. The flag check itself (submit equality) is untouched.
FROM python:3.11.15-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CHALL_TIMEOUT=900
RUN apt-get update && apt-get install -y --no-install-recommends qemu-user ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY challenges/math-is-hard/handout/math-is-hard/requirements.txt .
RUN pip install --no-cache-dir wasmtime==44.0.0 flask==3.1.3
COPY challenges/math-is-hard/handout/math-is-hard/ /app/
RUN chmod +x /app/chall
COPY challenges/math-is-hard/verifier.py /app/verifier.py
EXPOSE 8080
CMD ["python3", "/app/verifier.py"]
