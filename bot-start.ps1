<#
.SYNOPSIS
  一键启动飞书跑团机器人（dsh-lark 桥接），后台常驻。

.DESCRIPTION
  - 后台隐藏窗口启动 dsh --profile dsh-lark（飞书 WebSocket 桥接），关闭本窗口不影响运行
  - 自动固定 DSH_HOME 到 ~/.dsh（绕开 DSH Desktop 向子进程注入的 home，见 .dsh\bin\dsh.cmd 注释）
  - 启动后自动健康检查：最多等 30 秒出现 "ws client ready"
  - 日志写入 .dsh\bin\dsh-stdout.log / dsh-stderr.log（每次启动轮转为 *.prev）

.USAGE
  双击「一键开启.bat」，或在 PowerShell 运行：
  .\bot-start.ps1             启动（已在运行则跳过，直接显示状态）
  .\bot-start.ps1 -Restart    强制重启
  .\bot-stop.ps1              停止机器人（或 .\bot-start.ps1 -Stop）

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File "D:\DeepSeek Harness\跑团\bot-start.ps1"
#>
param(
    [switch]$Restart,
    [switch]$Stop,
    [switch]$Status
)

# 让 PowerShell 主机输出走 UTF-8（解决 Windows 中文控制台 GBK 乱码）
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$BinDir      = Join-Path $ProjectRoot '.dsh\bin'
$DefaultDshBin = Join-Path $env:LOCALAPPDATA 'Programs\DSH Desktop\resources\app\node_modules\@deepseek-ai\dsh\lib\bin.js'

# 优先使用 PATH 上的 dsh（如果有，但是必须是 .js，不能是 .cmd —— node 会拒绝把 .cmd 当 JS 执行）；
# 否则回退到 DSH Desktop 自带的 bin.js
$DshBin = $null
$cmd = Get-Command dsh -ErrorAction SilentlyContinue
if ($cmd -and $cmd.Source -and $cmd.Source -like '*.js') { $DshBin = $cmd.Source }
if (-not $DshBin -and (Test-Path $DefaultDshBin)) { $DshBin = $DefaultDshBin }

$DshHome     = Join-Path $env:USERPROFILE '.dsh'
$LarkHome    = Join-Path $env:USERPROFILE '.dsh-lark'
$Heartbeat   = Join-Path $LarkHome 'profiles\default\guardian\heartbeat.json'
$GuardianDir = Join-Path $LarkHome 'guardian'
$LogOut      = Join-Path $BinDir 'dsh-stdout.log'
$LogErr      = Join-Path $BinDir 'dsh-stderr.log'

# 关键：DSH Desktop 会向子进程注入 DSH_HOME=...\dsh-desktop\harness，那里没有
# dsh-lark profile（会报 profile does not exist），必须固定到用户级 ~/.dsh
$env:DSH_HOME = $DshHome
$env:DSH_PERMISSION_MODE = 'workspace-write'

# 把 dsh-lark 的 agent 工作区锁定到本项目根目录。
# 这样 Agent 会话加载的 skill 是本工作区内的 .dsh\skills\coc7th-keeper\，
# 所有 python 脚本调用都走 .dsh\bin\coc.cmd wrapper —— 路径完全在 workspace 内，
# 不会再出现 "C:\Users\xingk\..." 跨工作区写，DSH workspace-write 自动放行。
$env:DSH_LARK_WORKSPACE = $ProjectRoot

# --- 解析 node ---
$Node = 'C:\Program Files\nodejs\node.exe'
if (-not (Test-Path $Node)) {
    $cmd = Get-Command node -ErrorAction SilentlyContinue
    if ($cmd) { $Node = $cmd.Source }
}
if (-not (Test-Path $Node)) { throw '找不到 node.exe，请先安装 Node.js >= 22' }
if (-not (Test-Path $DshBin)) { throw "找不到 DSH CLI：$DshBin" }

