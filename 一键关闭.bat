@echo off
rem ============================================================
rem  yijian-guanbi.bat -- Double-click stopper for the Feishu TRPG bot.
rem
rem  Behavior:
rem    1) Switch console to UTF-8 (avoid Chinese mojibake)
rem    2) Verify bot-stop.ps1 and PowerShell both exist
rem    3) Forward the exit code from PowerShell to caller
rem    4) On error: clear Chinese message + keep window open (pause)
rem
rem  Usage:
rem    yijian-guanbi.bat             stop (no-op if not running)
rem    yijian-guanbi.bat status      show status
rem
rem  Note: Only ASCII parentheses () used -- cmd.exe's parser breaks
rem  on full-width Chinese parens.
rem ============================================================

setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%bot-stop.ps1"

rem --- 0) Verify PowerShell in PATH ---
where powershell >nul 2>&1
if errorlevel 1 (
    echo [ERROR] powershell.exe not found in PATH.
    echo         Install PowerShell: https://aka.ms/powershell
    pause
    exit /b 1
)

rem --- 1) Verify bot-stop.ps1 exists ---
if not exist "%PS_SCRIPT%" (
    echo [ERROR] Stopper script missing: %PS_SCRIPT%
    echo         Make sure yijian-guanbi.bat and bot-stop.ps1 are in the same directory.
    pause
    exit /b 1
)

rem --- 2) Forward args to PowerShell script (auto-prepend '-' for known switches) ---
title Feishu TRPG Bot - STOP
echo ============================================================
echo  Feishu TRPG Bot - stopper
echo  Workspace: %SCRIPT_DIR%
echo  Script:    %PS_SCRIPT%
echo ============================================================
echo.
set "PS_ARGS="
:argloop
if "%~1"=="" goto :argdone
set "ARG=%~1"
if /I "%ARG%"=="status"  set "PS_ARGS=%PS_ARGS% -Status"
if /I not "%ARG%"=="status" set "PS_ARGS=%PS_ARGS% %~1"
shift
goto :argloop
:argdone
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %PS_ARGS%
set "RC=%errorlevel%"
echo.
if not "%RC%"=="0" (
    echo ------------------------------------------------------------
    echo  Stopper exit code: %RC% (non-zero usually means process didn't exit within 10s)
    echo  Manually end the dsh --profile dsh-lark process via Task Manager if needed.
    echo ------------------------------------------------------------
)
pause
exit /b %RC%