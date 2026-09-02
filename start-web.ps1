# 跑团 Web 平台 · 一键启动（Windows PowerShell，M8R4）
# 用法：
#   .\start-web.ps1              # 前台阻塞启动（无穿透），行为与改造前完全一致
#   .\start-web.ps1 -Dev         # 开发模式：后端 + Vite dev server（http://localhost:5173）
#   .\start-web.ps1 -Daemon      # 后台起后端（无穿透），打印 PID 后退出
#   .\start-web.ps1 -Tunnel      # 后台：后端 + 内网穿透，抓公网 URL → 写 share_url → 打印 → 退出
#   .\start-web.ps1 -Tunnel -Provider mock   # 用 mock provider 演练（不启真进程）
#   .\start-web.ps1 -Tunnel -Force           # 跳过 access_password 安全确认
param(
    [switch]$Dev,
    [switch]$Daemon,
    [switch]$Tunnel,
    [switch]$Force,
    [string]$Provider = ""
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$RunDir   = Join-Path $Root "data\.run"
$BackendPid = Join-Path $RunDir "backend.pid"
$TunnelPid = Join-Path $RunDir "tunnel.pid"
$FrontendPid = Join-Path $RunDir "frontend.pid"
$BackendLog = Join-Path $RunDir "backend.log"
$TunnelLog  = Join-Path $RunDir "tunnel.log"
# stderr 必须单独成文件：Start-Process 拒绝把 -RedirectStandardOutput 与
# -RedirectStandardError 指向同一路径（InvalidOperationException: ...are same）。
# 穿透程序的公网地址常打在 stderr（如 cloudflared），故 Get-TunnelUrl 两个文件都要读。
$TunnelLogErr = "$TunnelLog.err"
$BackendLogErr = "$BackendLog.err"

function Ensure-Venv {
    $Py = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $Py)) {
        Write-Host "[错误] 未找到虚拟环境，请先执行：" -ForegroundColor Red
        Write-Host "  python -m venv .venv"
        Write-Host "  .venv\Scripts\python -m pip install fastapi uvicorn[standard] openai httpx"
        exit 1
    }
    return $Py
}

function Ensure-Dist {
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
}

function Get-ResolvedConfig {
    $code = @'
import sys, json
sys.path.insert(0, "server")
import config
print(json.dumps(config.load_config()))
'@
    $json = & $Py -c $code
    return $json | ConvertFrom-Json
}

function Set-ShareUrl {
    param([string]$url)
    $code = @'
import sys, json
sys.path.insert(0, "server")
import config
c = config.load_config()
c["share_url"] = sys.argv[1]
config.save_config(c)
print(c["share_url"])
'@
    & $Py -c $code $url
}

function Start-BackgroundCommand {
    param([string]$FilePath, [string]$Arguments, [string]$PidFile, [string]$LogFile)
    # 直接以二进制为 FilePath 启动（不使用 cmd.exe 包装，避免被安全策略拦截）
    # 注意：stdout 与 stderr 必须落到两个不同文件，同一路径会被 Start-Process 直接拒绝。
    $p = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $Root -PassThru -WindowStyle Hidden -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err"
    Set-Content -Path $PidFile -Value $p.Id -Encoding ASCII
    return $p
}

function Stop-Local {
    if (Test-Path $BackendPid) {
        $p = [int](Get-Content $BackendPid)
        taskkill /PID $p /T /F 2>$null
        Remove-Item $BackendPid -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $TunnelPid) {
        $p = [int](Get-Content $TunnelPid)
        taskkill /PID $p /T /F 2>$null
        Remove-Item $TunnelPid -Force -ErrorAction SilentlyContinue
    }
}

function Wait-BackendReady {
    $uri = "http://127.0.0.1:18000/api/health"
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $r = Invoke-RestMethod -Uri $uri -TimeoutSec 2
            if ($r.status -eq "ok") { return $true }
        } catch {}
        Start-Sleep -Seconds 1
    }
    return $false
}

