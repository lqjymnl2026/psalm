#!/bin/bash
# 推送到 GitHub（仓库 lqjymnl2026/psalm）。首次需要认证一次：
#   方式A（推荐）：brew install gh && gh auth login
#   方式B：GitHub → Settings → Developer settings → Personal access tokens → 生成 token
#         然后运行：git remote set-url origin https://<USER>:<TOKEN>@github.com/lqjymnl2026/psalm.git
set -e
cd "$(dirname "$0")"
if ! git remote | grep -q origin; then
  git remote add origin https://github.com/lqjymnl2026/psalm.git
fi
git branch -M main
git add -A
git commit -m "feat: 赞美诗资料智能整理中心 v1.0（6页工作流 + 导入/分类/去重/导出）" || echo "（没有新改动，跳过提交）"
git push -u origin main
echo ""
echo "✅ 已推送到 https://github.com/lqjymnl2026/psalm"
