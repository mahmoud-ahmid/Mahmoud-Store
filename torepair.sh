#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  Mahmoud-Store — Repair Script (Phase 1 Fix)
#  يحذف Blocks 2/3/4، يضيف Flask-WTF، ينظف apply_phase2.sh
# ============================================================
set -uo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m';  NC='\033[0m'

log()  { echo -e "${CYAN}[*]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }

echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Mahmoud-Store — سكربت الإصلاح الشامل${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo ""

# ---------- 0) Sanity ----------
if [ ! -f app.py ]; then
    err "لا يوجد app.py — شغّل السكربت من داخل مجلد المشروع"
    exit 1
fi
if [ ! -d templates ]; then
    err "لا يوجد templates/ — شغّل السكربت من داخل مجلد المشروع"
    exit 1
fi
if ! command -v python >/dev/null 2>&1; then
    err "python غير مثبت — نفّذ: pkg install python"
    exit 1
fi

# ---------- 1) Backup ----------
TS=$(date +%Y%m%d_%H%M%S)
BACKUP="../mahmoud-store-backup_$TS"
log "نسخة احتياطية → $BACKUP"
mkdir -p "$BACKUP"
cp -r templates "$BACKUP/" 2>/dev/null || true
for f in app.py requirements.txt .gitignore README.md .env apply_phase2.sh; do
    [ -f "$f" ] && cp "$f" "$BACKUP/" 2>/dev/null || true
done
ok "تم النسخ الاحتياطي"

# ---------- 2) Fix app.py ----------
log "إصلاح app.py (حذف Blocks 2، 3، 4)..."
python <<'PYEOF'
import re, sys
from pathlib import Path

p = Path('app.py')
src = p.read_text(encoding='utf-8').replace('\r\n', '\n')
lines = src.splitlines(keepends=True)
orig_count = len(lines)

n_app = src.count('app = Flask(__name__)')
n_run = src.count('app.run(host=host, port=port, debug=False)')
n_csrf = src.count('csrf = CSRFProtect(app)')
print(f"  قبل: {orig_count} سطر | {n_app} app | {n_run} app.run | {n_csrf} csrf")

if n_app == 1 and n_run == 1:
    print("  ✓ app.py نظيف بالفعل — تخطي")
    sys.exit(0)

# Find end of Block 1 = first `app.run(...)` line
pattern = re.compile(r'^\s+app\.run\(host=host,\s*port=port,\s*debug=False\)\s*$')
end_idx = None
for i, line in enumerate(lines):
    if pattern.match(line):
        end_idx = i
        break

if end_idx is None:
    print("  ✗ لم أجد نهاية Block 1 (app.run)", file=sys.stderr)
    sys.exit(1)

clean = ''.join(lines[:end_idx+1]).rstrip() + '\n'

# Verify critical markers survived
checks = {
    'CSRFProtect'              : 'csrf = CSRFProtect(app)' in clean,
    'flask_wtf import'         : 'from flask_wtf.csrf import' in clean,
    'CSRFError handler'        : '@app.errorhandler(CSRFError)' in clean,
    '/favorites route'         : 'def favorites():' in clean,
    '/admin/edit route'        : 'def admin_edit(' in clean,
    '/admin/delete route'      : 'def admin_delete(' in clean,
    '/admin/comment/delete'    : 'def admin_delete_comment(' in clean,
    'init_db() module-level'   : '\ninit_db()\n' in clean,
    'single app = Flask'       : clean.count('app = Flask(__name__)') == 1,
    'single app.run'           : clean.count('app.run(host=host, port=port, debug=False)') == 1,
}
ok_all = True
for name, passed in checks.items():
    print(f"  {'✓' if passed else '✗'} {name}")
    ok_all = ok_all and passed

if not ok_all:
    print("  ✗ بعض الفحوصات فشلت — لن يُكتب app.py", file=sys.stderr)
    sys.exit(1)

if len(clean.splitlines()) < 300:
    print(f"  ✗ الملف الناتج قصير جداً ({len(clean.splitlines())} سطر)", file=sys.stderr)
    sys.exit(1)

# WTF_CSRF_TIME_LIMIT=None → 3600
clean = clean.replace('WTF_CSRF_TIME_LIMIT=None,', 'WTF_CSRF_TIME_LIMIT=3600,')

# Save broken for reference, then write clean
Path('app.py.broken').write_text(src, encoding='utf-8')
p.write_text(clean, encoding='utf-8')
print(f"  بعد: {len(clean.splitlines())} سطر")
print(f"  النسخة المعطوبة محفوظة في app.py.broken")
PYEOF

if [ $? -ne 0 ]; then
    err "فشل إصلاح app.py — استرجاع النسخة الاحتياطية"
    cp "$BACKUP/app.py" app.py
    exit 1
fi
ok "app.py نُظّف"

# ---------- 3) Fix requirements.txt ----------
log "إضافة Flask-WTF إلى requirements.txt..."
if [ -f requirements.txt ]; then
    if ! grep -q '^Flask-WTF' requirements.txt; then
        echo 'Flask-WTF>=1.2.0' >> requirements.txt
    fi
else
    cat > requirements.txt <<'EOF'
Flask>=3.0.0
Flask-Limiter>=3.5.0
Flask-WTF>=1.2.0
python-dotenv>=1.0.0
requests>=2.31.0
Werkzeug>=3.0.0
EOF
fi
ok "requirements.txt محدَّث"

# ---------- 4) Fix apply_phase2.sh ----------
log "تنظيف apply_phase2.sh..."
python <<'PYEOF'
from pathlib import Path
p = Path('apply_phase2.sh')
if not p.exists():
    print("  ! غير موجود — تخطي")
    raise SystemExit(0)

lines = p.read_text(encoding='utf-8').splitlines()
before = len(lines)
lines = [l for l in lines if l.strip() not in ('SCRIPT_START', 'SCRIPT_END')]
if not any(l.strip() == 'exit 0' for l in lines[-3:]):
    lines.append('exit 0')
p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f"  ✓ حُذفت markers ({before} → {len(lines)} سطر)")
PYEOF

if [ -f apply_phase2.sh ]; then
    if bash -n apply_phase2.sh 2>/dev/null; then
        ok "apply_phase2.sh صالح syntax"
    else
        warn "apply_phase2.sh لا يزال فيه مشاكل — راجع يدوياً"
    fi
fi

# ---------- 5) Verify compile ----------
log "فحص Python compile..."
if python -m py_compile app.py 2>/dev/null; then
    ok "app.py يُترجم بنجاح"
else
    err "app.py فيه خطأ Python — استرجاع النسخة الاحتياطية"
    cp "$BACKUP/app.py" app.py
    exit 1
fi

# ---------- 6) Install deps ----------
log "تثبيت المتطلبات..."
if python -m pip install --quiet -r requirements.txt 2>/dev/null; then
    ok "تم تثبيت المتطلبات"
else
    warn "pip فشل — نفّذ يدوياً: python -m pip install -r requirements.txt"
fi

# ---------- 7) Summary ----------
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ الإصلاح اكتمل بنجاح${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo "  Backup:        $BACKUP"
echo "  Broken app:    app.py.broken"
echo "  Clean app:     app.py ($(wc -l < app.py) سطر)"
echo "  requirements:  $(wc -l < requirements.txt) سطر"
echo ""
echo "  ✅ ما تم إصلاحه:"
echo "    • حذف 3 نسخ مكدّسة من app.py"
echo "    • إضافة Flask-WTF (اعتمادية ناقصة كانت تمنع الإقلاع)"
echo "    • إزالة SCRIPT_START/SCRIPT_END من apply_phase2.sh"
echo "    • WTF_CSRF_TIME_LIMIT: None → 3600 ثانية"
echo ""
echo "  📋 الخطوات التالية:"
echo "    1. python app.py                # اختبر يدوياً"
echo "    2. افتح http://127.0.0.1:5000   # تحقق من كل الصفحات"
echo "    3. إذا كل شيء يعمل: rm app.py.broken"
echo "    4. ابدأ المرحلة 2 (الثغرات الحرجة)"
echo ""

read -p "تشغيل الخادم الآن للاختبار؟ (y/N) " -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python app.py
fi
