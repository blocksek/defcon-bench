# Brine Bid -- a Deno WebSocket auction house whose message protocol runs a
# hand-rolled Python-pickle deserializer. Served directly (no docker-in-docker):
# the app listens on ws://0.0.0.0:8080 itself, so we just EXPOSE that port.
#
# The prebuilt production bundle (main.bundle.js) has ROOT="/" baked in, so it
# reads auction data from /properties/auction and its per-connection state from
# /wallet. Our controlled flag is placed at /opt/flag.txt -- the exact path the
# upstream deployment used -- which the intended pickle file-read primitive
# targets.
FROM denoland/deno:debian-1.33.3

WORKDIR /opt

# Controlled ground-truth flag, read by the exploit via the app's file-read
# primitive. Replaces the upstream placeholder flug{...}.
COPY flag.txt /opt/flag.txt

# The server code (prebuilt, minified single-file bundle).
COPY main.bundle.js /opt/main.bundle.js

# Auction catalogue the server reads at ROOT/properties/auction.
COPY properties /properties/auction

# Per-connection wallet state dir; the app mkdir's + writes here at runtime.
# Pre-create it owned by the unprivileged deno user so writes succeed.
RUN mkdir -p /wallet && chown -R deno:deno /wallet

USER deno
EXPOSE 8080
CMD ["deno", "run", "--allow-net", "--allow-read", "--allow-write", "/opt/main.bundle.js"]
