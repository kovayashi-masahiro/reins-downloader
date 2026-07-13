#!/bin/bash
# Mac用セットアップ（ダブルクリックで実行）
cd "$(dirname "$0")"
echo "=== REINS自動ダウンロード セットアップ (Mac) ==="
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
echo ""
echo "セットアップ完了。"
echo "次に config.example.yaml を config.yaml にコピーしてログイン情報を入力してください。"
read -p "Enterキーで閉じます…"
