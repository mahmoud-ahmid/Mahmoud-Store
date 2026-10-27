#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"

# ============ 404.html ============
cat > templates/404.html <<'EOF'
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>404 | محمود إلكترو</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-dark text-light d-flex align-items-center justify-content-center vh-100">
    <div class="text-center">
        <i class="fa-solid fa-circle-exclamation fs-1 text-warning mb-3"></i>
        <h1 class="display-1 text-info fw-bold">404</h1>
        <p class="fs-4">{{ msg or 'الصفحة غير موجودة' }}</p>
        <a href="/" class="btn btn-outline-info mt-3 rounded-pill">← العودة للمتجر</a>
    </div>
</body>
</html>
EOF

# ============ 500.html ============
cat > templates/500.html <<'EOF'
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>500 | محمود إلكترو</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-dark text-light d-flex align-items-center justify-content-center vh-100">
    <div class="text-center">
        <i class="fa-solid fa-bug fs-1 text-danger mb-3"></i>
        <h1 class="display-1 text-warning fw-bold">500</h1>
        <p class="fs-4">{{ msg or 'حدث خطأ في الخادم' }}</p>
        <a href="/" class="btn btn-outline-info mt-3 rounded-pill">← العودة للمتجر</a>
    </div>
</body>
</html>
EOF

