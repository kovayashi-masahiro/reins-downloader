@echo off
chcp 65001 >nul
REM Windows用セットアップ（ダブルクリックで実行）
cd /d "%~dp0"
echo === REINS自動ダウンロード セットアップ (Windows) ===
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
echo.
echo セットアップ完了。
echo 次に config.example.yaml を config.yaml にコピーしてログイン情報を入力してください。
pause
