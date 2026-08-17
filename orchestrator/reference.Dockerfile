# Shared reference-runner image (orchestrator-side only; NEVER shipped to agents).
FROM python:3.11.15-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir z3-solver capstone sympy wasmtime==44.0.0
COPY solvers/ /solvers/
# rfc1149b solver path layout (attack.py->/gf, full_solve.py->/app, both need sim.py)
COPY challenges/rfc1149b/handout/rfc1149b/sim.py /gf/sim.py
COPY challenges/rfc1149b/handout/rfc1149b/sim.py /app/sim.py
RUN cp /solvers/rfc1149b/attack.py /solvers/rfc1149b/gf.py /gf/ \
 && cp /solvers/rfc1149b/attack.py /solvers/rfc1149b/gf.py /solvers/rfc1149b/full_solve.py /app/
WORKDIR /solvers
