#Fixed: admin bypass, SSRF, zip-bomb, rate limit, headers, cookies, debug.

import io
import hmac
import ipaddress
import socket
import sqlite3
import zipfile
from functools import wraps
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
    WTF_CSRF_TIME_LIMIT=None,
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
    ''')
    conn.commit(); conn.close()

init_db()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
        "connect-src 'self'; frame-ancestors 'none'")
    return resp


@app.errorhandler(404)
def _nf(_): return render_template('404.html'), 404

@app.errorhandler(500)
def _err(_): return render_template('500.html'), 500

@app.errorhandler(413)
def _too_large(_): return "الطلب كبير جداً", 413

@app.errorhandler(CSRFError)
def _csrf_err(_):
    return render_template('500.html',
                           msg='انتهت صلاحية النموذج — أعد تحميل الصفحة وحاول مجدداً'), 400


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


@app.route('/')
def index():
    cat = request.args.get('cat', 'all')
    q   = (request.args.get('q') or '').strip()[:80]
    where, params = [], []
    if cat != 'all':
        where.append('category = ?'); params.append(cat)
    if q:
        where.append('(title LIKE ? OR description LIKE ?)')
        params.extend([f'%{q}%', f'%{q}%'])
    where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
    conn = get_db()
    apps = conn.execute(f'SELECT * FROM apps{where_sql} ORDER BY id DESC', params).fetchall()
    user = session.get('user')
    favs = []
    if user and user.get('id') != 'admin':
        try:
            favs = [r['app_id'] for r in conn.execute(
                'SELECT app_id FROM favorites WHERE user_id=?', (user['id'],)).fetchall()]
        except Exception:
            pass
    conn.close()
    return render_template('index.html', apps=apps, current_cat=cat, q=q,
                           user=user, user_favs=favs, admin_username=ADMIN_USERNAME)


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


@app.route('/login/admin', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def admin_login():
    if request.method == 'POST':
        u  = request.form.get('username', '').strip()
        pw = request.form.get('password', '')
        if not ADMIN_PASSWORD:
            return render_template('admin_login.html',
                                   error='ADMIN_PASSWORD غير مضبوط في .env'), 500
        ok_user = hmac.compare_digest(u.lower(), ADMIN_USERNAME.lower())
        ok_pass = hmac.compare_digest(pw, ADMIN_PASSWORD)
        if ok_user and ok_pass:
            session.clear()  # ← Session fixation protection
            session['user'] = {'id': 'admin', 'name': u, 'email': 'admin@local',
                               'picture': f'https://github.com/{u}.png',
                               'is_admin': True}
            session.modified = True
            return redirect(url_for('index'))
        return render_template('admin_login.html', error='بيانات الدخول غير صحيحة')
    return render_template('admin_login.html')


@app.route('/login/google', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def google_login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        name  = (request.form.get('name')  or '').strip()[:60]
        if '@' not in email or len(email) > 120 or len(name) < 2:
            return render_template('google_login.html', error='بيانات غير صالحة'), 400
        conn = get_db()
        row = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        if row:
            uid = row['id']; pic = row['picture']
        else:
            pic = 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png'
            cur = conn.execute('INSERT INTO users(email,name,picture) VALUES(?,?,?)',
                               (email, name, pic))
            conn.commit(); uid = cur.lastrowid
        conn.close()
        session.clear()
        session['user'] = {'id': uid, 'name': name, 'email': email,
                           'picture': pic, 'is_admin': False}
        session.modified = True
        return redirect(url_for('index'))
    return render_template('google_login.html')


@app.route('/logout')
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
    conn.close()
    return render_template('detail.html', app=a, comments=comments,
                           user=session.get('user'))


@app.route('/download/<int:app_id>')
@limiter.limit("20 per hour")
def download_app(app_id):
    conn = get_db()
    a = conn.execute('SELECT * FROM apps WHERE id=?', (app_id,)).fetchone()
    if not a:
        conn.close(); return "التطبيق غير موجود", 404
    conn.execute('UPDATE apps SET downloads_count=downloads_count+1 WHERE id=?', (app_id,))
    conn.commit(); conn.close()

    raw = a['download_url'] or ''
    if not safe_url(raw):
        return "رابط التنزيل غير مسموح", 400
    if raw.lower().endswith(('.apk', '.exe')):
        return redirect(raw)
    try:
        r = requests.get(raw, timeout=10, stream=True, allow_redirects=False)
        if r.status_code != 200 or 'zip' not in r.headers.get('content-type', '').lower():
            return redirect(raw)
        buf = io.BytesIO(); size = 0
        for chunk in r.iter_content(65536):
            size += len(chunk)
            if size > MAX_DL: return "الملف كبير جداً", 413
            buf.write(chunk)
        buf.seek(0)
        z = zipfile.ZipFile(buf)
        for fi in z.infolist():
            if fi.file_size > MAX_DL: continue
            if fi.filename.lower().endswith(('.apk', '.exe', '.py')):
                data = z.read(fi.filename)
                return send_file(io.BytesIO(data), as_attachment=True,
                                 download_name=os.path.basename(fi.filename))
        return redirect(raw)
    except Exception:
        return redirect(raw)


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


load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise SystemExit('ERROR: SECRET_KEY missing from .env')

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
)

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
    ''')
    conn.commit(); conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
        "connect-src 'self'; frame-ancestors 'none'")
    return resp


