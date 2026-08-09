#!/bin/bash
# ============================================================
# 一键推送到 GitHub（lqjymnl2026/psalm）
# 用法：在你的【终端】里运行  ./推送脚本.sh
# 首次需要先登录一次：gh auth login（见下方说明）
# ============================================================
set -e
cd "$(dirname "$0")"

# 1) 找到 gh
GH=""
for cand in "$(command -v gh 2>/dev/null)" "/Users/macbook/bin/gh"; do
  if [ -n "$cand" ] && [ -x "$cand" ]; then GH="$cand"; break; fi
done

if [ -z "$GH" ]; then
  echo "❌ 未找到 GitHub CLI (gh)。请先安装："
  echo "   brew install gh"
  echo "   或去 https://github.com/cli/cli/releases 下载"
  exit 1
fi

# 2) 检查登录状态
if ! "$GH" auth status -h github.com >/dev/null 2>&1; then
  echo "❌ gh 尚未登录或令牌已失效。请先在你的终端运行："
  echo ""
  echo "   $GH auth login -h github.com"
  echo ""
  echo "   然后按提示选择：GitHub.com → HTTPS → 用浏览器登录并授权"
  echo "   完成后再重新运行本脚本。"
  exit 1
fi
echo "✅ gh 已登录：$("$GH" auth status -h github.com 2>&1 | grep -o 'account [a-zA-Z0-9_-]*' | head -1)"

# 3) 确保 git 使用 gh 作为凭据助手
"$GH" auth setup-git 2>/dev/null || true

# 4) 配置 remote 并推送
if ! git remote | grep -q origin; then
  git remote add origin https://github.com/lqjymnl2026/psalm.git
fi
git remote set-url origin https://github.com/lqjymnl2026/psalm.git
git branch -M main
git add -A
git commit -m "feat: 赞美诗资料智能整理中心 v1.1（手机端收集 + 拍照OCR识别自动填表）" || echo "（没有新改动，跳过提交）"
git push -u origin main

echo ""
echo "✅ 已推送到 https://github.com/lqjymnl2026/psalm"
echo "   仓库为公开仓库；如需隐藏数据请改为 Private："
echo "   GitHub → Settings → General → Danger Zone → Change repository visibility"
