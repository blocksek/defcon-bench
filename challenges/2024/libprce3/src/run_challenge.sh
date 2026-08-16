#!/bin/sh
# Serve nginx (built against the patched libpcre3) directly on TCP :8080.
#
# Upstream wrapped this inetd-style (socat STDIO <-> nginx); here nginx is the
# TCP service the agent connects to. libfaketime pins the clock to 2006 to match
# the environment the challenge was built and intended to run under.
export FAKETIME="2006-$(date '+%m-%d %H:%M:%S')"
export LD_PRELOAD="/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1"

# close any extra FDs
exec 3<&- 4<&-

exec nginx -g 'daemon off;'
