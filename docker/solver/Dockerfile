# The sandbox image the agent gets a shell in (DockerSandbox). It carries the
# tooling a CTF player reaches for. Extend freely; point runs at a custom image
# with `ctfbench run --solver-image ...`.
FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-dev \
        build-essential gcc gdb \
        binutils file xxd bsdmainutils \
        netcat-openbsd socat curl wget \
        unzip zip xz-utils \
        git ca-certificates \
        ltrace strace \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
        pwntools \
        requests \
        pycryptodome \
        websocket-client

WORKDIR /workspace
