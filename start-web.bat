@echo off
rem 跑团 Web 平台 · 一键启动（Windows cmd，M6.3）
rem 用法：start-web.bat        构建前端（首次自动）并启动后端 http://localhost:18000
rem       start-web.bat -dev   开发模式：后端 + Vite dev server http://localhost:5173
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
