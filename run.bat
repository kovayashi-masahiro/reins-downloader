@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo REINS 新着・更新物件ダウンロード
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

REM 環境確認
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ エラー: Python が見つかりません
    echo インストールしてください: https://www.python.org
    pause
    exit /b 1
)

if not exist "reins_downloader.py" (
    echo ❌ エラー: reins_downloader.py が見つかりません
    pause
    exit /b 1
)

echo 実行中...
echo.

REM メイン実行
python reins_downloader.py
if %errorlevel% equ 0 (
    echo.
    echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    echo ✅ 完了しました
    echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    echo 出力ファイル: downloads フォルダを確認してください
) else (
    echo.
    echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    echo ❌ エラーが発生しました
    echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    echo 詳細は logs フォルダを確認してください
)

echo.
pause
