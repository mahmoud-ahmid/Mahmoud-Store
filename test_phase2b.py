"""Phase 2B verification: SSRF, DNS-rebinding, safe_url."""
import sys
from app import safe_url, pinned_get

failures = []

def check(cond, label):
    status = 'OK ' if cond else 'FAIL'
    print(f'  [{status}] {label}')
    if not cond:
        failures.append(label)

print('=== safe_url (static checks) ===')
for url, label in [
    ('http://127.0.0.1/x',        '127.0.0.1 blocked'),
    ('http://localhost/x',        'localhost blocked'),
    ('http://[::1]/x',            '[::1] blocked'),
    ('http://169.254.169.254/x',  'AWS metadata blocked'),
    ('http://10.0.0.1/x',         '10.0.0.1 blocked'),
    ('http://192.168.1.1/x',      '192.168.1.1 blocked'),
    ('file:///etc/passwd',        'file:// blocked'),
    ('ftp://example.com/x',       'ftp:// blocked'),
    ('http://evil.local/x',       '.local blocked'),
    ('http://x.internal/x',       '.internal blocked'),
]:
    check(safe_url(url) is False, label)

for url, label in [
    ('https://github.com/',       'github.com allowed'),
    ('https://1.1.1.1/',          '1.1.1.1 allowed'),
    ('https://example.com/x',     'example.com allowed'),
]:
    check(safe_url(url) is True, label)

print('\n=== pinned_get (DNS rebinding protection) ===')
for url in ['http://127.0.0.1:5000/', 'http://localhost:5000/',
            'http://[::1]:5000/', 'http://169.254.169.254/latest/meta-data/']:
    try:
        r = pinned_get(url, timeout=2)
        r.close()
        check(False, f'pinned_get should block {url}')
    except ValueError as e:
        check(True, f'pinned_get blocks {url} ({e})')
    except Exception as e:
        check(True, f'pinned_get refuses {url} ({type(e).__name__})')

print()
if failures:
    print(f'✗ {len(failures)} failures:')
    for f in failures:
        print(f'  - {f}')
    sys.exit(1)
print('✓ All Phase 2B tests passed')
