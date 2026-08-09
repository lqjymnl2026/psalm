#!/bin/bash
# 赞美诗资料智能整理中心 · 启动脚本
# 用法：./run.sh           仅本机访问
#       ./run.sh --lan     局域网模式（手机可访问）
cd "$(dirname "$0")"

if [ "$1" = "--lan" ] || [ "$1" = "-l" ]; then
  export HOST="0.0.0.0"
  echo "📱 局域网模式已开启：手机与本机连同一 WiFi 后，打开启动信息中的 http://<本机IP>:8787"
fi

# 1) 优先使用 Codex 自带 Python 运行时（含 openpyxl/pdfplumber/docx/reportlab 等）
PY=""
for cand in \
  "/Users/macbook/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" \
  $(ls -d "$HOME"/.cache/codex-runtimes/*/dependencies/python/bin/python3 2>/dev/null | tail -n 1); do
  if [ -n "$cand" ] && [ -x "$cand" ]; then PY="$cand"; break; fi
done
[ -z "$PY" ] && PY="python3"

# 2) 检查依赖
if ! "$PY" -c "import openpyxl, pdfplumber, docx, reportlab, zhconv, pypdf" >/dev/null 2>&1; then
  echo ""
  echo "⚠️  缺少必要依赖库（openpyxl / pdfplumber / python-docx / reportlab / zhconv / pypdf）。"
  echo "   请安装后重试："
  echo "   pip3 install openpyxl pdfplumber python-docx reportlab zhconv pypdf"
  echo ""
  read -n 1 -s -r -p "按任意键关闭…"
  exit 1
fi

echo "使用 Python: $("$PY" --version)"
echo "启动中…"
exec "$PY" app.py
