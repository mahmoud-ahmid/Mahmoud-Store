from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'mahmoud_electro_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

def init_db():
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id TEXT UNIQUE,
            name TEXT,
            email TEXT,
            picture TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS apps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            version TEXT,
            category TEXT,
            description TEXT,
            icon_url TEXT,
            download_url TEXT,
            downloads_count INTEGER DEFAULT 0,
            rating REAL DEFAULT 5.0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER,
            app_id INTEGER,
            PRIMARY KEY (user_id, app_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id INTEGER,
            user_name TEXT,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect('store.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    category = request.args.get('cat', 'all')
    conn = get_db()
    if category != 'all':
        apps = conn.execute('SELECT * FROM apps WHERE category = ?', (category,)).fetchall()
    else:
        apps = conn.execute('SELECT * FROM apps ORDER BY id DESC').fetchall()
    
    user = session.get('user')
    user_favs = []
    if user:
        fav_rows = conn.execute('SELECT app_id FROM favorites WHERE user_id = ?', (user['id'],)).fetchall()
        user_favs = [r['app_id'] for r in fav_rows]
        
    conn.close()
    return render_template('index.html', apps=apps, current_cat=category, user=user, user_favs=user_favs)

@app.route('/login/google')
def google_login():
    session['user'] = {
        'id': 1,
        'name': 'مستخدم جوجل',
        'email': 'user@gmail.com',
        'picture': 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png'
    }
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/app/<int:app_id>')
def app_details(app_id):
    conn = get_db()
    app_data = conn.execute('SELECT * FROM apps WHERE id = ?', (app_id,)).fetchone()
    comments = conn.execute('SELECT * FROM comments WHERE app_id = ? ORDER BY id DESC', (app_id,)).fetchall()
    conn.close()
    return render_template('detail.html', app=app_data, comments=comments, user=session.get('user'))

@app.route('/toggle-favorite/<int:app_id>', methods=['POST'])
def toggle_favorite(app_id):
    user = session.get('user')
    if not user:
        return jsonify({'status': 'error', 'message': 'التسجيل مطلوب لحفظ المفضلة'}), 401
    
    conn = get_db()
    exist = conn.execute('SELECT * FROM favorites WHERE user_id = ? AND app_id = ?', (user['id'], app_id)).fetchone()
    if exist:
        conn.execute('DELETE FROM favorites WHERE user_id = ? AND app_id = ?', (user['id'], app_id))
        status = 'removed'
    else:
        conn.execute('INSERT INTO favorites (user_id, app_id) VALUES (?, ?)', (user['id'], app_id))
        status = 'added'
    conn.commit()
    conn.close()
    return jsonify({'status': status})

@app.route('/comment/<int:app_id>', methods=['POST'])
def add_comment(app_id):
    user = session.get('user')
    user_name = user['name'] if user else request.form.get('user_name', 'متابع زائر')
    comment = request.form.get('comment')
    if comment:
        conn = get_db()
        conn.execute('INSERT INTO comments (app_id, user_name, comment) VALUES (?, ?, ?)', (app_id, user_name, comment))
        conn.commit()
        conn.close()
    return redirect(url_for('app_details', app_id=app_id))

@app.route('/admin/add', methods=['GET', 'POST'])
def admin_add():
    if request.method == 'POST':
        title = request.form['title']
        version = request.form['version']
        category = request.form['category']
        description = request.form['description']
        icon_url = request.form['icon_url']
        download_url = request.form['download_url']
        
        conn = get_db()
        conn.execute('''
            INSERT INTO apps (title, version, category, description, icon_url, download_url)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, version, category, description, icon_url, download_url))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('admin.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
