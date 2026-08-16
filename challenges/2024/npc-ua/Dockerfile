# npc-ua: an F#/.NET reimplementation of an OPC-UA-like "NPC-UA" protocol
# server. It speaks a custom binary protocol over stdin/stdout and deserializes
# attacker-controlled objects (FsPickler); the intended bug is a .NET
# deserialization / type-confusion RCE. The flag is read off disk by the
# exploit at /flag.txt.
#
# Upstream served it docker-in-docker via socat; here we build the app and serve
# one process per TCP connection directly with socat.
FROM mcr.microsoft.com/dotnet/sdk:6.0 AS builder
WORKDIR /src
# Restore/build the F# project plus its C# BouncyCastle helper project.
COPY src/npcua.nautilus.fsproj ./
COPY src/crypto.nautilus/ ./crypto.nautilus/
COPY src/NPCUA.fs ./
RUN dotnet publish npcua.nautilus.fsproj -c Release -o /out

FROM mcr.microsoft.com/dotnet/runtime:6.0
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends socat openssl \
    && rm -rf /var/lib/apt/lists/*
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=true

WORKDIR /opt
COPY --from=builder /out/ /opt/
# StatusCode.csv and the EC keys are read from the cwd (GetCryptoSystem(".")).
COPY src/StatusCode.csv /opt/

# OUR controlled ground-truth flag, at the path the exploit reads.
COPY flag.txt /flag.txt

RUN adduser --no-create-home --disabled-password --gecos "" user

# Generate the EC keypair the server loads at startup. secp256k1, PEM encoded.
RUN openssl ecparam -name secp256k1 -genkey -noout -out /opt/private.ec.pem && \
    openssl ec -in /opt/private.ec.pem -pubout -out /opt/public.ec.pem && \
    chmod 644 /opt/public.ec.pem /opt/private.ec.pem && \
    chmod 644 /flag.txt && \
    chown -R user /opt

USER user
EXPOSE 31337

# The app talks over stdin/stdout; socat gives each connection its own process,
# with cwd=/opt so it finds StatusCode.csv and the .pem keys.
CMD ["socat", "tcp4-listen:31337,reuseaddr,fork", "exec:dotnet /opt/npcua.nautilus.dll,chdir=/opt"]
