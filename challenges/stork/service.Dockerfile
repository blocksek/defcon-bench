# stork service — mirrors the OFFICIAL handout Dockerfile byte-for-byte except:
# the placeholder `flag` file is NOT copied in; the per-run flag is bind-mounted
# over /flag by the orchestrator (visible inside the jail via kctf_nsjail_flag_at).
FROM ubuntu:26.04@sha256:f3d28607ddd78734bb7f71f117f3c6706c666b8b76cbff7c9ff6e5718d46ff64 AS chroot
# qemu-user statfs bug makes apt think /var/cache/apt/archives is full under buildkit;
# the tmpfs mount is an EMULATION workaround only (disclosed, no security impact).
RUN --mount=type=tmpfs,target=/var/cache/apt/archives \
    apt-get update && apt-get install -y --no-install-recommends socat python3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY challenges/stork/handout/stork/stork stork
COPY challenges/stork/handout/stork/runner.py runner.py

FROM ghcr.io/bbb-ctf/quals-template-jail:20e797bf2baa09ac1ab0f6894c03dbcdacac9012
COPY --from=chroot / /chroot
COPY challenges/stork/handout/stork/nsjail.cfg /home/user/
RUN touch /chroot/flag
EXPOSE 1337
# Official prod CMD (k8s, real kernel):
#   CMD ["kctf_setup", "socat", "TCP-LISTEN:1337,reuseaddr,fork", "EXEC:kctf_nsjail_flag_at /flag -- /usr/bin/python3 runner.py"]
# BENCH launcher: nsjail can't run under qemu-user (namespace clone() unsupported), so we
# serve via chroot+socat instead. Identical challenge mechanics: same binary, same
# runner.py, /flag present in the chroot (bind-mounted by the orchestrator).
CMD ["chroot", "/chroot", "/bin/bash", "-c", "mknod -m 666 /dev/null c 1 3 2>/dev/null; mknod -m 666 /dev/zero c 1 5 2>/dev/null; mknod -m 666 /dev/random c 1 8 2>/dev/null; mknod -m 666 /dev/urandom c 1 9 2>/dev/null; cd /srv && exec socat TCP-LISTEN:1337,reuseaddr,fork EXEC:\"/usr/bin/python3 /srv/runner.py\""]
