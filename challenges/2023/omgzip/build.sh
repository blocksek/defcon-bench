#!/bin/bash
# Build the omgzip artifact: pack the flag with the custom compressor and zip it
# up next to the compressor source, exactly like the original challenge.
#
# The upstream build ran the flag through `figlet` to make ASCII art before
# compressing. We keep the flag as plain text so the recovered plaintext is the
# literal flag string (graded by exact match). Everything else -- the tar
# wrapper, the omgzip compression, the zip container -- matches upstream.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${OUTPUT_DIR:-$HERE/dist}"
mkdir -p "$OUT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cp "$HERE/src/omgzip" "$WORK/omgzip"
mkdir -p "$WORK/corpus"
# Plain-text flag (no figlet), so decompression yields the exact flag string.
cp "$HERE/flag.txt" "$WORK/corpus/flag"

cd "$WORK"
tar cf data.tar corpus
python3 omgzip data.tar
zip -q omg.zip omgzip data.tar.omgzip

cp omg.zip "$OUT/omg.zip"
echo "wrote $OUT/omg.zip"
