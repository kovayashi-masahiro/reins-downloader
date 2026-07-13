#!/bin/bash
# Mac 毎日自動実行の解除（ダブルクリック）
PLIST="$HOME/Library/LaunchAgents/com.reins.daily.plist"
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✅ 毎日自動実行を解除しました。"
read -p "Enterキーで閉じます…"
