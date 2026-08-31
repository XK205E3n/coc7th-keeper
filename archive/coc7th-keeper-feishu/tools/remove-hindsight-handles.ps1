<#
.SYNOPSIS
  删除 DSH Desktop 的 web profile 里残留的 Hindsight 记忆插件句柄。

.DESCRIPTION
  DeepSeek Harness 的 web profile 若安装了 `@vectorize-io/hindsight-coding-agents`
  （Hindsight 记忆功能，默认未配置 apiToken 时会报 401），会在会话里注入
  hindsight_* 工具与「hindsight_knowledge」提示词。本脚本将其移除：

    1) node_modules\@vectorize-io\hindsight-coding-agents / hindsight-all 包目录
    2) node_modules\.bin\hindsight-* 可执行钩子（40+ 个）
    3) profiles\web\package.json 的 dependencies 与 dsh.profile.bundles 两处引用
    4) node_modules\.modules.yaml 与 pnpm-lock.yaml 中的 hindsight 条目（尽力清理）

  作用对象：%USERPROFILE%\AppData\Roaming\dsh-desktop\harness\profiles\web
  （DSH Desktop 注入的 harness 家目录；~/.dsh 与 dsh-lark 相关目录不受影响。）

.USAGE
  在【普通 PowerShell】里运行（不要放在受限沙箱/自动审批模式下）：

    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\remove-hindsight-handles.ps1 -WhatIf   # 预览
    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\remove-hindsight-handles.ps1          # 执行

  运行完毕后：完全退出并重启 DSH Desktop（或重新执行启动脚本），
  新会话中 hindsight_* 工具与相关提示词即消失。

.NOTES
  删除不可逆；如需恢复可进入该 profile 执行 `pnpm install` 重新安装。
  本脚本不触碰 .credentials.yaml / settings.yaml / dsh-lark 配置。
#>
[CmdletBinding()]
param(
    [switch]$WhatIf
)

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$ErrorActionPreference = 'Stop'
$web = Join-Path $env:USERPROFILE 'AppData\Roaming\dsh-desktop\harness\profiles\web'

if (-not (Test-Path $web)) {
    Write-Host "未找到 web profile：$web" -ForegroundColor Yellow
    Write-Host '请确认 DSH Desktop 已安装且初始化过 web profile。'
    exit 1
}

$hits = @()

# ---- 1) 删除 hindsight 包目录 ----
foreach ($d in @("$web\node_modules\@vectorize-io\hindsight-coding-agents", "$web\node_modules\@vectorize-io\hindsight-all")) {
    if (Test-Path $d) {
        $hits += "包目录: $d"
        if (-not $WhatIf) { Remove-Item -Recurse -Force $d }
    }
}

# ---- 2) 删除 .bin 钩子 ----
$binDir = "$web\node_modules\.bin"
if (Test-Path $binDir) {
    $shims = Get-ChildItem $binDir -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^hindsight' }
    foreach ($s in $shims) {
        $hits += ".bin 钩子: $($s.Name)"
        if (-not $WhatIf) { Remove-Item -Force $s.FullName }
    }
}

# ---- 3) 修 package.json（dependencies + dsh.profile.bundles） ----
$pj = "$web\package.json"
if (Test-Path $pj) {
    $pkg = Get-Content $pj -Raw -Encoding UTF8 | ConvertFrom-Json
    $changed = $false
    if ($pkg.dependencies.PSObject.Properties['@vectorize-io/hindsight-coding-agents']) {
        $pkg.dependencies.PSObject.Properties.Remove('@vectorize-io/hindsight-coding-agents')
        $hits += 'package.json: dependencies 移除 @vectorize-io/hindsight-coding-agents'
        $changed = $true
    }
    if ($pkg.dsh.profile.bundles -contains '@vectorize-io/hindsight-coding-agents') {
        $pkg.dsh.profile.bundles = @($pkg.dsh.profile.bundles | Where-Object { $_ -ne '@vectorize-io/hindsight-coding-agents' })
        $hits += 'package.json: dsh.profile.bundles 移除 @vectorize-io/hindsight-coding-agents'
        $changed = $true
    }
    if ($changed -and -not $WhatIf) {
        Set-Content -Path $pj -Value ($pkg | ConvertTo-Json -Depth 20) -Encoding UTF8
    }
}

# ---- 4) .modules.yaml 过滤 ----
$my = "$web\node_modules\.modules.yaml"
if (Test-Path $my) {
    $kept = Get-Content $my -Encoding UTF8 | Where-Object { $_ -notmatch 'hindsight' }
    if ($kept.Count -lt (Get-Content $my -Encoding UTF8).Count) {
        $hits += '.modules.yaml: 移除 hindsight 条目'
        if (-not $WhatIf) { Set-Content -Path $my -Value $kept -Encoding UTF8 }
    }
}

# ---- 5) pnpm-lock.yaml 尽力清理 ----
$lk = "$web\pnpm-lock.yaml"
if (Test-Path $lk) {
    $t = Get-Content $lk -Raw -Encoding UTF8
    $before = $t
    $t = $t -replace '(?m)^(\s*)''?@vectorize-io/hindsight-coding-agents''?:(\r?\n\1\s+\S[^\r\n]*)*\r?\n', ''
    $t = $t -replace '(?m)^(\s*)''?@vectorize-io/hindsight-[^:\r\n]*''?:(\r?\n\1  [^\r\n]*)*(\r?\n)?', ''
    if ($t -ne $before) {
        $hits += 'pnpm-lock.yaml: 移除 hindsight 条目'
        if (-not $WhatIf) { Set-Content -Path $lk -Value $t -Encoding UTF8 -NoNewline }
    }
}

# ---- 报告 ----
if ($hits.Count -eq 0) {
    Write-Host '未发现任何 hindsight 句柄，无需处理（或者已被清理过）。' -ForegroundColor Green
} else {
    Write-Host ('发现 {0} 处 hindsight 句柄：' -f $hits.Count) -ForegroundColor Cyan
    $hits | ForEach-Object { Write-Host "  - $_" }
    if ($WhatIf) {
        Write-Host ''
        Write-Host '【预览模式】未做任何修改。去掉 -WhatIf 后执行将真正删除。' -ForegroundColor Yellow
    } else {
        Write-Host ''
        Write-Host '✅ 清理完成。请完全退出并重启 DSH Desktop 使生效；' -ForegroundColor Green
        Write-Host '   重启后新会话不再出现 hindsight_* 工具与提示词。'
        Write-Host '   （如需恢复：进入该 profile 目录执行 pnpm install）'
    }
}
exit 0
