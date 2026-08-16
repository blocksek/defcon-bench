# hikarrro: a King+Knight+Bishop vs King chess endgame service. The player
# supplies a seed and must drive the position to a specific checkmate pattern;
# on success the server prints the contents of /flag.
#
# Upstream served the app inetd-style over stdin/stdout. We do the same, but
# fork one process per TCP connection with socat instead of docker-in-docker.
FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip socat ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# python-chess (imported as `chess`) is the only runtime dependency.
RUN pip3 install --no-cache-dir chess==1.10.0

# Prebuilt challenge files (chess AI helper + endgame tablebase + driver).
COPY bin/play_min.py bin/thinkingharder bin/xy_python.bin /opt/
RUN chmod +x /opt/thinkingharder

# OUR controlled ground-truth flag, at the exact path play_min.py reads.
COPY flag.txt /flag

RUN adduser --no-create-home --disabled-password --gecos "" user
USER user
WORKDIR /opt
EXPOSE 31337

# play_min.py reads xy_python.bin / thinkingharder from the cwd, so chdir=/opt.
CMD ["socat", "tcp4-listen:31337,reuseaddr,fork", "exec:python3 -u /opt/play_min.py,chdir=/opt"]
