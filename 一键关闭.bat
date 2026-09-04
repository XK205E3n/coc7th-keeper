@echo off
rem 跑团 Web 平台 · 一键关闭（M8R8）
rem 行为：委托 M8R4 已实测的 stop-web.ps1 —— 按 data\.run\*.pid 树杀后端/穿透/Vite，
rem       缺失 pid 时按命令行兜底过滤（只杀本项目相关进程，不无差别杀 python/node），幂等。
>nul chcp 65001
title 跑团平台 · 一键关闭
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-web.ps1"
echo.
echo [提示] 关闭完成。日志保留在 data\.run\，网址下次开启后可能变化属正常现象。
"%CD%\.venv\Scripts\python.exe" tools\print_urls.py 2>nul
pause
endlocal
