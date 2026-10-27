from pathlib import Path
import sys

p = Path('templates/index.html')
s = p.read_text(encoding='utf-8')
orig_len = len(s)

# 1) manifest + theme-color before </head>
if 'manifest.json' in s:
    print('[=] manifest already linked')
elif '</head>' in s:
    ins = ('    <link rel="manifest" href="/static/manifest.json">\n'
           '    <meta name="theme-color" content="#38bdf8">\n'
           '</head>')
    s = s.replace('</head>', ins, 1)
    print('[v] manifest + theme-color inserted')
else:
    print('[X] </head> NOT found', file=sys.stderr)
    sys.exit(2)

# 2) service worker registration before </body>
if 'serviceWorker' in s:
    print('[=] SW already registered')
elif '</body>' in s:
    sw = (
        '    <script>\n'
        "        if ('serviceWorker' in navigator) {\n"
        "            navigator.serviceWorker.register('/service-worker.js', { scope: '/' })\n"
        "              .then(r => console.log('SW registered:', r.scope))\n"
        "              .catch(e => console.error('SW failed:', e));\n"
        '        }\n'
        '    </script>\n'
        '</body>'
    )
    s = s.replace('</body>', sw, 1)
    print('[v] service worker registration inserted')
else:
    print('[X] </body> NOT found', file=sys.stderr)
    sys.exit(2)

p.write_text(s, encoding='utf-8')
print(f'[v] file: {orig_len} → {len(s)} bytes')
