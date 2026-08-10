#!/bin/bash
# ============================================================
# 从当前项目生成一套新的独立实例（空白数据、独立端口，可与现有实例同时运行）
# 用法: ./生成新实例.sh [实例名] [端口]
#   例: ./生成新实例.sh hymn-center-2 8788
# ============================================================
set -e
cd "$(dirname "$0")"
NAME="${1:-hymn-center-2}"
PORT="${2:-8788}"
TARGET="../$NAME"

if [ -d "$TARGET" ]; then
  echo "❌ 目标已存在：$TARGET"
  exit 1
fi

echo "正在生成新实例 → $TARGET （端口 $PORT）"
mkdir -p "$TARGET"
# 复制代码（不含数据/凭据/git）
cp -R app.py engine.py parsers.py exporters.py seed.py run.sh README.md \
      static samples tools "$TARGET/" 2>/dev/null
# OCR 模型
mkdir -p "$TARGET/data/tessdata"
cp -R data/tessdata/. "$TARGET/data/tessdata/" 2>/dev/null || true
# 空白数据库（seeded=true 表示不自动灌示例数据）
mkdir -p "$TARGET/data/uploads" "$TARGET/data/exports"
echo '{"songs": [], "seq": 0, "imports": [], "exports": [], "settings": {}, "seeded": true}' > "$TARGET/data/db.json"
touch "$TARGET/data/uploads/.gitkeep" "$TARGET/data/exports/.gitkeep"
# 生成该实例专用的启动脚本
cat > "$TARGET/启动-本实例.command" <<EOG
#!/bin/bash
cd "\$(dirname "\$0")"
export HOST="0.0.0.0"
export PORT="$PORT"
exec ./run.sh
EOG
chmod +x "$TARGET/启动-本实例.command"
chmod +x "$TARGET/run.sh" 2>/dev/null || true

echo ""
echo "✅ 新实例已生成：$TARGET"
echo "   启动：cd $TARGET && ./启动-本实例.command"
echo "   或：cd $TARGET && PORT=$PORT HOST=0.0.0.0 python3 app.py"
echo "   访问：http://127.0.0.1:$PORT（本机） / http://<本机IP>:$PORT（手机同一WiFi）"
