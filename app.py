#Fixed: admin bypass, SSRF, zip-bomb, rate limit, headers, cookies, debug.

import io
import hmac
import ipaddress
import socket
import sqlite3
import zipfile
import logging
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse

"""Mahmoud-Store — Phase 1 hardened app."""
import os, io, hmac, ipaddress, socket, sqlite3, zipfile
from functools import wraps
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, send_file)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

"""Mahmoud-Store — Phase 2: CSRF + Admin CRUD + Favorites + Search + Error pages."""
import os, io, hmac, ipaddress, socket, sqlite3, zipfile
from functools import wraps
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, send_file)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, CSRFError

load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise SystemExit('ERROR: SECRET_KEY missing from .env')

_log_handlers = [logging.StreamHandler()]
try:
    _log_handlers.insert(0, logging.FileHandler('app.log', encoding='utf-8'))
except OSError:
    pass
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=_log_handlers,
)
log = logging.getLogger('mahmoud-store')

DB_PATH        = os.environ.get('DB_PATH', 'store.db')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'mahmoud-ahmid')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
MAX_DL         = int(os.environ.get('MAX_DOWNLOAD_MB', '200')) * 1024 * 1024
PROD           = os.environ.get('FLASK_ENV') == 'production'

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Strict',
    SESSION_COOKIE_SECURE=PROD and os.environ.get('HTTPS') == '1',
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    WTF_CSRF_TIME_LIMIT=3600,
)

