#!/bin/bash
# 安装为 macOS 开机自启服务（登录后自动运行，崩了自动重启）
set -e
cd "$(dirname "$0")"
AGENT="$HOME/Library/LaunchAgents/com.hymncenter.server.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cp com.hymncenter.server.plist "$AGENT"
# 先停掉手动启动的服务（避免端口冲突）
launchctl bootout gui/$(id -u)/com.hymncenter.server 2>/dev/null || true
launchctl bootstrap gui/$(id -u) "$AGENT"
echo "✅ 已安装开机自启。"
echo "   管理：launchctl kickstart gui/$(id -u)/com.hymncenter.server   # 重启服务"
echo "         launchctl bootout gui/$(id -u)/com.hymncenter.server    # 卸载自启"
