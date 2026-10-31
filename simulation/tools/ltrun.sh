#!/bin/bash
# usage: ltrun.sh [-netlist] file   (runs LTspice batch via CrossOver wine, waits up to 300 s)
export CX_ROOT=/Applications/LTspice.app/Contents/SharedSupport/ltspice
W=$CX_ROOT/LTspice/wine
MODE=-b; if [ "$1" = "-netlist" ]; then MODE=-netlist; shift; fi
F="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
"$W" --bottle ltspice --wait-children -- "C:\\Program Files\\ADI\\LTspice\\LTspice.exe" $MODE "Z:$F" > /dev/null 2>&1 & P=$!
for i in $(seq 1 300); do kill -0 $P 2>/dev/null || exit 0; /bin/sleep 1; done
kill $P; echo "TIMEOUT"
