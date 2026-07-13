#!/bin/bash
# ============================================================
#  毎朝8:00 の一括処理を登録（ダウンロード→分析→図面）
#  ダブルクリックで登録。既存の com.reins.daily を置き換えます。
# ============================================================
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.reins.daily.plist"
HOUR=8
MIN=0

echo "=== REINS 毎朝一括処理の登録 (Mac) ==="
echo "フォルダ  : $DIR"
echo "実行時刻  : 毎日 ${HOUR}:0${MIN}"
echo "実行内容  : daily_all.command（DL→分析→図面）"
echo ""

mkdir -p "$HOME/Library/LaunchAgents" "$DIR/logs"
chmod +x "$DIR/daily_all.command"

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.reins.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${DIR}/daily_all.command</string>
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

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✅ 登録しました。毎日 ${HOUR}:0${MIN} に『DL→分析→図面』を自動実行します。"
echo "   （図面取得は config.yaml の zumen.enabled: true のときだけ動きます）"
echo "   解除は uninstall_schedule_mac.command をダブルクリック。"
echo ""
read -p "Enterキーで閉じます…"
