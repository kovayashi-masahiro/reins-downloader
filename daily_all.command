#!/bin/bash
# ============================================================
#  毎朝の一括処理（ダブルクリックでも手動実行可）
#   1) REINS 新着・更新物件のダウンロード
#   2) 分析 → Google スプレッドシート（抽出物件／エリア統計）
#   3) 図面PDF取得（config.yaml の zumen.enabled: true のときのみ）
# ============================================================
cd "$(dirname "$0")" || exit 1
PY="$(command -v python3 || echo /usr/bin/python3)"
ANALYZE_DIR="../reins自動分析"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " REINS 毎朝の一括処理  $(date '+%Y-%m-%d %H:%M')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "[1/3] 新着・更新物件のダウンロード"
"$PY" reins_downloader.py || echo "  ⚠ ダウンロードでエラー（続行します）"

echo ""
echo "[2/3] 分析 → スプレッドシート記録"
"$PY" "$ANALYZE_DIR/analyze.py" || echo "  ⚠ 分析でエラー（続行します）"

echo ""
echo "[3/3] 図面PDF取得（有効時のみ）"
"$PY" zumen_download.py || echo "  ⚠ 図面取得でエラー"

echo ""
echo "✅ 一括処理おわり"
# ダブルクリック実行時に窓を残す（launchd実行時は無視される）
[ -t 1 ] && read -p "Enterで閉じます…"
