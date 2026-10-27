#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")" || exit 1
TS=$(date +%Y%m%d_%H%M%S)
BK="../mahmoud-store_phase5_$TS"
mkdir -p "$BK"
cp app.py templates/index.html "$BK/"
echo "backup → $BK"

python apply_phase5_logic.py

