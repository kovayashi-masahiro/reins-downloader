#!/bin/bash
# ============================================================
#  Mac 毎日自動実行インストーラ（ダブルクリックで登録）
#  毎日 朝8:00 に reins_downloader.py を実行します。
# ============================================================
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$(command -v python3 || echo /usr/bin/python3)"
PLIST="$HOME/Library/LaunchAgents/com.reins.daily.plist"
HOUR=8
MIN=0

echo "=== REINS自動DL 毎日実行の登録 (Mac) ==="
echo "フォルダ: $DIR"
echo "Python : $PYTHON"
echo "実行時刻: 毎日 ${HOUR}:0${MIN}"
echo ""

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$DIR/logs"

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.reins.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${DIR}/reins_downloader.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${DIR}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${HOUR}</integer>
        <key>Minute</key>
        <integer>${MIN}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${DIR}/logs/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>${DIR}/logs/launchd.err.log</string>
</dict>
</plist>
PLISTEOF

# 既存があれば解除してから登録
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✅ 登録しました。毎日 ${HOUR}:0${MIN} に自動実行されます。"
echo "   解除する場合は uninstall_schedule_mac.command をダブルクリックしてください。"
echo ""
read -p "Enterキーで閉じます…"
