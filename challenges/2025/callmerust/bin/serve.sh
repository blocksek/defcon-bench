#!/bin/sh
# Per-connection entrypoint, run as root by socat.
#
# The setuid loader requires a fresh precondition file /opt/privuserdir/f to
# exist at start and removes it (upstream hosting gave each connection a fresh
# container). To make the service reusable across connections in a single
# long-lived container, we re-create that file (owned by privuser) for every
# connection, then drop to the unprivileged 'user' to run the challenge. The
# loader itself is setuid privuser, reads the flag as privuser, and drops to the
# calling uid before compiling/running the player's Rust code.
rm -f /opt/privuserdir/f
install -o privuser -g privuser -m 644 /dev/null /opt/privuserdir/f
cd /opt
exec runuser -u user -- env HOME=/home/user /opt/run_challenge.sh
