# dotcom-airbag: a two-stage pwn. `dotcom_market` is a sandboxed client that
# crashes on purpose; `airbag` is its parent "crash reporter" that ptraces the
# child and parses an LLVM GSYM debug section from an attacker-influenced ELF --
# that GSYM parsing is the bug. Stage 1 leaks flag1 (an fd left open to
# /flag1.txt). Stage 2 escalates to invoke the setuid `bailout` helper, which
# reads /treasury/flag2.txt. flag2 is the flag graded here.
#
# Built and run in the same ubuntu:22.04 base so the runtime libc matches what
# the exploit is developed against. Served one process per TCP connection with
# socat (no docker-in-docker).
FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
        clang llvm-14 binutils libseccomp-dev make python3 socat \
        libc6-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# build_elf.py invokes `llvm-gsymutil-14`; make sure that name resolves.
RUN command -v llvm-gsymutil-14 >/dev/null 2>&1 || \
    ln -s /usr/lib/llvm-14/bin/llvm-gsymutil /usr/bin/llvm-gsymutil-14

# Build the three binaries (airbag, dotcom_market, bailout) from source.
WORKDIR /build
COPY src/ /build/
RUN make all

# ---- runtime layout -------------------------------------------------------
# Users: `gov` owns the treasury + setuid bailout; `user` runs the service.
RUN adduser --no-create-home --disabled-password --gecos "" gov && \
    adduser --no-create-home --disabled-password --gecos "" user

# Stage-1 flag: a distinct decoy (NOT the graded flag). Grading is on flag2.
RUN echo 'flag{stage1_decoy_now_go_get_the_bailout_money}' > /flag1.txt && \
    chmod o+r /flag1.txt

# Stage-2 flag: OUR controlled ground-truth, readable only via setuid bailout.
RUN mkdir /treasury
COPY flag.txt /treasury/flag2.txt
RUN chown -R gov /treasury && chmod 500 /treasury && chmod 400 /treasury/flag2.txt

# The setuid helper that prints flag2 when asked for a big enough bailout.
RUN cp /build/bailout /bailout && \
    chown gov /bailout && \
    chmod u+s /bailout && chmod o+x /bailout

# The service binaries.
RUN mkdir -p /opt && cp /build/airbag /build/dotcom_market /opt/ && \
    chmod 755 /opt/airbag /opt/dotcom_market

USER user
WORKDIR /opt
EXPOSE 31337

# airbag reads the client over stdin/stdout (inherited by its forked child).
CMD ["socat", "tcp4-listen:31337,reuseaddr,fork", "exec:/opt/airbag /opt/dotcom_market"]
