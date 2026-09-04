@echo off
rem 跑团 Web 平台 · 一键开启（M8R8）
rem 行为：幂等预检 -> 进站密码补设（未设时交互）-> start-web.ps1 -Tunnel
rem       （前端首次自动构建 + 后台后端 + 内网穿透）-> 命令行最下方打印可打开的网址。
rem 底层全部委托给 M8R4 已实测的 start-web.ps1，本文件不含启停逻辑。
>nul chcp 65001
title 跑团平台 · 一键开启
setlocal
cd /d "%~dp0"
set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [错误] 未找到虚拟环境 .venv。
    echo 请先完成一次性安装（详见 docs\单人测试一键开团手册-20260904.md 第 0 步）：
    echo   python -m venv .venv
    echo   .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)

rem 幂等：后端已在运行时不盲目重复拉起，交给用户选择（防止旧代码遗留服务被误用）
"%PY%" tools\print_urls.py check >nul 2>&1
if not errorlevel 1 (
    "%PY%" tools\print_urls.py
    echo.
    choice /c RE /n /m "[提示] 检测到后端已在运行。按 R = 重启到最新代码（先关闭再开启）；按 E = 直接沿用当前服务："
    if not errorlevel 2 (
        echo.
        echo [重启] 先关闭现有服务...
        powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-web.ps1"
        echo.
    ) else (
        echo.
        echo [提示] 沿用当前服务。如之后发现功能异常，请双击「一键关闭.bat」后重新开启。
        pause
        exit /b 0
    )
)

rem 公网测试建议设置进站密码（已设置则自动跳过；直接回车可跳过不设）
"%PY%" tools\config_cli.py ensure-access-password
echo.

echo [1/2] 启动后端与前端（首次自动 npm install + build），并建立内网穿透...
echo       （公网地址一般需 10-30 秒，请耐心等待）
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-web.ps1" -Tunnel

echo.
echo [2/2] 汇总可打开的网址：
"%PY%" tools\print_urls.py
echo.
echo （保持本窗口开启即可，关闭服务请双击「一键关闭.bat」；本窗口可以直接最小化）
pause
endlocal
