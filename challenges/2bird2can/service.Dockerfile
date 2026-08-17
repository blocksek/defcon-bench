# 2bird2can server — the OFFICIAL handout server image, unmodified.
# FLAG via env (as in prod). Optional BENCH_SHORT_FLIGHT build-arg applies
# solvers/2bird2can/patch_radius.py to shorten the CSPRNG spawn distance
# (disclosed, default off here; orchestrator may build a -short variant).
FROM debian:bookworm-slim@sha256:f9c6a2fd2ddbc23e336b6257a5245e31f996953ef06cd13a59fa0a1df2d5c252
# qemu-user statfs bug makes apt think /var/cache/apt/archives is full under buildkit;
# the tmpfs mount is an EMULATION workaround only (disclosed, no security impact).
RUN --mount=type=tmpfs,target=/var/cache/apt/archives \
    apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates libfontconfig1 libfreetype6 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY challenges/2bird2can/handout/2bird2can/server-docker/linux-server-build/linux-server-build.x86_64 ./
COPY challenges/2bird2can/handout/2bird2can/server-docker/linux-server-build/linux-server-build_Data ./linux-server-build_Data
COPY challenges/2bird2can/handout/2bird2can/server-docker/linux-server-build/UnityPlayer.so ./
COPY challenges/2bird2can/handout/2bird2can/server-docker/linux-server-build/GameAssembly.so ./
RUN chmod +x ./linux-server-build.x86_64
RUN ln -s /app/linux-server-build_Data/Plugins/libSkiaSharp_linux-x64.so /usr/lib/libSkiaSharp.so
EXPOSE 7777 7778
ENTRYPOINT ["./linux-server-build.x86_64", "-batchmode", "-nographics", "-server", "-address", "0.0.0.0", "-port", "7777"]