@app.errorhandler(404)
def _nf(_): return "404 — الصفحة غير موجودة", 404

@app.errorhandler(500)
def _err(_): return "500 — خطأ في الخادم", 500

@app.errorhandler(413)
def _too_large(_): return "الطلب كبير جداً", 413


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


@app.route('/')
def index():
    cat = request.args.get('cat', 'all')
    conn = get_db()
    if cat != 'all':
        apps = conn.execute('SELECT * FROM apps WHERE category=? ORDER BY id DESC', (cat,)).fetchall()
    else:
        apps = conn.execute('SELECT * FROM apps ORDER BY id DESC').fetchall()
    user = session.get('user')
    favs = []
    if user and user.get('id') != 'admin':
        try:
            favs = [r['app_id'] for r in conn.execute(
                'SELECT app_id FROM favorites WHERE user_id=?', (user['id'],)).fetchall()]
        except Exception:
            pass
    conn.close()
    return render_template('index.html', apps=apps, current_cat=cat,
                           user=user, user_favs=favs, admin_username=ADMIN_USERNAME)


@app.route('/login/admin', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def admin_login():
    if request.method == 'POST':
        u  = request.form.get('username', '').strip()
        pw = request.form.get('password', '')
        if not ADMIN_PASSWORD:
            return render_template('admin_login.html',
                                   error='ADMIN_PASSWORD غير مضبوط في .env'), 500
        ok_user = hmac.compare_digest(u.lower(), ADMIN_USERNAME.lower())
        ok_pass = hmac.compare_digest(pw, ADMIN_PASSWORD)
        if ok_user and ok_pass:
            session['user'] = {'id': 'admin', 'name': u, 'email': 'admin@local',
                               'picture': f'https://github.com/{u}.png',
                               'is_admin': True}
            return redirect(url_for('index'))
        return render_template('admin_login.html', error='بيانات الدخول غير صحيحة')
    return render_template('admin_login.html')


@app.route('/login/google', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def google_login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        name  = (request.form.get('name')  or '').strip()[:60]
        if '@' not in email or len(email) > 120 or len(name) < 2:
            return render_template('google_login.html', error='بيانات غير صالحة'), 400
        conn = get_db()
        row = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        if row:
            uid = row['id']; pic = row['picture']
        else:
            pic = 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png'
            cur = conn.execute('INSERT INTO users(email,name,picture) VALUES(?,?,?)',
                               (email, name, pic))
            conn.commit(); uid = cur.lastrowid
        conn.close()
        session['user'] = {'id': uid, 'name': name, 'email': email,
                           'picture': pic, 'is_admin': False}
        return redirect(url_for('index'))
    return render_template('google_login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/app/<int:app_id>')
def app_details(app_id):
    conn = get_db()
    a = conn.execute('SELECT * FROM apps WHERE id=?', (app_id,)).fetchone()
    if not a:
        conn.close()
        return "404 — التطبيق غير موجود", 404
    comments = conn.execute('SELECT * FROM comments WHERE app_id=? ORDER BY id DESC',
                            (app_id,)).fetchall()
    conn.close()
    return render_template('detail.html', app=a, comments=comments,
                           user=session.get('user'))


@app.route('/download/<int:app_id>')
@limiter.limit("20 per hour")
def download_app(app_id):
    conn = get_db()
    a = conn.execute('SELECT * FROM apps WHERE id=?', (app_id,)).fetchone()
    if not a:
        conn.close(); return "التطبيق غير موجود", 404
    conn.execute('UPDATE apps SET downloads_count=downloads_count+1 WHERE id=?', (app_id,))
    conn.commit(); conn.close()

    raw = a['download_url'] or ''
    if not safe_url(raw):
        return "رابط التنزيل غير مسموح", 400

    if raw.lower().endswith(('.apk', '.exe')):
        return redirect(raw)

    try:
        r = requests.get(raw, timeout=10, stream=True, allow_redirects=False)
        if r.status_code != 200 or 'zip' not in r.headers.get('content-type', '').lower():
            return redirect(raw)
        buf = io.BytesIO()
        size = 0
        for chunk in r.iter_content(65536):
            size += len(chunk)
            if size > MAX_DL:
                return "الملف كبير جداً", 413
            buf.write(chunk)
        buf.seek(0)
        z = zipfile.ZipFile(buf)
        for fi in z.infolist():
            if fi.file_size > MAX_DL:
                continue
            if fi.filename.lower().endswith(('.apk', '.exe', '.py')):
                data = z.read(fi.filename)
                return send_file(io.BytesIO(data), as_attachment=True,
                                 download_name=os.path.basename(fi.filename))
        return redirect(raw)
    except Exception:
        return redirect(raw)


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


if __name__ == '__main__':
    init_db()
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '5000'))
    print(f'[*] Starting on http://{host}:{port} (debug=OFF)')
    app.run(host=host, port=port, debug=False)

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise SystemExit('ERROR: SECRET_KEY missing from .env')