function Get-BridgePid {
    if (Test-Path $Heartbeat) {
        try {
            $hb = Get-Content $Heartbeat -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($hb.pid -and (Get-Process -Id $hb.pid -ErrorAction SilentlyContinue)) {
                return [int]$hb.pid
            }
        } catch { }
    }
    return $null
}

function Stop-Bridge {
    $bp = Get-BridgePid
    if ($bp) {
        Write-Host "停止现有机器人进程 (PID $bp)..."
        Stop-Process -Id $bp -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    } else {
        Write-Host '没有正在运行的机器人进程。'
    }
}

if ($Stop) {
    Stop-Bridge
    Write-Host '✅ 机器人已停止。'
    exit 0
}

if ($Status) {
    $bp = Get-BridgePid
    if ($bp) {
        Write-Host "✅ 机器人正在运行（PID $bp）"
        Write-Host "   日志：$LogOut / $LogErr"
        Write-Host "   停止：.\bot-stop.ps1（或双击「一键关闭.bat」）"
    } else {
        Write-Host 'ℹ️  机器人当前未运行。'
        Write-Host '   启动：.\bot-start.ps1（或双击「一键开启.bat」）'
    }
    exit 0
}

$existing = Get-BridgePid
if ($existing -and -not $Restart) {
    Write-Host "✅ 机器人已在运行 (PID $existing)，本次跳过启动。"
    Write-Host '   重启用：.\bot-start.ps1 -Restart    停止用：.\bot-stop.ps1'
    exit 0
}
if ($Restart) { Stop-Bridge }

# --- 启动（隐藏窗口的独立进程；stdout/stderr 落盘）
foreach ($f in @($LogOut, $LogErr)) {
    if (Test-Path $f) { Move-Item -Force $f "$f.prev" -ErrorAction SilentlyContinue }
}
$proc = Start-Process -FilePath $Node -ArgumentList "`"$DshBin`" --profile dsh-lark" `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $LogOut -RedirectStandardError $LogErr
Write-Host "启动中... PID $($proc.Id)（飞书 WebSocket 连接约需 5-15 秒）"

# --- 健康检查：等 "ws client ready"
$ready = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 2
    if ($proc.HasExited) { break }
    foreach ($log in @($LogOut, $LogErr)) {
        if ((Test-Path $log) -and (Select-String -Path $log -Pattern 'ws client ready' -Quiet)) {
            $ready = $true; break
        }
    }
    if ($ready) { break }
}

if (-not $ready) {
    if ($proc.HasExited) {
        Write-Host '❌ 启动失败，stderr 最后 12 行：'
        Get-Content $LogErr -Tail 12 -ErrorAction SilentlyContinue
    } else {
        Write-Host "⚠️ 进程在运行 (PID $($proc.Id)) 但 30 秒内未出现 ws client ready。"
        Write-Host "   请稍后查看日志：$LogOut 和 $LogErr"
    }
    exit 1
}

# --- 摘要
$notifyUrl = ''
if (Test-Path $LogErr) {
    $m = Select-String -Path $LogErr -Pattern '"url":"([^"]+)"' | Select-Object -Last 1
    if ($m) { $notifyUrl = $m.Matches[0].Groups[1].Value }
}
Write-Host ''
Write-Host '✅ 飞书机器人已就绪（后台常驻，可关闭本窗口）'
Write-Host "   进程 PID ：$($proc.Id)"
if ($notifyUrl) { Write-Host "   通知地址 ：$notifyUrl" }
Write-Host "   运行日志 ：$LogOut / $LogErr"
Write-Host '   停止     ：.\bot-stop.ps1（或双击「一键关闭.bat」）'
if (-not (Test-Path $GuardianDir)) {
    Write-Host ''
    Write-Host '💡 可选：安装崩溃自愈守护（机器人挂掉自动拉起）'
    Write-Host '   npx dsh-lark-bot@latest guardian install'
}