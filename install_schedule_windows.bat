@echo off
chcp 65001 >nul
REM ============================================================
REM  Windows 毎日自動実行インストーラ
REM  ※「管理者として実行」で起動してください（右クリック→管理者として実行）
REM  毎日 朝8:00 に run.bat を実行します。
REM ============================================================
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 管理者権限が必要です。
    echo     このファイルを右クリックして「管理者として実行」で起動してください。
    echo.
    pause
    exit /b 1
)

echo === REINS自動DL 毎日実行の登録 (Windows) ===
echo フォルダ: %~dp0
echo 実行時刻: 毎日 08:00
echo.

schtasks /create /tn "REINS自動DL" /tr "\"%~dp0run.bat\"" /sc daily /st 08:00 /rl HIGHEST /f

if %errorlevel% equ 0 (
    echo.
    echo ✅ 登録しました。毎日 08:00 に自動実行されます。
    echo    解除する場合は uninstall_schedule_windows.bat を管理者として実行してください。
) else (
    echo.
    echo [!] 登録に失敗しました。管理者として実行されているかご確認ください。
)
echo.
pause
