# ChatTGE -- a WebSocket chat server written entirely in TorqueScript, running
# as a Windows binary (ChatTGE.exe) under Wine. The build stage compiles the
# .cs scripts to .dso with the engine; the run stage serves the app on TCP
# 28080. The intended exploit chains an eval() injection in the hand-rolled
# JSON parser with a dSprintf stack overflow to get code execution and read the
# flag file.
#
# Served directly (no docker-in-docker): start.sh launches the engine which
# listens on 28080 itself. Our controlled flag is copied to /chal/flag.txt --
# the process working directory and the path the exploit reads.
FROM --platform=i386 debian:bullseye-slim as base

RUN apt-get update \
    && apt-get install -y --no-install-recommends wget ca-certificates
RUN mkdir -pm755 /etc/apt/keyrings \
    && wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/debian/dists/bullseye/winehq-bullseye.sources
RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends winehq-stable xvfb xauth \
    && rm -rf /var/lib/apt/lists/*
RUN apt-get update \
    && apt-get install -y --no-install-recommends netcat python3 \
    && rm -rf /var/lib/apt/lists/*

FROM base as build

COPY chal /chal

WORKDIR /chal
RUN chmod +x /chal/build.sh
RUN /chal/build.sh

# ----------------------------------------------------------
FROM base as run

COPY --from=build /server.tar.gz /server.tar.gz
COPY --from=build /handout.tar.gz /handout.tar.gz

RUN mkdir /chal
WORKDIR /chal
RUN tar xvzf /server.tar.gz

# Controlled ground-truth flag, read by the exploit from the working directory.
# Overwrites the placeholder flag packed into server.tar.gz at build time.
COPY flag.txt /chal/flag.txt

EXPOSE 28080

ENTRYPOINT [ "/bin/bash", "/chal/start.sh" ]
