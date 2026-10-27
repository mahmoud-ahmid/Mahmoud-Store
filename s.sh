cd ~/Mahmoud-Store
echo "manifest:  $(grep -c 'manifest.json' templates/index.html)"
echo "SW:        $(grep -c 'serviceWorker' templates/index.html)"
echo "head:      $(grep -c '</head>' templates/index.html)"
echo "body:      $(grep -c '</body>' templates/index.html)"
python -m py_compile app.py && echo "compile: OK"