function Start-Tunnel {
    param($cfg, $port, $ProviderOverride)
    $provider = if ($ProviderOverride) { $ProviderOverride } else { $cfg.tunnel.provider }
    $tc = $cfg.tunnel
    switch ($provider) {
        "cloudflared" {
            $bin = $tc.cloudflared.bin
            if (-not (Get-Command $bin -ErrorAction SilentlyContinue)) {
                Write-Host "[错误] 未找到穿透二进制 '$bin'。" -ForegroundColor Red
                Write-Host "  安装：winget install cloudflared 或 https://developers.cloudflare.com/cloudflared/" -ForegroundColor Yellow
                return @{Ok = $false; Reason = "missing:$bin" }
            }
            $args2 = "tunnel --url http://127.0.0.1:$port"
            if ($tc.cloudflared.tunnel_name) { $args2 += " --name $($tc.cloudflared.tunnel_name)" }
            $p = Start-BackgroundCommand -FilePath $bin -Arguments $args2 -PidFile $TunnelPid -LogFile $TunnelLog
            return @{Ok = $true; Process = $p; Url = $null }
        }
        "frp" {
            $bin = $tc.frp.bin
            if (-not (Get-Command $bin -ErrorAction SilentlyContinue)) {
                Write-Host "[错误] 未找到穿透二进制 '$bin'。" -ForegroundColor Red
                Write-Host "  安装：https://gofrp.org  （或 scoop install frpc）" -ForegroundColor Yellow
                return @{Ok = $false; Reason = "missing:$bin" }
            }
            $cfgPath = $tc.frp.config
            if (-not (Test-Path $cfgPath)) {
                Write-Host "[错误] 缺少 frp 配置 '$cfgPath'（参考 tools/frpc.toml 模板填写）。" -ForegroundColor Red
                return @{Ok = $false; Reason = "missing:$cfgPath" }
            }
            $p = Start-BackgroundCommand -FilePath $bin -Arguments "-c $cfgPath" -PidFile $TunnelPid -LogFile $TunnelLog
            return @{Ok = $true; Process = $p; Url = $null }
        }
        "cpolar" {
            $bin = $tc.cpolar.bin
            if (-not (Get-Command $bin -ErrorAction SilentlyContinue)) {
                Write-Host "[错误] 未找到穿透二进制 '$bin'。" -ForegroundColor Red
                Write-Host "  安装：https://www.cpolar.com  （或官网下载 cpolar）" -ForegroundColor Yellow
                return @{Ok = $false; Reason = "missing:$bin" }
            }
            $p = Start-BackgroundCommand -FilePath $bin -Arguments "http $port" -PidFile $TunnelPid -LogFile $TunnelLog
            return @{Ok = $true; Process = $p; Url = $null }
        }
        "mock" {
            Write-Host "[穿透] mock provider（自测模式，不启真进程）→ $($tc.mock.url)" -ForegroundColor Cyan
            return @{Ok = $true; Process = $null; Url = $tc.mock.url }
        }
        default {
            Write-Host "[错误] 未知 tunnel.provider: '$provider'（可选 cloudflared/frp/cpolar/mock）。" -ForegroundColor Red
            return @{Ok = $false; Reason = "unknown:$provider" }
        }
    }
}

