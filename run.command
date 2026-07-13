#!/bin/bash
# Mac用：クリック一つで実行（エラー表示・実行完了待機対応）
cd "$(dirname "$0")" || exit 1

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "REINS 新着・更新物件ダウンロード"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 環境確認
if ! command -v python3 &> /dev/null; then
    echo "❌ エラー: Python3 が見つかりません"
    echo "インストールしてください: https://www.python.org"
    read -p "Enterを押して終了..."
    exit 1
fi

if [ ! -f "reins_downloader.py" ]; then
    echo "❌ エラー: reins_downloader.py が見つかりません"
    read -p "Enterを押して終了..."
    exit 1
fi

echo "実行中..."
echo ""

# メイン実行
if python3 reins_downloader.py; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ 完了しました"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "出力ファイル: downloads/ フォルダを確認してください"
else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "❌ エラーが発生しました"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "詳細は logs/ フォルダを確認してください"
fi

echo ""
read -p "Enterを押して終了..."
