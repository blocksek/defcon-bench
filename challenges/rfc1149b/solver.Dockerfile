# Solver image for rfc1149b: official handout harness image + our solver files.
# Build context MUST be the repo root (needs solvers/ + challenges/*/handout/).
# The handout image already ships sim.py at /app; attack.py expects /gf, full_solve.py /app.
FROM bench/rfc1149b-harness
USER root
RUN pip install --no-cache-dir sympy
RUN mkdir -p /gf /solver
COPY challenges/rfc1149b/handout/rfc1149b/sim.py /gf/sim.py
COPY solvers/rfc1149b/ /solver/
RUN cp /solver/attack.py /solver/gf.py /gf/ \
 && cp /solver/attack.py /solver/gf.py /solver/full_solve.py /solver/make_winner.py /app/
WORKDIR /solver