DB_PATH        = os.environ.get('DB_PATH', 'store.db')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'mahmoud-ahmid')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
MAX_DL         = int(os.environ.get('MAX_DOWNLOAD_MB', '200')) * 1024 * 1024
PROD           = os.environ.get('FLASK_ENV') == 'production'

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Strict',   # ← CSRF mitigation without template edits
    SESSION_COOKIE_SECURE=PROD and os.environ.get('HTTPS') == '1',
    MAX_CONTENT_LENGTH=2 * 1024 * 1024, # 2MB max request body
)

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
        CREATE INDEX IF NOT EXISTS idx_apps_cat  ON apps(category);
        CREATE INDEX IF NOT EXISTS idx_comm_app  ON comments(app_id);
        CREATE INDEX IF NOT EXISTS idx_fav_user  ON favorites(user_id);
    ''')
    conn.commit(); conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
        "connect-src 'self'; frame-ancestors 'none'")
    return resp


@app.errorhandler(404)
def _nf(_):
    return "404 — الصفحة غير موجودة", 404


@app.errorhandler(500)
def _err(_):
    return "500 — خطأ في الخادم", 500


@app.errorhandler(413)
def _too_large(_):
    return "الطلب كبير جداً", 413


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        u = session.get('user')
        if not u or not u.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*a, **k)
    return w


def safe_url(url: str) -> bool:
    """Reject non-http(s) and any URL resolving to private/loopback/link-local IP."""
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
            if (ip.is_private or ip.is_loopback
                    or ip.is_link_local or ip.is_reserved or ip.is_multicast):
                return False
    except Exception:
        return False
    return True


# ---------- public routes ----------

@app.route('/')
def index():
    cat = request.args.get('cat', 'all')
    conn = get_db()
    if cat != 'all':
        apps = conn.execute('SELECT * FROM apps WHERE category=? ORDER BY id DESC', (cat,)).fetchall()
    else:
        apps = conn.execute('SELECT * FROM apps ORDER BY id DESC').fetchall()
    user = session.get('user')
    favs = []
    if user and user.get('id') != 'admin':
        try:
            favs = [r['app_id'] for r in conn.execute(
                'SELECT app_id FROM favorites WHERE user_id=?', (user['id'],)).fetchall()]
        except Exception:
            pass
    conn.close()
    return render_template('index.html', apps=apps, current_cat=cat,
                           user=user, user_favs=favs, admin_username=ADMIN_USERNAME)


@app.route('/login/admin', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def admin_login():
    if request.method == 'POST':
        u  = request.form.get('username', '').strip()
        pw = request.form.get('password', '')
        if not ADMIN_PASSWORD:
            return render_template('admin_login.html',
                                   error='ADMIN_PASSWORD غير مضبوط في .env'), 500
        ok_user = hmac.compare_digest(u.lower(), ADMIN_USERNAME.lower())
        ok_pass = hmac.compare_digest(pw, ADMIN_PASSWORD)
        if ok_user and ok_pass:
            session['user'] = {'id': 'admin', 'name': u, 'email': 'admin@local',
                               'picture': f'https://github.com/{u}.png',
                               'is_admin': True}
            return redirect(url_for('index'))
        return render_template('admin_login.html', error='بيانات الدخول غير صحيحة')
    return render_template('admin_login.html')


@app.route('/login/google', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def google_login():
    # NOTE: this is a placeholder. For real OAuth use Authlib + Google client_id/secret.
    # Kept functional but rate-limited and input-validated to prevent abuse.
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        name  = (request.form.get('name')  or '').strip()[:60]
        if '@' not in email or len(email) > 120 or len(name) < 2:
            return render_template('google_login.html', error='بيانات غير صالحة'), 400
        conn = get_db()
        row = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        if row:
            uid = row['id']; pic = row['picture']
        else:
            pic = 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png'
            cur = conn.execute('INSERT INTO users(email,name,picture) VALUES(?,?,?)',
                               (email, name, pic))
            conn.commit(); uid = cur.lastrowid
        conn.close()
        session['user'] = {'id': uid, 'name': name, 'email': email,
                           'picture': pic, 'is_admin': False}
        return redirect(url_for('index'))
    return render_template('google_login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/app/<int:app_id>')
def app_details(app_id):
    conn = get_db()
    a = conn.execute('SELECT * FROM apps WHERE id=?', (app_id,)).fetchone()
    if not a:
        conn.close()
        return "404 — التطبيق غير موجود", 404
    comments = conn.execute('SELECT * FROM comments WHERE app_id=? ORDER BY id DESC',
                            (app_id,)).fetchall()
    conn.close()
    return render_template('detail.html', app=a, comments=comments,
                           user=session.get('user'))


@app.route('/download/<int:app_id>')
@limiter.limit("20 per hour")
def download_app(app_id):
    conn = get_db()
    a = conn.execute('SELECT * FROM apps WHERE id=?', (app_id,)).fetchone()
    if not a:
        conn.close(); return "التطبيق غير موجود", 404
    conn.execute('UPDATE apps SET downloads_count=downloads_count+1 WHERE id=?', (app_id,))
    conn.commit(); conn.close()

    raw = a['download_url'] or ''
    if not safe_url(raw):
        return "رابط التنزيل غير مسموح", 400

    if raw.lower().endswith(('.apk', '.exe')):
        return redirect(raw)

    try:
        r = requests.get(raw, timeout=10, stream=True, allow_redirects=False)
        if r.status_code != 200 or 'zip' not in r.headers.get('content-type', '').lower():
            return redirect(raw)
        buf = io.BytesIO()
        size = 0
        for chunk in r.iter_content(65536):
            size += len(chunk)
            if size > MAX_DL:
                return "الملف كبير جداً", 413
            buf.write(chunk)
        buf.seek(0)
        z = zipfile.ZipFile(buf)
        for fi in z.infolist():
            if fi.file_size > MAX_DL:
                continue
            if fi.filename.lower().endswith(('.apk', '.exe', '.py')):
                data = z.read(fi.filename)
                return send_file(io.BytesIO(data), as_attachment=True,
                                 download_name=os.path.basename(fi.filename))
        return redirect(raw)
    except Exception:
        return redirect(raw)


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


if __name__ == '__main__':
    init_db()
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '5000'))
    print(f'[*] Starting on http://{host}:{port} (debug=OFF)')
    app.run(host=host, port=port, debug=False)
