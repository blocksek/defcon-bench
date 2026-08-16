# memorybank: a Deno/V8 "ATM" that speaks a menu over stdin/stdout. The intended
# bug is a V8 garbage-collection issue: forcing a GC cycle nulls out the WeakRef
# to the bank_manager, letting the player withdraw the flag. The app reads the
# flag with Deno.readTextFileSync("/flag").
#
# Upstream used a PRIVATE base image (shellweplayagame.azurecr.io/deno:latest),
# which is not pullable. We swap it for the public denoland/deno:latest and serve
# one process per TCP connection with socat. The V8 GC flags (--trace-gc) are
# kept because they matter for the exploit.
FROM denoland/deno:latest

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends socat \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY index.js /app/index.js

# OUR controlled ground-truth flag, at the path the app reads (Deno.readTextFileSync("/flag")).
COPY flag.txt /flag
RUN chmod 644 /flag

EXPOSE 31337

# The denoland/deno image sets ENTRYPOINT ["deno"]; clear it so our socat CMD is
# not appended as deno arguments.
ENTRYPOINT []

# socat forks a fresh deno process per connection. Keep the V8 GC flags and
# --allow-read so the app can read /flag.
CMD ["socat", "tcp4-listen:31337,reuseaddr,fork", "exec:deno run --v8-flags=--trace-gc --allow-read /app/index.js,chdir=/app"]