csrf = CSRFProtect(app)
limiter = Limiter(app=app, key_func=get_remote_address,
                  default_limits=["300 per hour"], storage_uri="memory://")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE, name TEXT, picture TEXT,
            role TEXT DEFAULT 'user');
        CREATE TABLE IF NOT EXISTS apps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, version TEXT, category TEXT,
            description TEXT, icon_url TEXT, download_url TEXT,
            downloads_count INTEGER DEFAULT 0, rating REAL DEFAULT 5.0);
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER, app_id INTEGER,
            PRIMARY KEY (user_id, app_id));
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id INTEGER, user_name TEXT, comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_apps_cat ON apps(category);
        CREATE INDEX IF NOT EXISTS idx_comm_app ON comments(app_id);
        CREATE INDEX IF NOT EXISTS idx_fav_user ON favorites(user_id);
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL, username TEXT NOT NULL,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_login_attempts
            ON login_attempts(ip, username, attempted_at);
        CREATE TABLE IF NOT EXISTS app_ratings (
            user_id INTEGER NOT NULL,
            app_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, app_id));
        CREATE INDEX IF NOT EXISTS idx_ratings_app ON app_ratings(app_id);
    ''')
    conn.commit(); conn.close()

init_db()


def _migrate_password_hash():
    try:
        conn = sqlite3.connect(DB_PATH)
        cols = [r[1] for r in conn.execute('PRAGMA table_info(users)')]
        if 'password_hash' not in cols:
            conn.execute('ALTER TABLE users ADD COLUMN password_hash TEXT')
            conn.commit()
        conn.close()
    except sqlite3.Error:
        pass

_migrate_password_hash()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.before_request
def force_https():
    if PROD and os.environ.get('HTTPS') == '1':
        if not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
            return redirect(request.url.replace('http://', 'https://', 1), code=301)


@app.after_request
def security_headers(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options']        = 'DENY'
    resp.headers['Referrer-Policy']        = 'strict-origin-when-cross-origin'
    resp.headers['Permissions-Policy']     = 'geolocation=(), camera=(), microphone=()'
    resp.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "img-src 'self' https: data:; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'self'; form-action 'self'; object-src 'none'")
    if PROD and os.environ.get('HTTPS') == '1':
        resp.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return resp


@app.route('/service-worker.js')
def service_worker():
    """PWA: يجب أن يُقدَّم من الجذر / وليس /static/"""
    from flask import send_from_directory, current_app
    return send_from_directory(
        current_app.static_folder, 'service-worker.js',
        mimetype='application/javascript')


@app.route('/healthz')
def healthz():
    """
    Health check للتشغيل والمراقبة + يكشف مشاكل الجداول.
    يعيد 200 إذا كل شيء سليم، و503 إذا كان هناك خلل.
    """
    result = {
        'status': 'ok',
        'db': False,
        'tables': {},
    }
    code = 200

    try:
        conn = get_db()
        conn.execute('SELECT 1').fetchone()
        result['db'] = True

        required = ('users', 'apps', 'favorites', 'comments',
                    'login_attempts', 'app_ratings')
        for t in required:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (t,)
            ).fetchone()
            exists = bool(row)
            result['tables'][t] = exists
            if not exists:
                result['status'] = 'degraded'
                code = 503

        conn.close()
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        code = 503

    return jsonify(result), code

@app.errorhandler(404)
def _nf(_): return render_template('404.html'), 404

@app.errorhandler(500)
def _err(e):
    log.error('500 error: %s', e)
    return render_template('500.html'), 500

@app.errorhandler(413)
def _too_large(_): return "الطلب كبير جداً", 413

@app.errorhandler(CSRFError)
def _csrf_err(e):
    log.warning('CSRF error: ip=%s path=%s reason=%s',
                request.remote_addr, request.path, e.description)
    return "انتهت صلاحية النموذج — أعد تحميل الصفحة وحاول مجدداً", 400


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        u = session.get('user')
        if not u or not u.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*a, **k)
    return w


def safe_url(url):
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ('http', 'https') or not p.hostname:
        return False
    h = p.hostname.lower()
    if h in ('localhost', '::1') or h.endswith('.local') or h.endswith('.internal'):
        return False
    try:
        for info in socket.getaddrinfo(h, None):
            ip = ipaddress.ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast):
                return False
    except Exception:
        return False
    return True


# ---------- DNS-rebinding-safe fetch (pinned_get) ----------
import http.client as _http_client
import ssl as _ssl


class _PinnedResponse:
    __slots__ = ('_conn', '_resp', 'status_code', 'headers')
    def __init__(self, conn, resp):
        self._conn = conn
        self._resp = resp
        self.status_code = resp.status
        self.headers = {k.lower(): v for k, v in resp.getheaders()}
    def getheader(self, name, default=''):
        v = self._resp.getheader(name, default)
        return v if v is not None else default
    def read(self, amt=None):
        return self._resp.read(amt)
    def close(self):
        try: self._resp.close()
        except Exception: pass
        try: self._conn.close()
        except Exception: pass


def pinned_get(url, timeout=10):
    '''DNS-rebinding-safe GET: resolve once, validate ALL IPs, pin first IP.

    This defeats DNS rebinding (TOCTOU): attacker changes DNS answer between
    our validation and the fetch. Here, the same resolved IP is used for
    connect. No redirects are followed. Caller MUST call .close().
    '''
    p = urlparse(url)
    if p.scheme not in ('http', 'https') or not p.hostname:
        raise ValueError('invalid scheme or host')
    host = p.hostname.lower()
    port = p.port or (443 if p.scheme == 'https' else 80)
    path = (p.path or '/')
    if p.query:
        path += '?' + p.query

    # 1) Resolve ONCE, validate EVERY address
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    ips = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise ValueError(f'blocked IP: {ip}')
        ips.append(info[4][0])
    if not ips:
        raise ValueError('no valid IP')
    pinned_ip = ips[0]

    headers = {'Host': host, 'User-Agent': 'Mahmoud-Store/1.0'}

    # 2) Connect to the validated IP; keep hostname for Host header + TLS SNI
    if p.scheme == 'https':
        ctx = _ssl.create_default_context()
        raw = socket.create_connection((pinned_ip, port), timeout=timeout)
        try:
            tls = ctx.wrap_socket(raw, server_hostname=host)
        except Exception:
            raw.close()
            raise
        conn = _http_client.HTTPSConnection(host, port, timeout=timeout)
        conn.sock = tls
    else:
        conn = _http_client.HTTPConnection(pinned_ip, port, timeout=timeout)

    try:
        conn.request('GET', path, headers=headers)
        resp = conn.getresponse()
    except Exception:
        conn.close()
        raise

    return _PinnedResponse(conn, resp)


@app.route('/')
def index():
    cat = request.args.get('cat', 'all')
    q   = (request.args.get('q') or '').strip()[:80]
    sort = request.args.get('sort', 'newest')
    if sort not in ('newest', 'downloads', 'rating', 'title'):
        sort = 'newest'
    try:
        page = max(1, int(request.args.get('page', '1')))
    except (ValueError, TypeError):
        page = 1
    per_page = 12
    offset = (page - 1) * per_page
    where, params = [], []
    if cat != 'all':
        where.append('category = ?'); params.append(cat)
    if q:
        where.append('(title LIKE ? OR description LIKE ?)')
        params.extend([f'%{q}%', f'%{q}%'])
    where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
    conn = get_db()
    order_map = {'newest': 'id DESC', 'downloads': 'downloads_count DESC, id DESC',
                 'rating': 'rating DESC, id DESC', 'title': 'title ASC'}
    order_sql = order_map.get(sort, 'id DESC')
    total = conn.execute(f'SELECT COUNT(*) FROM apps{where_sql}', params).fetchone()[0]
    apps = conn.execute(
        f'SELECT * FROM apps{where_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?',
        params + [per_page, offset]
    ).fetchall()
    rating_counts = {}
    try:
        for r in conn.execute('SELECT app_id, COUNT(*) AS c FROM app_ratings GROUP BY app_id'):
            rating_counts[r['app_id']] = r['c']
    except sqlite3.Error:
        pass
    user = session.get('user')
    favs = []
    if user and user.get('id') != 'admin':
        try:
            favs = [r['app_id'] for r in conn.execute(
                'SELECT app_id FROM favorites WHERE user_id=?', (user['id'],)).fetchall()]
        except Exception:
            pass
    categories = [r[0] for r in conn.execute(
        "SELECT DISTINCT category FROM apps WHERE category IS NOT NULL AND category != '' ORDER BY category"
    ).fetchall()]
    conn.close()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template('index.html', apps=apps, current_cat=cat, q=q,
                           user=user, user_favs=favs,
                           admin_username=ADMIN_USERNAME,
                           rating_counts=rating_counts,
                           categories=categories, current_sort=sort,
                           page=page, total_pages=total_pages,
                           total=total)


@app.route('/favorites')
def favorites():
    user = session.get('user')
    if not user or user.get('id') == 'admin':
        return redirect(url_for('index'))
    conn = get_db()
    apps = conn.execute(
        'SELECT a.* FROM apps a INNER JOIN favorites f ON f.app_id = a.id '
        'WHERE f.user_id = ? ORDER BY a.id DESC', (user['id'],)
    ).fetchall()
    conn.close()
    return render_template('favorites.html', apps=apps, user=user,
                           user_favs=[a['id'] for a in apps])


LOCKOUT_MAX = 5
LOCKOUT_WINDOW_MIN = 15
LOCKOUT_DURATION_MIN = 15

def _is_locked_out(ip, username):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM login_attempts WHERE ip=? AND username=? "
            "AND attempted_at > datetime('now', ?)",
            (ip, username.lower(), f'-{LOCKOUT_DURATION_MIN} minutes')).fetchone()
        conn.close()
        return (row['c'] or 0) >= LOCKOUT_MAX
    except sqlite3.Error:
        log.exception('lockout check failed'); return False

def _record_failed_login(ip, username):
    try:
        conn = get_db()
        conn.execute('INSERT INTO login_attempts(ip, username) VALUES(?, ?)',
                     (ip, username.lower()))
        conn.execute("DELETE FROM login_attempts WHERE attempted_at < datetime('now', ?)",
                     (f'-{LOCKOUT_WINDOW_MIN * 4} minutes',))
        conn.commit(); conn.close()
    except sqlite3.Error:
        log.exception('failed to record login attempt')

def _clear_login_attempts(ip, username):
    try:
        conn = get_db()
        conn.execute('DELETE FROM login_attempts WHERE ip=? AND username=?',
                     (ip, username.lower()))
        conn.commit(); conn.close()
    except sqlite3.Error:
        log.exception('failed to clear login attempts')

@app.route('/login/admin', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def admin_login():
    if request.method == 'POST':
        u  = request.form.get('username', '').strip()
        pw = request.form.get('password', '')
        ip = request.remote_addr or '0.0.0.0'
        if _is_locked_out(ip, u):
            log.warning('admin login LOCKED OUT: ip=%s user=%s', ip, u)
            return render_template('admin_login.html',
                                   error='محاولات كثيرة خاطئة — انتظر 15 دقيقة'), 429
        if not ADMIN_PASSWORD:
            return render_template('admin_login.html',
                                   error='ADMIN_PASSWORD غير مضبوط في .env'), 500
        ok_user = hmac.compare_digest(u.lower(), ADMIN_USERNAME.lower())
        ok_pass = hmac.compare_digest(pw, ADMIN_PASSWORD)
        if ok_user and ok_pass:
            _clear_login_attempts(ip, u)
            session.clear()
            session['user'] = {'id': 'admin', 'name': u, 'email': 'admin@local',
                               'picture': f'https://github.com/{u}.png',
                               'is_admin': True}
            session.modified = True
            log.info('admin login success: ip=%s user=%s', ip, u)
            return redirect(url_for('index'))
        _record_failed_login(ip, u)
        log.warning('admin login failed: ip=%s user=%s', ip, u)
        return render_template('admin_login.html', error='بيانات الدخول غير صحيحة')
    return render_template('admin_login.html')


@app.route('/login', methods=['GET', 'POST'])
@app.route('/login/google', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def user_login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        if '@' not in email or len(email) > 120 or not password:
            return render_template('login.html', error='بيانات غير صالحة'), 400
        conn = get_db()
        row = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        if not row or not row['password_hash'] or not check_password_hash(row['password_hash'], password):
            conn.close()
            return render_template('login.html', error='البريد الإلكتروني أو كلمة المرور غير صحيحة'), 401
        uid = row['id']; pic = row['picture']; name = row['name']
        conn.close()
        session.clear()
        session['user'] = {'id': uid, 'name': name, 'email': email,
                           'picture': pic, 'is_admin': False}
        session.modified = True
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def user_register():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        name  = (request.form.get('name')  or '').strip()[:60]
        password = (request.form.get('password') or '').strip()
        if '@' not in email or len(email) > 120 or len(name) < 2 or len(password) < 6:
            return render_template('register.html', error='بيانات غير صالحة (كلمة المرور 6 أحرف على الأقل)'), 400
        conn = get_db()
        row = conn.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()
        if row:
            conn.close()
            return render_template('register.html', error='البريد مستخدم بالفعل'), 400
        pic = 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png'
        phash = generate_password_hash(password)
        cur = conn.execute('INSERT INTO users(email,name,picture,password_hash) VALUES(?,?,?,?)',
                           (email, name, pic, phash))
        conn.commit()
        uid = cur.lastrowid
        conn.close()
        session.clear()
        session['user'] = {'id': uid, 'name': name, 'email': email,
                           'picture': pic, 'is_admin': False}
        session.modified = True
        return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/app/<int:app_id>')
def app_details(app_id):
    conn = get_db()
    a = conn.execute('SELECT * FROM apps WHERE id=?', (app_id,)).fetchone()
    if not a:
        conn.close()
        return render_template('404.html', msg='التطبيق غير موجود'), 404
    comments = conn.execute('SELECT * FROM comments WHERE app_id=? ORDER BY id DESC',
                            (app_id,)).fetchall()
    stats = conn.execute(
        'SELECT COUNT(*) AS cnt, AVG(rating) AS avg FROM app_ratings WHERE app_id=?',
        (app_id,)).fetchone()
    user_rating = None
    u = session.get('user')
    if u and u.get('id') != 'admin':
        r = conn.execute('SELECT rating FROM app_ratings WHERE app_id=? AND user_id=?',
                         (app_id, u['id'])).fetchone()
        if r: user_rating = r['rating']
    conn.close()
    return render_template('detail.html', app=a, comments=comments,
                           user=u, user_rating=user_rating,
                           ratings_count=stats['cnt'] or 0)


def _bump_download(app_id):
    try:
        conn = get_db()
        conn.execute('UPDATE apps SET downloads_count=downloads_count+1 WHERE id=?', (app_id,))
        conn.commit(); conn.close()
    except sqlite3.Error:
        log.exception('failed to bump download counter app_id=%s', app_id)


@app.route('/download/<int:app_id>')
@limiter.limit("20 per hour")
def download_app(app_id):
    conn = get_db()
    a = conn.execute('SELECT * FROM apps WHERE id=?', (app_id,)).fetchone()
    conn.close()
    if not a:
        return "التطبيق غير موجود", 404

    raw = a['download_url'] or ''
    if not safe_url(raw):
        log.warning('SSRF blocked: app_id=%s url=%s ip=%s',
                    app_id, raw, request.remote_addr)
        return "رابط التنزيل غير مسموح", 400

    if raw.lower().endswith(('.apk', '.exe')):
        _bump_download(app_id)
        return redirect(raw)

    r = None
    try:
        r = pinned_get(raw, timeout=10)
        if r.status_code != 200 or 'zip' not in r.getheader('content-type', '').lower():
            _bump_download(app_id)
            return redirect(raw)
        buf = io.BytesIO()
        size = 0
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_DL:
                log.warning('download exceeded MAX_DL: app_id=%s size=%s', app_id, size)
                return "الملف كبير جداً", 413
            buf.write(chunk)
        buf.seek(0)
        z = zipfile.ZipFile(buf)
        for fi in z.infolist():
            fname = fi.filename.lower()
            if not fname.endswith(('.apk', '.exe', '.py')):
                continue
            # zip-bomb defense 1: declared size cap
            if fi.file_size > MAX_DL or fi.file_size > 500 * 1024 * 1024:
                log.warning('zip entry too large (declared): %s (%s bytes)',
                            fi.filename, fi.file_size)
                continue
            # zip-bomb defense 2: compression ratio cap (100:1)
            if fi.compress_size and fi.file_size > 0:
                ratio = fi.file_size / fi.compress_size
                if ratio > 100:
                    log.warning('zip-bomb suspected: %s ratio=%.0f:1',
                                fi.filename, ratio)
                    continue
            # zip-bomb defense 3: hard read limit
            with z.open(fi.filename) as zf:
                data = zf.read(MAX_DL + 1)
            if len(data) > MAX_DL:
                log.warning('zip entry exceeded limit during read: %s', fi.filename)
                continue
            _bump_download(app_id)
            return send_file(io.BytesIO(data), as_attachment=True,
                             download_name=os.path.basename(fi.filename))
        _bump_download(app_id)
        return redirect(raw)
    except (ValueError, OSError) as e:
        log.warning('download blocked/failed: app_id=%s err=%s', app_id, e)
        return "رابط التنزيل غير مسموح", 400
    except zipfile.BadZipFile:
        log.warning('bad zip: app_id=%s', app_id)
        _bump_download(app_id)
        return redirect(raw)
    except Exception:
        log.exception('download failed: app_id=%s', app_id)
        _bump_download(app_id)
        return redirect(raw)
    finally:
        if r is not None:
            r.close()


@app.route('/toggle-favorite/<int:app_id>', methods=['POST'])
@limiter.limit("30 per minute")
def toggle_fav(app_id):
    u = session.get('user')
    if not u or u.get('id') == 'admin':
        return jsonify({'status': 'error', 'message': 'التسجيل مطلوب'}), 401
    conn = get_db()
    ex = conn.execute('SELECT 1 FROM favorites WHERE user_id=? AND app_id=?',
                      (u['id'], app_id)).fetchone()
    if ex:
        conn.execute('DELETE FROM favorites WHERE user_id=? AND app_id=?', (u['id'], app_id))
        s = 'removed'
    else:
        conn.execute('INSERT INTO favorites(user_id,app_id) VALUES(?,?)', (u['id'], app_id))
        s = 'added'
    conn.commit(); conn.close()
    return jsonify({'status': s})


@app.route('/rate/<int:app_id>', methods=['POST'])
@limiter.limit("20 per minute")
def rate_app(app_id):
    u = session.get('user')
    if not u or u.get('id') == 'admin':
        return jsonify({'status': 'error', 'message': 'التسجيل مطلوب'}), 401
    try:
        rating = int(request.form.get('rating', '0'))
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'قيمة غير صالحة'}), 400
    if rating < 1 or rating > 5:
        return jsonify({'status': 'error', 'message': 'التقييم بين 1 و 5'}), 400
    conn = get_db()
    if not conn.execute('SELECT 1 FROM apps WHERE id=?', (app_id,)).fetchone():
        conn.close(); return jsonify({'status': 'error', 'message': 'التطبيق غير موجود'}), 404
    conn.execute('INSERT OR REPLACE INTO app_ratings(user_id, app_id, rating) VALUES(?,?,?)',
                 (u['id'], app_id, rating))
    row = conn.execute('SELECT AVG(rating) AS avg, COUNT(*) AS cnt FROM app_ratings WHERE app_id=?',
                       (app_id,)).fetchone()
    new_avg = round(row['avg'] or 0, 1)
    conn.execute('UPDATE apps SET rating=? WHERE id=?', (new_avg, app_id))
    conn.commit(); conn.close()
    log.info('rating: app_id=%s user=%s value=%s new_avg=%s',
             app_id, u['id'], rating, new_avg)
    return jsonify({'status': 'ok', 'rating': new_avg,
                    'count': row['cnt'], 'user_rating': rating})


@app.route('/comment/<int:app_id>', methods=['POST'])
@limiter.limit("10 per minute")
def add_comment(app_id):
    u = session.get('user')
    name = u['name'] if u else (request.form.get('user_name', 'زائر')[:40] or 'زائر')
    txt = (request.form.get('comment') or '').strip()
    if not txt or len(txt) > 2000:
        return redirect(url_for('app_details', app_id=app_id))
    conn = get_db()
    conn.execute('INSERT INTO comments(app_id,user_name,comment) VALUES(?,?,?)',
                 (app_id, name, txt))
    conn.commit(); conn.close()
    return redirect(url_for('app_details', app_id=app_id))


@app.route('/admin/stats')
@admin_required
def admin_stats():
    conn = get_db()
    stats = {
        'apps':       conn.execute('SELECT COUNT(*) FROM apps').fetchone()[0],
        'users':      conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'comments':   conn.execute('SELECT COUNT(*) FROM comments').fetchone()[0],
        'favorites':  conn.execute('SELECT COUNT(*) FROM favorites').fetchone()[0],
        'downloads':  conn.execute('SELECT COALESCE(SUM(downloads_count),0) FROM apps').fetchone()[0],
    }
    top_apps = conn.execute(
        'SELECT id, title, downloads_count FROM apps ORDER BY downloads_count DESC LIMIT 5'
    ).fetchall()
    recent_comments = conn.execute(
        'SELECT app_id, user_name, comment, created_at FROM comments ORDER BY id DESC LIMIT 5'
    ).fetchall()
    conn.close()
    return render_template('stats.html', stats=stats,
                           top_apps=top_apps, recent_comments=recent_comments)


@app.route('/admin/add', methods=['GET', 'POST'])
@admin_required
def admin_add():
    if request.method == 'POST':
        t  = request.form.get('title', '').strip()[:100]
        v  = request.form.get('version', '').strip()[:20]
        c  = request.form.get('category', 'أخرى')[:30]
        d  = request.form.get('description', '')[:5000]
        i  = request.form.get('icon_url', '').strip()[:500]
        du = request.form.get('download_url', '').strip()[:500]
        if not t or not safe_url(du):
            return render_template('admin.html', error='بيانات غير صالحة'), 400
        conn = get_db()
        conn.execute('INSERT INTO apps(title,version,category,description,icon_url,download_url) '
                     'VALUES(?,?,?,?,?,?)', (t, v, c, d, i, du))
        conn.commit(); conn.close()
        return redirect(url_for('index'))
    return render_template('admin.html')


@app.route('/admin/edit/<int:app_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit(app_id):
    conn = get_db()
    a = conn.execute('SELECT * FROM apps WHERE id=?', (app_id,)).fetchone()
    if not a:
        conn.close()
        return render_template('404.html', msg='التطبيق غير موجود'), 404
    if request.method == 'POST':
        t  = request.form.get('title', '').strip()[:100]
        v  = request.form.get('version', '').strip()[:20]
        c  = request.form.get('category', 'أخرى')[:30]
        d  = request.form.get('description', '')[:5000]
        i  = request.form.get('icon_url', '').strip()[:500]
        du = request.form.get('download_url', '').strip()[:500]
        if not t or not safe_url(du):
            conn.close()
            return render_template('admin_edit.html', app=a,
                                   error='بيانات غير صالحة'), 400
        conn.execute('UPDATE apps SET title=?,version=?,category=?,description=?,'
                     'icon_url=?,download_url=? WHERE id=?',
                     (t, v, c, d, i, du, app_id))
        conn.commit(); conn.close()
        return redirect(url_for('app_details', app_id=app_id))
    conn.close()
    return render_template('admin_edit.html', app=a)


@app.route('/admin/delete/<int:app_id>', methods=['POST'])
@admin_required
def admin_delete(app_id):
    conn = get_db()
    conn.execute('DELETE FROM apps WHERE id=?', (app_id,))
    conn.execute('DELETE FROM comments WHERE app_id=?', (app_id,))
    conn.execute('DELETE FROM favorites WHERE app_id=?', (app_id,))
    conn.commit(); conn.close()
    return redirect(url_for('index'))


@app.route('/admin/comment/delete/<int:comment_id>', methods=['POST'])
@admin_required
def admin_delete_comment(comment_id):
    conn = get_db()
    row = conn.execute('SELECT app_id FROM comments WHERE id=?', (comment_id,)).fetchone()
    if not row:
        conn.close()
        return render_template('404.html', msg='التعليق غير موجود'), 404
    app_id = row['app_id']
    conn.execute('DELETE FROM comments WHERE id=?', (comment_id,))
    conn.commit(); conn.close()
    return redirect(url_for('app_details', app_id=app_id))


if __name__ == '__main__':
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '5000'))
    print(f'[*] Starting on http://{host}:{port} (debug=OFF)')
    app.run(host=host, port=port, debug=False)
