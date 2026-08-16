# callmerust: a Rust "code runner" fronted by a setuid C loader. The player sends
# Rust source (terminated by 5 newlines); the loader (setuid privuser) reads the
# flag from /home/privuser/flag, drops privileges, compiles the code as an
# unprivileged user, and supervises it under ptrace, injecting the flag into the
# child's memory only for a correctly-crafted program. The flag must be readable
# ONLY by privuser (not world-readable), which the setuid mechanism relies on.
#
# This merges upstream's dockers/challenge and dockers/test Dockerfiles into one
# self-contained image and serves one process per TCP connection with socat
# (upstream test used socat on 5555; we use 31337). No docker-in-docker.
FROM ubuntu:22.04 AS builder
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY src /src
RUN mkdir /build
WORKDIR /src
RUN rm -f loader
# build.sh compiles loader.c -> loader and copies it into /build.
RUN if [ -f ./build.sh ]; then ./build.sh; fi

FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive
# cargo: the loader recompiles the player's Rust at runtime. socat: TCP frontend.
RUN apt-get update && apt-get install -y --no-install-recommends cargo socat ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The setuid loader binary, owned by privuser.
COPY --from=builder /build/loader /opt/loader

RUN adduser --disabled-password --gecos "" user \
    && adduser --disabled-password --gecos "" privuser \
    && mkdir -p /home/privuser && chown privuser:privuser /home/privuser && chmod go-rwx /home/privuser

# OUR controlled ground-truth flag. Readable ONLY by privuser (mode 400), at the
# exact path the loader reads: read_flag("/home/privuser/flag", ...).
COPY flag.txt /home/privuser/flag
RUN chown privuser:privuser /home/privuser/flag && chmod 400 /home/privuser/flag

# Challenge runtime files.
COPY bin/run_challenge.sh /opt/run_challenge.sh
COPY bin/serve.sh /opt/serve.sh
COPY bin/workdir /opt/workdir
RUN chown -R user:user /opt/workdir \
    && chmod 755 /opt/run_challenge.sh /opt/serve.sh

# Precondition dir/file the loader checks and removes at startup (re-created per
# connection by serve.sh). Dir is world-writable so serve.sh's install works and
# the loader (as privuser) can remove the file.
RUN mkdir -p /opt/privuserdir && touch /opt/privuserdir/f \
    && chown -R privuser:privuser /opt/privuserdir && chmod 1777 /opt/privuserdir

# Make the loader setuid privuser so it can read the privuser-only flag.
RUN chown privuser:privuser /opt/loader && chmod u+s /opt/loader

# Pre-populate cargo's crate cache and target dir as 'user' so the runtime
# rebuild (of just the player's main.rs) needs no network. HOME must match the
# runtime HOME (/home/user) so the same cache is reused.
USER user
WORKDIR /opt/workdir
RUN HOME=/home/user cargo build --release

USER root
WORKDIR /opt
EXPOSE 31337

# socat forks a fresh serve.sh per connection (as root); serve.sh re-arms the
# precondition file and drops to 'user' to run the loader.
CMD ["socat", "tcp4-listen:31337,reuseaddr,fork", "exec:/opt/serve.sh,chdir=/opt"]
