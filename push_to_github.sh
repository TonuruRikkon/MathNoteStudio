#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "================================================================"
echo "  🚀 ĐẨY MATHNOTE STUDIO LÊN GITHUB & TỰ ĐỘNG BUILD FILE .EXE"
echo "================================================================"
echo ""
if [ -z "$1" ]; then
    read -rp "👉 Dán đường dẫn GitHub Repo của bạn (VD: https://github.com/ten-ban/MathNoteStudio.git): " REPO_URL
else
    REPO_URL="$1"
fi

if [ -z "$REPO_URL" ]; then
    echo "❌ Bạn chưa nhập đường dẫn GitHub Repo."
    exit 1
fi

git branch -M main
if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "$REPO_URL"
else
    git remote add origin "$REPO_URL"
fi

echo "⏳ Đang đẩy mã nguồn lên GitHub..."
git push -u origin main --force

echo ""
echo "✅ ĐÃ ĐẨY THÀNH CÔNG!"
echo "👉 Bây giờ bạn chỉ cần mở trang GitHub Repo vừa tạo:"
echo "   1. Bấm vào tab 'Actions' để xem GitHub tự động đóng gói MathNoteStudio.exe (~2 phút)."
echo "   2. Sau khi xong, vào mục 'Releases' ở góc phải trang GitHub để tải trực tiếp file MathNoteStudio.exe!"
