#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")" || exit 1
TS=$(date +%Y%m%d_%H%M%S)
BK="../mahmoud-store_phase5clean_$TS"
mkdir -p "$BK"
cp app.py templates/index.html templates/favorites.html templates/detail.html "$BK/" 2>/dev/null
echo "backup → $BK"

# Fix NULL description in 3 templates
for f in templates/index.html templates/favorites.html; do
    sed -i "s/{{ app\['description'\]\[:90\] }}/{{ (app['description'] or '')[:90] }}/g" "$f"
    echo "[v] $f NULL-safe"
done
sed -i "s/{{ app\['description'\] }}/{{ app['description'] or '' }}/g" templates/detail.html
echo "[v] templates/detail.html NULL-safe"

# SQL cleanup
python -c "
import sqlite3
conn = sqlite3.connect('store.db')
conn.execute(\"UPDATE apps SET description='' WHERE description IS NULL\")
conn.execute(\"UPDATE apps SET category='أخرى' WHERE category IS NULL\")
conn.execute(\"UPDATE apps SET version='1.0' WHERE version IS NULL\")
conn.commit(); conn.close()
print('[v] SQL cleanup done')
"

# Verify
echo ""
grep -c "description'] or ''" templates/index.html && echo "[v] index: fix present" || echo "[X] index fix missing"
grep -c "description'] or ''" templates/favorites.html && echo "[v] favorites: fix present" || echo "[X] favorites fix missing"

python -m py_compile app.py && echo "[✓] compile OK" || echo "[X] compile FAILED"