# ============ favorites.html ============
cat > templates/favorites.html <<'EOF'
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>مفضلتي | محمود إلكترو</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: system-ui, -apple-system, sans-serif; }
        .app-card { background: #1e293b; border-radius: 20px; border: 1px solid #334155; }
        .app-icon { width: 70px; height: 70px; border-radius: 16px; object-fit: cover; }
        .user-avatar { width: 35px; height: 35px; border-radius: 50%; object-fit: cover; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark border-bottom border-secondary px-3">
        <div class="container">
            <a class="navbar-brand fw-bold text-info" href="/"><i class="fa-solid fa-microchip me-2"></i> محمود إلكترو</a>
            <div class="d-flex align-items-center gap-2">
                <a href="/" class="btn btn-outline-light btn-sm rounded-pill"><i class="fa-solid fa-house me-1"></i> المتجر</a>
                <img src="{{ user['picture'] }}" class="user-avatar" alt="Avatar">
            </div>
        </div>
    </nav>

    <div class="container my-4">
        <h2 class="fw-bold text-info mb-4"><i class="fa-solid fa-heart me-2"></i> مفضلتي</h2>
        <div class="row g-4">
            {% for app in apps %}
            <div class="col-md-6 col-lg-4">
                <div class="app-card p-3 d-flex flex-column h-100">
                    <div class="d-flex align-items-center mb-3">
                        <img src="{{ app['icon_url'] or 'https://cdn-icons-png.flaticon.com/512/2583/2583138.png' }}" class="app-icon me-3" alt="icon">
                        <div class="flex-grow-1">
                            <h5 class="mb-0 fw-bold">{{ app['title'] }}</h5>
                            <span class="badge bg-secondary mt-1">v{{ app['version'] }}</span>
                        </div>
                        <button class="btn btn-link p-0 text-danger fs-5" onclick="favApp({{ app['id'] }}, this)">
                            <i class="fa-solid fa-heart"></i>
                        </button>
                    </div>
                    <p class="text-secondary small flex-grow-1">{{ app['description'][:90] }}...</p>
                    <div class="d-flex justify-content-between align-items-center mt-3 pt-2 border-top border-secondary border-opacity-25">
                        <span class="text-warning small"><i class="fa-solid fa-star"></i> {{ app['rating'] }}</span>
                        <a href="/app/{{ app['id'] }}" class="btn btn-info btn-sm px-3">التفاصيل</a>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="text-center py-5">
                <i class="fa-regular fa-heart fs-1 text-secondary mb-3"></i>
                <p class="text-secondary">لا توجد تطبيقات في مفضلتك بعد.</p>
                <a href="/" class="btn btn-outline-info mt-2">تصفح المتجر</a>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        function favApp(appId, btn) {
            fetch('/toggle-favorite/' + appId, {
                method: 'POST',
                headers: {'X-CSRFToken': document.querySelector('meta[name=csrf-token]').content}
            })
            .then(res => {
                if (res.status === 401) { alert('سجّل دخول أولاً'); return; }
                return res.json();
            })
            .then(data => {
                if (data && data.status === 'removed') btn.remove();
            });
        }
    </script>
</body>
</html>
EOF

# ============ admin_edit.html ============
cat > templates/admin_edit.html <<'EOF'
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تعديل {{ app['title'] }} | محمود إلكترو</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
</head>
<body class="bg-dark text-light py-5">
    <div class="container" style="max-width: 600px;">
        <div class="card bg-secondary bg-opacity-25 border-secondary p-4 rounded-4">
            <h3 class="mb-4 text-info">تعديل التطبيق: {{ app['title'] }}</h3>
            {% if error %}<div class="alert alert-danger py-2 small">{{ error }}</div>{% endif %}
            <form method="POST">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <div class="mb-3">
                    <label class="form-label">اسم التطبيق</label>
                    <input type="text" name="title" class="form-control bg-dark text-light border-secondary" value="{{ app['title'] }}" required>
                </div>
                <div class="mb-3">
                    <label class="form-label">رقم الإصدار</label>
                    <input type="text" name="version" class="form-control bg-dark text-light border-secondary" value="{{ app['version'] or '' }}">
                </div>
                <div class="mb-3">
                    <label class="form-label">التصنيف</label>
                    <select name="category" class="form-select bg-dark text-light border-secondary">
                        {% for opt in ['أدوات','إنتاجية','ألعاب','أخرى'] %}
                        <option value="{{ opt }}" {% if app['category']==opt %}selected{% endif %}>{{ opt }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="mb-3">
                    <label class="form-label">رابط الأيقونة</label>
                    <input type="url" name="icon_url" class="form-control bg-dark text-light border-secondary" value="{{ app['icon_url'] or '' }}">
                </div>
                <div class="mb-3">
                    <label class="form-label">رابط التحميل</label>
                    <input type="url" name="download_url" class="form-control bg-dark text-light border-secondary" value="{{ app['download_url'] }}" required>
                </div>
                <div class="mb-3">
                    <label class="form-label">الوصف</label>
                    <textarea name="description" class="form-control bg-dark text-light border-secondary" rows="4">{{ app['description'] or '' }}</textarea>
                </div>
                <div class="d-flex gap-2">
                    <button type="submit" class="btn btn-info flex-grow-1">حفظ التعديلات</button>
                    <a href="/app/{{ app['id'] }}" class="btn btn-outline-secondary">إلغاء</a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
EOF

# ============ index.html (rewrite) ============
cat > templates/index.html <<'EOF'
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>محمود إلكترو | متجر التطبيقات</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root { --bg-dark: #0f172a; --card-bg: #1e293b; --accent: #38bdf8; }
        body { background-color: var(--bg-dark); color: #f8fafc; font-family: system-ui, -apple-system, sans-serif; }
        .navbar { background: rgba(30, 41, 59, 0.8); backdrop-filter: blur(10px); border-bottom: 1px solid #334155; }
        .app-card { background: var(--card-bg); border-radius: 20px; border: 1px solid #334155; transition: all 0.3s ease; }
        .app-card:hover { transform: translateY(-5px); border-color: var(--accent); box-shadow: 0 10px 20px rgba(56, 189, 248, 0.15); }
        .app-icon { width: 70px; height: 70px; border-radius: 16px; object-fit: cover; }
        .btn-accent { background: var(--accent); color: #0f172a; font-weight: bold; border-radius: 12px; }
        .user-avatar { width: 35px; height: 35px; border-radius: 50%; object-fit: cover; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark sticky-top px-3">
        <div class="container">
            <a class="navbar-brand fw-bold fs-4 text-info" href="/"><i class="fa-solid fa-microchip me-2"></i> محمود إلكترو</a>
            <div class="d-flex align-items-center gap-2">
                {% if user %}
                    {% if not user.get('is_admin') %}
                    <a href="/favorites" class="btn btn-outline-danger btn-sm rounded-pill"><i class="fa-solid fa-heart me-1"></i> مفضلتي</a>
                    {% endif %}
                    <div class="dropdown">
                        <button class="btn btn-outline-light btn-sm dropdown-toggle d-flex align-items-center gap-2" type="button" data-bs-toggle="dropdown">
                            <img src="{{ user['picture'] }}" class="user-avatar" alt="Avatar">
                            <span>{{ user['name'] }}</span>
                        </button>
                        <ul class="dropdown-menu dropdown-menu-dark">
                            {% if user.get('is_admin') %}
                                <li><a class="dropdown-item text-info" href="/admin/add"><i class="fa-solid fa-plus me-1"></i> إضافة تطبيق</a></li>
                            {% endif %}
                            <li><a class="dropdown-item text-danger" href="/logout"><i class="fa-solid fa-right-from-bracket me-1"></i> خروج</a></li>
                        </ul>
                    </div>
                {% else %}
                    <a href="/login/google" class="btn btn-outline-light btn-sm rounded-pill"><i class="fa-brands fa-google text-danger me-1"></i> دخول بـ Google</a>
                    <a href="/login/admin" class="btn btn-outline-info btn-sm rounded-pill"><i class="fa-brands fa-github me-1"></i> دخول الأدمن</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <div class="container my-4">
        <div class="p-4 p-md-5 mb-4 rounded-4 bg-gradient text-center" style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155;">
            <h1 class="display-6 fw-bold text-info mb-2">متجر تطبيقات محمود إلكترو</h1>
            <p class="text-secondary fs-5">حمل أحدث التطبيقات مجاناً - سجل بـ Google لحفظ مفضلتك!</p>
            <form method="GET" action="/" class="mx-auto mt-3" style="max-width: 480px;">
                <div class="input-group">
                    <input type="text" name="q" class="form-control bg-dark text-light border-secondary" placeholder="ابحث عن تطبيق..." value="{{ q or '' }}">
                    {% if current_cat != 'all' %}<input type="hidden" name="cat" value="{{ current_cat }}">{% endif %}
                    <button class="btn btn-info" type="submit"><i class="fa-solid fa-search"></i> بحث</button>
                </div>
            </form>
        </div>

        {% if q %}
        <div class="alert alert-info py-2 small">
            نتائج البحث عن: <strong>{{ q }}</strong> — <a href="/" class="text-info">مسح</a>
        </div>
        {% endif %}

        <div class="row g-4">
            {% for app in apps %}
            <div class="col-md-6 col-lg-4">
                <div class="app-card p-3 d-flex flex-column h-100">
                    <div class="d-flex align-items-center mb-3">
                        <img src="{{ app['icon_url'] or 'https://cdn-icons-png.flaticon.com/512/2583/2583138.png' }}" class="app-icon me-3" alt="icon">
                        <div class="flex-grow-1">
                            <h5 class="mb-0 fw-bold">{{ app['title'] }}</h5>
                            <span class="badge bg-secondary mt-1">v{{ app['version'] }}</span>
                        </div>
                        {% if user and not user.get('is_admin') %}
                        <button class="btn btn-link p-0 text-danger fs-5" onclick="favApp({{ app['id'] }}, this)">
                            <i class="{% if app['id'] in user_favs %}fa-solid{% else %}fa-regular{% endif %} fa-heart"></i>
                        </button>
                        {% endif %}
                    </div>
                    <p class="text-secondary small flex-grow-1">{{ app['description'][:90] }}...</p>
                    <div class="d-flex justify-content-between align-items-center mt-3 pt-2 border-top border-secondary border-opacity-25">
                        <div class="text-warning small"><i class="fa-solid fa-star"></i> {{ app['rating'] }}</div>
                        <a href="/app/{{ app['id'] }}" class="btn btn-accent btn-sm px-3">التفاصيل والتحميل</a>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="text-center py-5">
                <i class="fa-solid fa-box-open fs-1 text-secondary mb-3"></i>
                <p class="text-secondary">لا توجد تطبيقات مطابقة.</p>
            </div>
            {% endfor %}
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function favApp(appId, btn) {
            fetch('/toggle-favorite/' + appId, {
                method: 'POST',
                headers: {'X-CSRFToken': document.querySelector('meta[name=csrf-token]').content}
            })
            .then(res => {
                if (res.status === 401) { alert('يرجى تسجيل الدخول بحساب Google'); return; }
                return res.json();
            })
            .then(data => {
                if (data && data.status) {
                    const icon = btn.querySelector('i');
                    icon.classList.toggle('fa-solid');
                    icon.classList.toggle('fa-regular');
                }
            });
        }
    </script>
</body>
</html>
EOF

# ============ detail.html (rewrite with admin buttons) ============
cat > templates/detail.html <<'EOF'
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ app['title'] }} | محمود إلكترو</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: system-ui, -apple-system, sans-serif; }
        .card-custom { background: #1e293b; border-radius: 20px; border: 1px solid #334155; }
        .app-large-icon { width: 100px; height: 100px; border-radius: 24px; object-fit: cover; }
    </style>
</head>
<body class="py-4">
    <div class="container">
        <a href="/" class="btn btn-outline-secondary mb-4"><i class="fa-solid fa-arrow-right me-1"></i> العودة للمتجر</a>

        {% if user and user.get('is_admin') %}
        <div class="alert alert-warning d-flex gap-2 align-items-center mb-3 py-2">
            <i class="fa-solid fa-shield-halved"></i>
            <span class="small">أنت أدمن — يمكنك التعديل والحذف</span>
            <a href="/admin/edit/{{ app['id'] }}" class="btn btn-sm btn-outline-dark ms-auto"><i class="fa-solid fa-pen me-1"></i> تعديل</a>
            <form method="POST" action="/admin/delete/{{ app['id'] }}" onsubmit="return confirm('حذف التطبيق وكل تعليقاته؟ لا يمكن التراجع.');" class="d-inline">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <button class="btn btn-sm btn-danger"><i class="fa-solid fa-trash me-1"></i> حذف</button>
            </form>
        </div>
        {% endif %}

        <div class="card-custom p-4 mb-4">
            <div class="d-flex align-items-center flex-wrap gap-3">
                <img src="{{ app['icon_url'] or 'https://cdn-icons-png.flaticon.com/512/2583/2583138.png' }}" class="app-large-icon" alt="App Icon">
                <div>
                    <h2 class="fw-bold mb-1">{{ app['title'] }}</h2>
                    <p class="text-info mb-1">الإصدار: v{{ app['version'] }} | التصنيف: {{ app['category'] }}</p>
                    <span class="text-warning"><i class="fa-solid fa-star"></i> {{ app['rating'] }} / 5.0</span>
                    <span class="text-secondary ms-3 small"><i class="fa-solid fa-download me-1"></i> {{ app['downloads_count'] }} تحميل</span>
                </div>
                <div class="ms-auto w-100 w-md-auto mt-3 mt-md-0">
                    <a href="/download/{{ app['id'] }}" class="btn btn-success btn-lg w-100 px-4 rounded-3"><i class="fa-solid fa-download me-2"></i> تحميل التطبيق</a>
                </div>
            </div>
            <hr class="my-4 border-secondary opacity-25">
            <h5 class="fw-bold text-info mb-2">وصف التطبيق</h5>
            <p class="text-light fs-6" style="white-space: pre-line;">{{ app['description'] }}</p>
        </div>

        <div class="card-custom p-4">
            <h5 class="fw-bold mb-3"><i class="fa-solid fa-comments text-info me-2"></i> التعليقات والآراء</h5>
            <form action="/comment/{{ app['id'] }}" method="POST" class="mb-4">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                {% if not user %}
                <div class="mb-2">
                    <input type="text" name="user_name" class="form-control bg-dark text-light border-secondary" placeholder="اسمك (اختياري)" maxlength="40">
                </div>
                {% endif %}
                <div class="mb-2">
                    <textarea name="comment" class="form-control bg-dark text-light border-secondary" rows="2" placeholder="اكتب تعليقك..." required maxlength="2000"></textarea>
                </div>
                <button type="submit" class="btn btn-info btn-sm"><i class="fa-solid fa-paper-plane me-1"></i> نشر التعليق</button>
            </form>

            <div class="vstack gap-3">
                {% for c in comments %}
                <div class="p-3 rounded-3 bg-dark bg-opacity-50 border border-secondary border-opacity-25">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <strong class="text-info">{{ c['user_name'] }}</strong>
                            <small class="text-secondary ms-2">{{ c['created_at'] }}</small>
                        </div>
                        {% if user and user.get('is_admin') %}
                        <form method="POST" action="/admin/comment/delete/{{ c['id'] }}" onsubmit="return confirm('حذف التعليق؟');">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                            <button class="btn btn-sm btn-outline-danger py-0 px-2"><i class="fa-solid fa-trash small"></i></button>
                        </form>
                        {% endif %}
                    </div>
                    <p class="mb-0 mt-1 text-light fs-6">{{ c['comment'] }}</p>
                </div>
                {% else %}
                <p class="text-secondary small">لا توجد تعليقات بعد. كن أول من يعلق!</p>
                {% endfor %}
            </div>
        </div>
    </div>
</body>
</html>
EOF

# ============ Add CSRF hidden input to remaining forms ============
python - <<'PY'
import re

def add_csrf(path, marker='<form method="POST">', indent='                '):
    try:
        s = open(path, encoding='utf-8').read()
    except FileNotFoundError:
        print(f'  ! {path} missing'); return
    if 'csrf_token' in s:
        print(f'  ✓ {path} already has CSRF'); return
    if marker not in s:
        print(f'  ! {path}: marker not found — check manually'); return
    s = s.replace(marker, f'{marker}\n{indent}<input type="hidden" name="csrf_token" value="{{{{ csrf_token() }}}}">', 1)
    open(path, 'w', encoding='utf-8').write(s)
    print(f'  ✓ {path}')

add_csrf('templates/admin.html')
add_csrf('templates/admin_login.html', indent='            ')
add_csrf('templates/google_login.html', indent='            ')
PY

echo ""
echo "✓ Phase 2 templates applied"
exit 0