function Read-LogSafe {
    # 以 ReadWrite 共享方式读取仍被子进程占用的日志文件，避免「文件正被另一进程使用」
    param([string]$Path)
    if (-not (Test-Path $Path)) { return "" }
    try {
        $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open,
              [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        try {
            $sr = New-Object System.IO.StreamReader($fs)
            try { return $sr.ReadToEnd() } finally { $sr.Close() }
        } finally { $fs.Close() }
    } catch { return "" }
}

function Get-TunnelUrl {
    param($tunnelResult, $provider, $port)
    if ($tunnelResult.Url) { return $tunnelResult.Url }   # mock：直接返回
    if ($provider -eq "cpolar") {
        try {
            $r = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
            $u = ($r.tunnels | ForEach-Object { $_.public_url } | Select-Object -First 1)
            if ($u) { return $u }
        } catch {}
    }
    # 轮询 tunnel.log 与 tunnel.log.err，剥离 ANSI 颜色码后按正则提取 HTTPS URL
    # （公网地址常打在 stderr，两个流分属两个文件，必须都读）
    $regex = if ($provider -eq "cloudflared") {
        'https://[A-Za-z0-9-]+\.trycloudflare\.com'
    } else {
        'https?://[^\s"''<>]+'
    }
    for ($i = 0; $i -lt 60; $i++) {
        $txt = (Read-LogSafe $TunnelLog) + "`n" + (Read-LogSafe $TunnelLogErr)
        if ($txt.Trim()) {
            $clean = $txt -replace '\x1B\[[0-9;]*m', ''
            if ($clean -match $regex) { return $Matches[0] }
        }
        Start-Sleep -Seconds 1
    }
    return $null
}

function Run-DaemonMode {
    Write-Host "[后端] 后台启动中..." -ForegroundColor Cyan
    $be = Start-BackgroundCommand -FilePath $Py -Arguments "server\main.py" -PidFile $BackendPid -LogFile $BackendLog
    if (-not (Wait-BackendReady)) {
        Write-Host "[错误] 后端 30s 内未就绪，已清理。" -ForegroundColor Red
        Stop-Local; exit 1
    }
    Write-Host "[后端] 已后台启动 PID $($be.Id)  http://localhost:18000" -ForegroundColor Green
    Write-Host "日志：data/.run/backend.log    关闭：.\stop-web.ps1"
}

function Run-TunnelMode {
    $cfg = Get-ResolvedConfig
    # 安全检查：公网暴露前必须确认已设访问密码
    if (-not $cfg.access_password -and -not $Force) {
        Write-Host "[警告] access_password 未设置 —— 穿透后公网任何人可进入你的房间。" -ForegroundColor Red
        Write-Host "        建议先在 data/config.json 设置 access_password，或加 -Force 跳过。" -ForegroundColor Red
        try { $ans = Read-Host "确认继续穿透？(y/N)" } catch { $ans = "n" }
        if ($ans -notmatch '^[yY]') { Write-Host "[已取消] 未穿透。"; exit 1 }
    }
    if (-not (Test-Path $RunDir)) { New-Item -ItemType Directory -Path $RunDir -Force | Out-Null }

    Write-Host "[后端] 启动中..." -ForegroundColor Cyan
    $be = Start-BackgroundCommand -FilePath $Py -Arguments "server\main.py" -PidFile $BackendPid -LogFile $BackendLog
    if (-not (Wait-BackendReady)) {
        Write-Host "[错误] 后端 30s 内未就绪，已清理。" -ForegroundColor Red
        Stop-Local; exit 1
    }
    Write-Host "[后端] 就绪 PID $($be.Id)" -ForegroundColor Green

    $port = if ($cfg.tunnel.target_port) { $cfg.tunnel.target_port } else { $cfg.server.port }
    $prov = if ($Provider) { $Provider } else { $cfg.tunnel.provider }
    $tr = Start-Tunnel -cfg $cfg -port $port -ProviderOverride $Provider
    if (-not $tr.Ok) {
        Write-Host "[错误] 穿透启动失败：$($tr.Reason)，已清理后端。" -ForegroundColor Red
        Stop-Local; exit 1
    }
    if ($tr.Process) { Write-Host "[穿透] 进程 PID $($tr.Process.Id)，等待公网地址..." -ForegroundColor Cyan }

    $url = Get-TunnelUrl -tunnelResult $tr -provider $prov -port $port
    if (-not $url) {
        Write-Host "[错误] 60s 内未抓到公网地址，已关闭穿透。" -ForegroundColor Red
        Stop-Local; exit 1
    }
    Set-ShareUrl -url $url
    Write-Host ""
    Write-Host "========== 穿透已建立 ==========" -ForegroundColor Green
    Write-Host "本地地址 ：$("http://localhost:" + $port)"
    Write-Host "公网地址 ：$url"
    Write-Host "后端 PID ：$($be.Id)$(if ($tr.Process) { "  穿透 PID：$($tr.Process.Id)" } else { "  (mock 无进程)" })"
    Write-Host "分享地址已写入 data/config.json 的 share_url"
    Write-Host "关闭命令 ：.\stop-web.ps1"
    Write-Host "================================" -ForegroundColor Green
}

# ---------------- 主流程 ----------------
$Py = Ensure-Venv

if ($Dev -and $Tunnel) {
    Write-Host "[错误] -Dev 与 -Tunnel 不能同时传。" -ForegroundColor Red
    Write-Host "        开发模式前端跑在 Vite(5173)，穿透 18000 只能暴露 API、拿不到前端资源且跨域。请先 npm run build 再用 -Tunnel。" -ForegroundColor Yellow
    exit 1
}

if ($Dev) {
    # 开发模式：后端 + Vite dev server（保持改造前行为）
    $server = Start-Process -FilePath $Py -ArgumentList "server\main.py" -WorkingDirectory $Root -PassThru -WindowStyle Hidden
    Write-Host "[后端] PID $($server.Id)  http://localhost:18000"
    Push-Location (Join-Path $Root "frontend")
    npm run dev
    Pop-Location
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
} else {
    Ensure-Dist
    if ($Tunnel) {
        if (-not (Test-Path $RunDir)) { New-Item -ItemType Directory -Path $RunDir -Force | Out-Null }
        Run-TunnelMode
    } elseif ($Daemon) {
        if (-not (Test-Path $RunDir)) { New-Item -ItemType Directory -Path $RunDir -Force | Out-Null }
        Run-DaemonMode
    } else {
        # 前台阻塞启动（与改造前完全一致）
        Write-Host "[启动] http://localhost:18000  （Ctrl+C 退出）"
        & $Py server\main.py
    }
}
