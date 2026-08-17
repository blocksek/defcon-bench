#!/usr/bin/env bash
# fetch_handouts.sh — populate challenges/<name>/handout/ with the PRISTINE
# DEF CON 2026 quals handouts (BBB organizers). Sources, in order:
#   1. local cache (paths below)   2. official GCS handout bucket
# Handouts are checksummed by the organizers' API; these are the exact tarballs
# served during the competition.
set -euo pipefail
cd "$(dirname "$0")"
GCS="https://storage.googleapis.com/gha-quals-2026-handout-production"

# name|archive|local-cache(optional)
CAT=(
"rfc1149b|$GCS/rfc1149b-b43cb8c-da5683d0b4c012bd.tar.gz|/Users/fork/cyber/rfc1149b/rfc1149b-b43cb8c-da5683d0b4c012bd.tar.gz"
"math-is-hard|$GCS/math-is-hard-8b7bd3c-fb461e0f9287fec7.tar.gz|"
"black-talon|$GCS/the-black-talon-the-black-talon-85ea5da-af9bd779a4636d24.tar|/Users/fork/cyber/the-black-talon-the-black-talon-85ea5da-af9bd779a4636d24.tar"
"soaring-swifts|$GCS/soaring-swifts-65b9995-c0f8d349ca2251e5.tar.gz|"
"stork|$GCS/stork-12edc50-8e27f89c6851b20d.tar.gz|/Users/fork/ctf/stork/handout.tar.gz"
"mapllvm|$GCS/mapllvm-0f45d7e-cd42818eaa9ab46f.tar.gz|"
"2bird2can|$GCS/twobirdtwocan-1cd1b10-75b006c76a393878.tar.gz|/Users/fork/ctf/twobird.tar.gz"
"stickdrift|$GCS/stickdrift-halleffect-joysticks-12398075.tar.gz|/Users/fork/ctf/stickdrift.tar.gz"
)

for row in "${CAT[@]}"; do
  IFS='|' read -r name url cache <<< "$row"
  dest="challenges/$name/handout"
  if [ -d "$dest" ] && [ -n "$(ls -A "$dest" 2>/dev/null)" ]; then
    echo "[=] $name: already present"; continue
  fi
  mkdir -p "$dest" tmp_handout
  echo "[+] $name: fetching"
  if [ -n "$cache" ] && [ -f "$cache" ]; then
    cp "$cache" tmp_handout/a.pkg
  else
    curl -fL --retry 3 -o tmp_handout/a.pkg "$url"
  fi
  tar -xf tmp_handout/a.pkg -C "$dest" --strip-components 0
  rm -rf tmp_handout
  echo "    -> $(find "$dest" -type f | wc -l | tr -d ' ') files"
done
# soaring-swifts: extract compiler.zip into challenges/soaring-swifts/compiler/
# (the service build consumes the extracted tree; redacted glue filled from solvers/)
if [ -f challenges/soaring-swifts/handout/compiler.zip ] && [ ! -d challenges/soaring-swifts/compiler/app ]; then
  unzip -o -q challenges/soaring-swifts/handout/compiler.zip -d challenges/soaring-swifts/
  # the shipped .cabal is redacted too (Private.???); fill it (documented reconstruction)
  sed -i '' 's/Private\.???/Private.FlagChecker/' challenges/soaring-swifts/compiler/branchless-compiler.cabal 2>/dev/null \
   || sed -i 's/Private\.???/Private.FlagChecker/' challenges/soaring-swifts/compiler/branchless-compiler.cabal
  echo "[=] soaring-swifts: compiler.zip extracted + cabal glue filled"
fi
echo "done. Handouts under challenges/*/handout/ (gitignored)."
