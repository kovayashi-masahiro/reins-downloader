@echo off
chcp 65001 >nul
REM Windows 毎日自動実行の解除（管理者として実行）
schtasks /delete /tn "REINS自動DL" /f
echo ✅ 毎日自動実行を解除しました。
pause
