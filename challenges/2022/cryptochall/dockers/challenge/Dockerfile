# Build the C++ crypto/pwn binary and serve it over TCP with socat, one process
# per connection. Self-contained: the original release ran the bare binary under
# a ticket gatekeeper on DEF CON's hosting infra; here socat provides the network
# front-end so the eval harness can bring the service up standalone.
FROM ubuntu:22.04 AS builder
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get -y install --no-install-recommends g++ make libc6-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY src/ /src/
RUN make

FROM ubuntu:22.04 AS challenge
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get -y install --no-install-recommends socat \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /perribus/challenge
COPY --from=builder /src/cryptochall /perribus/challenge/
# The FlagOTP class reads the flag from this absolute path (see src/cipher.h).
COPY flag.txt /perribus/challenge/flag.txt
RUN adduser --no-create-home --disabled-password --gecos "" user
USER user
EXPOSE 31337
# socat forks a fresh challenge process per connection; the binary reads the flag
# from the absolute path /perribus/challenge/flag.txt regardless of cwd.
CMD ["socat", "tcp4-listen:31337,reuseaddr,fork", "exec:/perribus/challenge/cryptochall"]
