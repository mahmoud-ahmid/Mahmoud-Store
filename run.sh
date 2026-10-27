#!/data/data/com.termux/files/usr/bin/bash
# Mahmoud-Store — تشغيل الخادم للوصول من الشبكة
cd "$(dirname "$0")" || exit 1

if [ -f server.pid ] && kill -0 "$(cat server.pid)" 2>/dev/null; then
    echo "⚠ الخادم يعمل بالفعل (PID $(cat server.pid))"
    echo "  استخدم ./stop.sh لإيقافه"
    exit 1
fi

# اكتشاف IP المحلي
IP=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
[ -z "$IP" ] && IP=$(ifconfig 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '^127' | head -1)
[ -z "$IP" ] && IP="<IP-غير-معروف>"

echo "═══ Mahmoud-Store ═══"
echo "محلي:  http://127.0.0.1:5000"
echo "شبكة:  http://$IP:5000"
echo ""
echo "⚠  أي جهاز على نفس WiFi يمكنه الوصول."
echo "   لا تشغّله على WiFi عام."
echo ""

HOST=0.0.0.0 PORT=5000 nohup python app.py > server.log 2>&1 &
echo $! > server.pid
sleep 1

if kill -0 "$(cat server.pid)" 2>/dev/null; then
    echo "✓ يعمل (PID $(cat server.pid))"
    echo "  السجلات: tail -f server.log"
    echo "  الإيقاف: ./stop.sh"
else
    echo "✗ فشل التشغيل — راجع server.log"
    rm -f server.pid
    exit 1
fi
