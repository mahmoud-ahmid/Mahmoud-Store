#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")" || exit 1
if [ -f server.pid ] && kill -0 "$(cat server.pid)" 2>/dev/null; then
    kill "$(cat server.pid)" && rm -f server.pid
    echo "✓ تم إيقاف الخادم"
else
    echo "الخادم لا يعمل"
    rm -f server.pid 2>/dev/null
fi
