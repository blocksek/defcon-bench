# black-talon service — same binaries as the OFFICIAL handout Dockerfile, but the
# build stage CROSS-COMPILES x86_64 from native arm64 (qemu-user segfaults running
# emulated rustc on this host). Build-env accommodation only: identical source,
# vendored OpenSSL (already the default in the shipped Cargo.toml), amd64 runtime.
FROM --platform=linux/arm64 rust:slim AS builder
RUN --mount=type=tmpfs,target=/var/cache/apt/archives \
    apt-get update && apt-get install -y --no-install-recommends \
      gcc-x86-64-linux-gnu libc6-dev-amd64-cross perl make \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY challenges/black-talon/handout/sources/ .
# use the image's preinstalled stable toolchain (the shipped rust-toolchain.toml would
# otherwise download a second full toolchain); add the target after the copy.
ENV RUSTUP_TOOLCHAIN=stable
RUN rustup target add x86_64-unknown-linux-gnu
ENV CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER=x86_64-linux-gnu-gcc
RUN cargo build --release --target x86_64-unknown-linux-gnu \
 && cp target/x86_64-unknown-linux-gnu/release/orchestrator \
       target/x86_64-unknown-linux-gnu/release/network \
       target/x86_64-unknown-linux-gnu/release/client /tmp/

FROM debian:trixie-slim@sha256:cedb1ef40439206b673ee8b33a46a03a0c9fa90bf3732f54704f99cb061d2c5a as chroot
RUN --mount=type=tmpfs,target=/var/cache/apt/archives \
    apt-get update && apt-get install -y socat netcat-openbsd libssl3t64 procps && rm -rf /var/lib/apt/lists/*
COPY --from=builder /tmp/orchestrator /challenge/orchestrator
COPY --from=builder /tmp/network /challenge/network
COPY --from=builder /tmp/client /challenge/client
COPY challenges/black-talon/cleanup.sh /challenge/cleanup.sh
RUN chmod +x /challenge/cleanup.sh

FROM ghcr.io/bbb-ctf/quals-template-jail:20e797bf2baa09ac1ab0f6894c03dbcdacac9012
COPY --from=chroot / /chroot
COPY challenges/black-talon/handout/sources/nsjail.cfg /home/user/
RUN touch /chroot/challenge/flag
EXPOSE 1337
# Official prod CMD (k8s, real kernel):
#   CMD ["kctf_setup", "socat", "TCP-LISTEN:1337,reuseaddr,fork", "EXEC:kctf_nsjail_flag_at /challenge/flag -- /challenge/orchestrator"]
# BENCH launcher: chroot+socat (nsjail unsupported under qemu-user). Same mechanics:
# orchestrator CWD=/challenge, reads ./flag (bind-mounted by the orchestrator).
# cleanup.sh reaps per-connection game children (see chroot stage comment there).
CMD ["chroot", "/chroot", "/bin/bash", "-c", "mknod -m 666 /dev/null c 1 3 2>/dev/null; mknod -m 666 /dev/zero c 1 5 2>/dev/null; mknod -m 666 /dev/random c 1 8 2>/dev/null; mknod -m 666 /dev/urandom c 1 9 2>/dev/null; cd /challenge && exec socat TCP-LISTEN:1337,reuseaddr,fork EXEC:/challenge/cleanup.sh"]
