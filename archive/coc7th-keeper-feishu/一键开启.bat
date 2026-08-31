@echo off
rem ============================================================
rem  yijian-kaiqi.bat -- Double-click launcher for the Feishu TRPG bot.
rem
rem  Behavior:
rem    1) Switch console to UTF-8 (avoid Chinese mojibake)
rem    2) Verify bot-start.ps1 and PowerShell both exist
rem    3) Forward the exit code from PowerShell to caller
rem    4) On error: clear Chinese message + keep window open (pause)
rem
rem  Usage:
rem    yijian-kaiqi.bat             start (skip if already running)
rem    yijian-kaiqi.bat restart     force restart
rem    yijian-kaiqi.bat stop        stop only
rem    yijian-kaiqi.bat status      show current status
rem
rem  Note: This file intentionally uses only ASCII parentheses () and
rem  no full-width Chinese parens () -- cmd.exe's parser breaks on
rem  multi-byte parens, treating them as command boundaries.
rem ============================================================

setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%bot-start.ps1"

rem --- 0) Verify PowerShell in PATH ---
where powershell >nul 2>&1
if errorlevel 1 (
    echo [ERROR] powershell.exe not found in PATH.
    echo         Install PowerShell: https://aka.ms/powershell
    pause
    exit /b 1
)

rem --- 1) Verify bot-start.ps1 exists ---
if not exist "%PS_SCRIPT%" (
    echo [ERROR] Launcher script missing: %PS_SCRIPT%
    echo         Make sure yijian-kaiqi.bat and bot-start.ps1 are in the same directory.
    pause
    exit /b 1
)

rem --- 2) Forward args to PowerShell script (auto-prepend '-' for known switches) ---
title Feishu TRPG Bot - START
echo ============================================================
echo  Feishu TRPG Bot - launcher
echo  Workspace: %SCRIPT_DIR%
echo  Script:    %PS_SCRIPT%
echo ============================================================
echo.
set "PS_ARGS="
:argloop
if "%~1"=="" goto :argdone
set "ARG=%~1"
if /I "%ARG%"=="status"  set "PS_ARGS=%PS_ARGS% -Status"
if /I "%ARG%"=="restart" set "PS_ARGS=%PS_ARGS% -Restart"
if /I "%ARG%"=="stop"    set "PS_ARGS=%PS_ARGS% -Stop"
if /I not "%ARG%"=="status" if /I not "%ARG%"=="restart" if /I not "%ARG%"=="stop" set "PS_ARGS=%PS_ARGS% %~1"
shift
goto :argloop
:argdone
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %PS_ARGS%
set "RC=%errorlevel%"
echo.
if not "%RC%"=="0" (
    echo ------------------------------------------------------------
    echo  Launcher exit code: %RC% (non-zero means startup failed)
    echo  Check logs: .dsh\bin\dsh-stdout.log / .dsh\bin\dsh-stderr.log
    echo ------------------------------------------------------------
)
echo Closing this window does NOT stop the background bot (already detached).
pause
exit /b %RC%