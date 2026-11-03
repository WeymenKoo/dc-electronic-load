#!/bin/bash
# usage: ltrun_local.sh [-t seconds] <deck>.asc
# Runs LTspice (CrossOver build) on a LOCAL copy of the simulation tree: Google Drive File Stream makes LTspice's incremental
# .raw writes fail ("Trouble writing ... to the disk"). The deck folder and lib/ are mirrored into a temp tree with the same relative
# layout (so the .include ../lib or ../../lib lines resolve), LTspice runs there, and the .log / .raw files are copied back.
T=900; if [ "$1" = "-t" ]; then T=$2; shift 2; fi
HERE="$(cd "$(dirname "$0")" && pwd)"; SIM="$(cd "$HERE/.." && pwd)"
ASC="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
REL="${ASC#$SIM/}"                                 # e.g. rev_e/03_loop_gain/03_loop_gain.asc
TMP="${TMPDIR:-/tmp}/ltrun_local"; mkdir -p "$TMP/lib" "$TMP/$(dirname "$REL")"
cp "$SIM"/lib/* "$TMP/lib/"; cp "$ASC" "$TMP/$REL"
export CX_ROOT=/Applications/LTspice.app/Contents/SharedSupport/ltspice
"$CX_ROOT/LTspice/wine" --bottle ltspice --wait-children -- "C:\\Program Files\\ADI\\LTspice\\LTspice.exe" -b "Z:$TMP/$REL" > /dev/null 2>&1 & P=$!
for i in $(seq 1 $T); do kill -0 $P 2>/dev/null || break; /bin/sleep 1; done
if kill -0 $P 2>/dev/null; then kill $P; echo "TIMEOUT $REL after $T s"; fi
B="${TMP}/${REL%.asc}"; D="$(dirname "$ASC")"
for f in "$B.log" "$B.raw" "$B.op.raw" "$B.net"; do [ -f "$f" ] && cp "$f" "$D/"; done
echo "done $REL ($(du -h "$B.raw" 2>/dev/null | cut -f1) raw)"
