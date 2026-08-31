# 跑团 Web 平台 · 一键启动（Windows PowerShell，M6.3）
# 用法：
#   .\start-web.ps1            # 构建前端（首次自动）并启动后端（http://localhost:18000）
#   .\start-web.ps1 -Dev       # 开发模式：后端 + Vite dev server（http://localhost:5173）
param(
    [switch]$Dev
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "[错误] 未找到虚拟环境，请先执行：" -ForegroundColor Red
    Write-Host "  python -m venv .venv"
    Write-Host "  .venv\Scripts\python -m pip install fastapi uvicorn[standard] openai httpx"
    exit 1
}

$Dist = Join-Path $Root "frontend\dist\index.html"
if (-not (Test-Path $Dist)) {
    Write-Host "[首次启动] 构建前端静态产物..."
    Push-Location (Join-Path $Root "frontend")
    npm install
    if ($LASTEXITCODE -ne 0) { Write-Host "[错误] npm install 失败"; exit 1 }
    npm run build
    if ($LASTEXITCODE -ne 0) { Write-Host "[错误] 前端构建失败"; exit 1 }
    Pop-Location
}

if ($Dev) {
    # 开发模式：后端 + Vite dev server（后端静态挂载与 vite 并存，建议经 5173 访问）
    $server = Start-Process -FilePath $Py -ArgumentList "server\main.py" -WorkingDirectory $Root -PassThru -WindowStyle Hidden
    Write-Host "[后端] PID $($server.Id)  http://localhost:18000"
    Push-Location (Join-Path $Root "frontend")
    npm run dev
    Pop-Location
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "[启动] http://localhost:18000  （Ctrl+C 退出）"
    & $Py server\main.py
}
