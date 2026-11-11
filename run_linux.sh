#!/usr/bin/env bash
cd "$(dirname "$0")"
if ! python3 -c "import PySide6" >/dev/null 2>&1; then
    echo "[MathNote Studio] Đang cài đặt thư viện cần thiết cho lần chạy đầu tiên..."
    pip install -r requirements.txt --break-system-packages 2>/dev/null || pip install -r requirements.txt
fi
exec python3 main.py "$@"
