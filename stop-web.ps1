# 跑团 Web 平台 · 一键关闭（Windows PowerShell，M8R4）
# 用法：.\stop-web.ps1
# 行为：按 data/.run/*.pid 树杀（taskkill /T /F），并对缺失/失效的 pid 做命令行兜底过滤；
#       只杀本项目后端（server\main.py）、穿透二进制（cloudflared/frpc/cpolar）、Vite，
#       绝不无差别杀所有 python / node。重复执行幂等（无进程时打印「无运行中进程」）。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$RunDir = Join-Path $Root "data\.run"

$killed = 0
$pidFiles = @()

if (Test-Path $RunDir) {
    $pidFiles = @(Get-ChildItem $RunDir -Filter *.pid -ErrorAction SilentlyContinue)
}

# 杀进程助手：先确认进程存在再杀（避免 PS5.1 下 taskkill 对已死进程的
# stderr 报错在 $ErrorActionPreference=Stop 时刷 NativeCommandError 红字）。
function Stop-ProcTree {
    param([int]$TargetPid)
    if (-not (Get-Process -Id $TargetPid -ErrorAction SilentlyContinue)) { return }
    try { taskkill /PID $TargetPid /T /F 2>$null } catch { }
    if ($LASTEXITCODE -eq 0) { $script:killed++ }
}

# 1) 按 pid 文件树杀
#    注意：不能用 $pid —— 那是 PowerShell 自动变量（当前进程 ID），会被覆盖。
foreach ($f in $pidFiles) {
    $procId = [int](Get-Content $f.FullName -ErrorAction SilentlyContinue)
    if ($procId -gt 0) {
        Stop-ProcTree -TargetPid $procId
    }
    Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
}

# 2) 兜底：命令行过滤（只杀本项目相关进程）
#    vite 条件额外要求命令行含本项目根目录，避免误杀别的项目里的 vite 进程。
$fallback = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    ($_.CommandLine -like '*server\main.py*') -or
    ($_.CommandLine -like '*server/main.py*') -or
    ($_.Name -in @('cloudflared.exe', 'frpc.exe', 'cpolar.exe')) -or
    ($_.CommandLine -like '*vite*' -and $_.CommandLine -like "*$Root*")
}
foreach ($proc in $fallback) {
    Stop-ProcTree -TargetPid $proc.ProcessId
}

# 3) 清理残留 pid 文件（日志保留）
if (Test-Path $RunDir) {
    Get-ChildItem $RunDir -Filter *.pid -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
}

if ($killed -eq 0) {
    Write-Host "[停止] 无运行中进程。" -ForegroundColor Green
} else {
    Write-Host "[停止] 已关闭 $killed 个进程（后端 / 穿透 / Vite），pid 文件已清空，日志保留在 data/.run/。" -ForegroundColor Green
}
