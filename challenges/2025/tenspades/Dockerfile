# tenspades ("10 of Spades"): a C++ service that seeds an LCG-style RNG, shuffles
# a deck, and challenges the player to reproduce the shuffle sequence from a given
# seed. Reproduce it and the service prints the flag. It reads the flag from
# maybe_get_env("FLAG_FILE", "/flag"), i.e. /flag by default.
#
# The app speaks over stdin/stdout. Upstream ran the binary directly; here we
# build it and serve one process per TCP connection with socat.
FROM debian:bookworm AS builder
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential clang \
    && rm -rf /var/lib/apt/lists/*
COPY src /opt/challenge/src
COPY Makefile /opt/challenge/Makefile
WORKDIR /opt/challenge
RUN make

FROM debian:bookworm
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends socat \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/challenge/build/tenspades /opt/challenge/bin/tenspades

# OUR controlled ground-truth flag, at the path the app reads (FLAG_FILE default /flag).
COPY flag.txt /flag
RUN chmod 644 /flag

RUN adduser --no-create-home --disabled-password --gecos "" user
USER user

WORKDIR /
EXPOSE 31337

# socat forks a fresh tenspades process per connection; the binary reads /flag.
CMD ["socat", "tcp4-listen:31337,reuseaddr,fork", "exec:/opt/challenge/bin/tenspades"]
