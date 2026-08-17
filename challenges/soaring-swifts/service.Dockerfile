# soaring-swifts service — official handout (chal.py + compiler.zip) with the two
# REDACTED glue files filled by our reconstruction (solvers/soaring-swifts/reconstructed).
# DISCLOSED: the organizers redacted Compiler.hs/FlagChecker.hs in the handout; the
# reconstruction uses only the shipped passes. The reference solver is generic and does
# not depend on the embedding, so the challenge remains a faithful test of the graded skill.
# apt note: this old bullseye-based pinned image fails GPG checks under qemu emulation;
# AllowInsecureRepositories is an EMULATION accommodation only (disclosed).
# Flag via FLAG env, exactly like the official chal.py expects.
FROM haskell:9.10@sha256:37a7585a7b9ce9237f67b3b430cbb9488734958a04c9d903a0e4bedc4b26b114 AS builder
WORKDIR /build
COPY challenges/soaring-swifts/compiler/ /build/
# fill the redacted glue (documented reconstruction)
COPY solvers/soaring-swifts/reconstructed/Compiler.hs /build/app/Compiler.hs
COPY solvers/soaring-swifts/reconstructed/FlagChecker.hs /build/app/Private/FlagChecker.hs
RUN cabal update && cabal build -j
RUN cp $(cabal list-bin branchless-compiler) /build/compiler

FROM haskell:9.10@sha256:37a7585a7b9ce9237f67b3b430cbb9488734958a04c9d903a0e4bedc4b26b114
# qemu-user statfs bug makes apt think /var/cache/apt/archives is full under buildkit;
# the tmpfs mount is an EMULATION workaround only (disclosed, no security impact).
RUN --mount=type=tmpfs,target=/var/cache/apt/archives \
    apt-get update && apt-get install -y --no-install-recommends python3 nasm binutils socat \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /build/compiler ./compiler
COPY challenges/soaring-swifts/handout/chal.py .
EXPOSE 1337
# stdin/stdout service behind socat, as in prod (jail template did the same)
CMD ["socat", "TCP-LISTEN:1337,reuseaddr,fork", "EXEC:python3 chal.py"]
