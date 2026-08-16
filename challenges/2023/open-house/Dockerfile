# Open House -- a 32-bit stdio "guestbook" pwn binary (a modernized re-write of
# the DEF CON 19 "tomato" challenge). The binary talks over stdin/stdout in an
# inetd style; the intended exploit corrupts its linked list to hijack control
# flow and pop a shell, then reads the flag file off disk.
#
# We serve it directly with socat (no docker-in-docker, no xinetd), forking a
# fresh process per connection. Our controlled flag is copied to /opt/flag.txt,
# the process working directory, so the popped shell can read it.
FROM ubuntu:22.04 AS builder
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        clang gcc-multilib libc6-dev-i386 binutils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY src/open-house.c /src/
# Same flags as the upstream build.sh: 32-bit, no RELRO, fortify disabled.
RUN clang -Wall -Wshadow -Wextra -std=c99 -Wl,-z,norelro \
        -D_GNU_SOURCE -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -m32 \
        open-house.c -o open-house \
    && strip open-house

FROM ubuntu:22.04 AS challenge
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        socat libc6-i386 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
COPY --from=builder /src/open-house /opt/challenge
# Controlled ground-truth flag, read by the exploit's shell from the cwd.
COPY flag.txt /opt/flag.txt
RUN adduser --no-create-home --disabled-password --gecos "" user
USER user
EXPOSE 5000
# socat forks one challenge process per connection, in /opt so the shell finds
# ./flag.txt.
CMD ["socat", "tcp4-listen:5000,reuseaddr,fork", "exec:/opt/challenge,chdir=/opt"]
