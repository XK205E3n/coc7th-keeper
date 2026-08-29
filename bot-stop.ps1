<#
.SYNOPSIS
  一键关闭飞书跑团机器人（dsh-lark 桥接）。

.USAGE
  双击「一键关闭.bat」，或在 PowerShell 运行：.\bot-stop.ps1 [-Status]

.NOTES
  通过 ~/.dsh-lark 的心跳文件定位机器人进程（心跳由桥接进程持续刷新），
  停止后自动确认进程已退出。
#>
param(
    [switch]$Status
)

# 让 PowerShell 主机输出走 UTF-8（解决 Windows 中文控制台 GBK 乱码）
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

$ErrorActionPreference = 'SilentlyContinue'
$Heartbeat = Join-Path $env:USERPROFILE '.dsh-lark\profiles\default\guardian\heartbeat.json'

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

$bp = Get-BridgePid

if ($Status) {
    if ($bp) {
        Write-Host "✅ 机器人正在运行（PID $bp）"
        exit 0
    } else {
        Write-Host 'ℹ️  机器人当前未运行。'
        exit 0
    }
}

if (-not $bp) {
    Write-Host 'ℹ️  机器人当前没有在运行，无需关闭。'
    Write-Host '   启动用：.\bot-start.ps1（或双击「一键开启.bat」）'
    exit 0
}

Write-Host "停止机器人进程 (PID $bp)..."
Stop-Process -Id $bp -Force
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    if (-not (Get-Process -Id $bp -ErrorAction SilentlyContinue)) { break }
}

if (Get-Process -Id $bp -ErrorAction SilentlyContinue) {
    Write-Host "⚠️  进程未在 10 秒内退出，请在任务管理器中手动结束 PID $bp。"
    exit 1
}

Write-Host '✅ 机器人已关闭。'
Write-Host '   重新开启：.\bot-start.ps1（或双击「一键开启.bat」）'
exit 0