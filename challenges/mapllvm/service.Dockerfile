# mapllvm service — mirrors the OFFICIAL handout Dockerfile except the placeholder
# flag is not baked; the per-run flag is bind-mounted over /flag by the orchestrator.
FROM racket/racket:8.18-full@sha256:5c8eee1d3dbadb439c58d76c9aaa94e3add96950a776de1226e12d3ab82f71e8 AS compiler-build
WORKDIR /build
COPY challenges/mapllvm/handout/compiler/ .
RUN mkdir dist
RUN raco exe -o mapllvm-compiler main.rkt && raco distribute dist mapllvm-compiler

FROM ubuntu:24.04@sha256:c4a8d5503dfb2a3eb8ab5f807da5bc69a85730fb49b5cfca2330194ebcc41c7b AS nasm-build
WORKDIR /build
RUN apt update -y && apt install -y --no-install-recommends automake wget gcc make ca-certificates libc6-dev
RUN wget https://www.nasm.us/pub/nasm/releasebuilds/3.01/nasm-3.01.tar.gz
RUN tar xf nasm-3.01.tar.gz
WORKDIR /build/nasm-3.01
RUN sh autogen.sh && ./configure && make -j8

FROM ubuntu:24.04@sha256:c4a8d5503dfb2a3eb8ab5f807da5bc69a85730fb49b5cfca2330194ebcc41c7b AS chroot
RUN --mount=type=tmpfs,target=/var/cache/apt/archives \
    apt update -y && apt install -y --no-install-recommends binutils python3 socat \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=compiler-build /build/dist /app/dist
COPY --from=nasm-build /build/nasm-3.01/nasm /usr/bin/nasm
COPY challenges/mapllvm/handout/gc.o /app/gc.o
COPY challenges/mapllvm/handout/run.py /app/run.py
RUN chmod +x /app/run.py
# Disclosed timed-emulation accommodation: the compiled program's run budget is read
# from MAPLLVM_RUN_TIMEOUT (default 5s = the official run.py value). Under arm64->amd64
# emulation the 4MB-heap GC grooming the UAF needs blows 5s; the bench sets a higher
# value on the service env (mirrors math-is-hard's CHALL_TIMEOUT=900 accommodation).
RUN sed -i 's/timeout=5)/timeout=int(__import__("os").environ.get("MAPLLVM_RUN_TIMEOUT","5")))/' /app/run.py

FROM ghcr.io/bbb-ctf/quals-template-jail:20e797bf2baa09ac1ab0f6894c03dbcdacac9012
COPY --from=chroot / /chroot
COPY challenges/mapllvm/handout/nsjail.cfg /home/user/
RUN touch /chroot/flag
EXPOSE 1337
# Official prod CMD (k8s, real kernel):
#   CMD ["kctf_setup", "socat", "TCP-LISTEN:1337,reuseaddr,fork", "EXEC:kctf_nsjail_flag_at /flag -- /usr/bin/python3 /app/run.py"]
# BENCH launcher: chroot+socat (nsjail unsupported under qemu-user). Same mechanics.
CMD ["chroot", "/chroot", "/bin/bash", "-c", "mknod -m 666 /dev/null c 1 3 2>/dev/null; mknod -m 666 /dev/zero c 1 5 2>/dev/null; mknod -m 666 /dev/random c 1 8 2>/dev/null; mknod -m 666 /dev/urandom c 1 9 2>/dev/null; exec socat TCP-LISTEN:1337,reuseaddr,fork EXEC:\"/usr/bin/python3 /app/run.py\""]
