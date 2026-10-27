import sys
from pathlib import Path

APP = Path('app.py')
src = APP.read_text(encoding='utf-8')
changes = 0

def apply(name, old, new):
    global src, changes
    if new in src:
        print(f'[=] {name}: already')
        return True
    if old not in src:
        print(f'[X] {name}: NOT found', file=sys.stderr)
        return False
    src = src.replace(old, new, 1)
    changes += 1
    print(f'[v] {name}')
    return True

ok = True

# 1) Parse sort/page
ok &= apply('parse sort/page',
    """    q   = (request.args.get('q') or '').strip()[:80]
    where, params = [], []""",
    """    q   = (request.args.get('q') or '').strip()[:80]
    sort = request.args.get('sort', 'newest')
    if sort not in ('newest', 'downloads', 'rating', 'title'):
        sort = 'newest'
    try:
        page = max(1, int(request.args.get('page', '1')))
    except (ValueError, TypeError):
        page = 1
    per_page = 12
    offset = (page - 1) * per_page
    where, params = [], []""")

# 2) Paginated query
ok &= apply('paginated query',
    "    apps = conn.execute(f'SELECT * FROM apps{where_sql} ORDER BY id DESC', params).fetchall()",
    """    order_map = {'newest': 'id DESC', 'downloads': 'downloads_count DESC, id DESC',
                 'rating': 'rating DESC, id DESC', 'title': 'title ASC'}
    order_sql = order_map.get(sort, 'id DESC')
    total = conn.execute(f'SELECT COUNT(*) FROM apps{where_sql}', params).fetchone()[0]
    apps = conn.execute(
        f'SELECT * FROM apps{where_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?',
        params + [per_page, offset]
    ).fetchall()""")

# 3) Template vars
ok &= apply('template vars',
    """    conn.close()
    return render_template('index.html', apps=apps, current_cat=cat, q=q,
                           user=user, user_favs=favs,
                           admin_username=ADMIN_USERNAME,
                           rating_counts=rating_counts)""",
    """    categories = [r[0] for r in conn.execute(
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
                           total=total)""")

if not ok:
    print('\n[X] failed — NOT writing', file=sys.stderr)
    sys.exit(2)

APP.write_text(src, encoding='utf-8')
print(f'[v] app.py: {len(src.splitlines())} lines, {changes} changes')
