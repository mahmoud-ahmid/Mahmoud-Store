#!/data/data/com.termux/files/usr/bin/bash
# Mahmoud-Store — نسخة احتياطية يومية
cd "$(dirname "$0")" || exit 1

TS=$(date +%Y%m%d_%H%M%S)
BK="../store-backups/$TS"
mkdir -p "$BK"

cp store.db   "$BK/" 2>/dev/null
cp .env       "$BK/" 2>/dev/null
cp app.py     "$BK/" 2>/dev/null
cp -r templates "$BK/" 2>/dev/null

# keep last 7 backups only
cd ../store-backups
ls -dt */ 2>/dev/null | tail -n +8 | xargs -r rm -rf

echo "Backup: $BK"
echo "Total:  $(ls -1 | wc -l) backups kept"
