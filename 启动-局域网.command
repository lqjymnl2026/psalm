#!/bin/bash
# 双击运行（局域网模式）：手机与 Mac 连同一 WiFi 后，用手机浏览器打开终端显示的地址即可收集诗歌
cd "$(dirname "$0")"
exec ./run.sh --lan
