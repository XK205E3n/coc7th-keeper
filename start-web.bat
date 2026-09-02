@echo off
rem 跑团 Web 平台 · 一键启动（Windows cmd，M8R4）
rem 用法：start-web.bat               构建前端（首次自动）并前台启动后端 http://localhost:18000
rem       start-web.bat -dev         开发模式：后端 + Vite dev server http://localhost:5173
rem       start-web.bat -daemon      后台起后端（无穿透），打印 PID 后退出
rem       start-web.bat -tunnel       后台：后端 + 内网穿透，抓公网 URL 写 share_url 后退出
rem       start-web.bat -tunnel -provider mock   用 mock provider 演练（不启真进程）
rem       start-web.bat -tunnel -force           跳过 access_password 安全确认
rem 注：-daemon / -tunnel 逻辑由 start-web.ps1 实现，此处委派以保证行为一致。
>nul chcp 65001
setlocal
cd /d "%~dp0"

set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [错误] 未找到虚拟环境，请先执行：
    echo   python -m venv .venv
    echo   .venv\Scripts\python -m pip install fastapi "uvicorn[standard]" openai httpx
    exit /b 1
)

if "%1"=="-daemon" (
    powershell -ExecutionPolicy Bypass -File "%~dp0start-web.ps1" -Daemon
    exit /b %ERRORLEVEL%
)
if "%1"=="-tunnel" (
    set "ARGS=-Tunnel"
    if "%2"=="-provider" set "ARGS=-Tunnel -Provider %3"
    if "%2"=="-force" set "ARGS=-Tunnel -Force"
    if "%3"=="-force" set "ARGS=%ARGS% -Force"
    powershell -ExecutionPolicy Bypass -File "%~dp0start-web.ps1" %ARGS%
    exit /b %ERRORLEVEL%
)

if not exist "frontend\dist\index.html" (
    echo [首次启动] 构建前端静态产物...
    pushd frontend
    call npm install
    if errorlevel 1 ( echo [错误] npm install 失败 & popd & exit /b 1 )
    call npm run build
    if errorlevel 1 ( echo [错误] 前端构建失败 & popd & exit /b 1 )
    popd
)

if "%1"=="-dev" (
    echo [启动] 开发模式：后端 18000 + Vite 5173
    start "跑团后端" /min "%PY%" server\main.py
    pushd frontend
    call npm run dev
    popd
) else (
    echo [启动] http://localhost:18000  （Ctrl+C 退出）
    "%PY%" server\main.py
)
endlocal
