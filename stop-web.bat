@echo off
rem 跑团 Web 平台 · 一键关闭（Windows cmd，M8R4）
rem 用法：stop-web.bat
rem 行为：按 data\.run\*.pid 树杀；缺失/失效时按命令行兜底（只杀本项目后端 / 穿透二进制 / Vite）。
rem       不无差别杀所有 python / node。重复执行幂等。
>nul chcp 65001
setlocal
cd /d "%~dp0"
set "RUN=%CD%\data\.run"
set KILLED=0

if exist "%RUN%\*.pid" (
    for /f "usebackq tokens=*" %%p in (`type "%RUN%\*.pid" 2^>nul`) do (
        taskkill /PID %%p /T /F 2>nul
        set /a KILLED+=1
    )
    del /q "%RUN%\*.pid" 2>nul
)

rem 兜底：按命令行 / 进程名过滤（只杀本项目相关）
for /f "usebackq tokens=2 delims==" %%P in (`wmic process where "CommandLine like '%%server\\main.py%%' or CommandLine like '%%server/main.py%%' or CommandLine like '%%vite%%' or Name='cloudflared.exe' or Name='frpc.exe' or Name='cpolar.exe'" get ProcessId /value 2^>nul ^| findstr ProcessId`) do (
    taskkill /PID %%P /T /F 2>nul
    set /a KILLED+=1
)

if "%KILLED%"=="0" (
    echo [停止] 无运行中进程。
) else (
    echo [停止] 已关闭 %KILLED% 个进程（后端 / 穿透 / Vite），pid 文件已清空，日志保留在 data\.run\。
)
endlocal
