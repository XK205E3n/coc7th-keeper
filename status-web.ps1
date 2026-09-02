# 跑团 Web 平台 · 状态查询（Windows PowerShell，M8R4）
# 用法：.\status-web.ps1
# 读取 data/.run/*.pid，打印后端 / 穿透存活状态、本地与公网地址、日志路径。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$RunDir = Join-Path $Root "data\.run"

function Test-PidAlive {
    param([string]$PidFile)
    if (-not (Test-Path $PidFile)) { return $null }
    $pid = [int](Get-Content $PidFile -ErrorAction SilentlyContinue)
    if (-not $pid) { return $null }
    try {
        $p = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($p) { return $pid }
    } catch {}
    return $false   # pid 文件存在但进程已死
}

$cj = $null
try { $cj = (Get-Content (Join-Path $Root "data\config.json") -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json) } catch {}

$port = if ($cj -and $cj.server.port) { $cj.server.port } else { 18000 }
$share = if ($cj -and $cj.share_url) { $cj.share_url } else { "(未设置)" }

Write-Host "===== 跑团 Web 平台状态 =====" -ForegroundColor Cyan
$be = Test-PidAlive (Join-Path $RunDir "backend.pid")
if ($be -eq $null) { Write-Host "后端     ：未运行（无 pid 文件）" }
elseif ($be -eq $false) { Write-Host "后端     ：pid 文件存在但进程已退出（建议 .\stop-web.ps1 清理）" -ForegroundColor Yellow }
else { Write-Host "后端     ：运行中 PID $be  → http://localhost:$port" -ForegroundColor Green }

$tu = Test-PidAlive (Join-Path $RunDir "tunnel.pid")
if ($tu -eq $null) { Write-Host "穿透     ：未运行（无 pid 文件）" }
elseif ($tu -eq $false) { Write-Host "穿透     ：pid 文件存在但进程已退出" -ForegroundColor Yellow }
else { Write-Host "穿透     ：运行中 PID $tu" -ForegroundColor Green }

Write-Host "本地地址 ：http://localhost:$port"
Write-Host "公网地址 ：$share"
Write-Host "日志目录 ：data/.run/  (backend.log / tunnel.log / *.err)"
Write-Host "关闭命令 ：.\stop-web.ps1"
Write-Host "===========================" -ForegroundColor Cyan
