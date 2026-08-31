#requires -Version 5.1
<#
.SYNOPSIS
    打包 coc7th-keeper 发布 ZIP 到 dist/coc7th-keeper-v<版本>.zip。
.DESCRIPTION
    从仓库根目录收集发布内容到临时暂存目录，再以 Compress-Archive 压缩。
    排除规则与 .gitignore 同步 —— ZIP 内绝不出现：
    .dsh/backup/（飞书 appSecret）、模组/（原版 PDF 与转换源稿）、
    coc-session 与 coc-session-*/（玩家运行时数据）、
    __pycache__ / *.pyc / *.log*、node_modules、.agent-teams、dist、.git。
    内置模组（the-haunting、toy-dancer-comes）随包分发。
    打包完成后自动核验 ZIP 条目列表，发现排除项即中止。
.NOTES
    用法：powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\pack-release.ps1 [-Version 0.2.0]
    依赖：tar.exe（Windows 10+ 自带 bsdtar）用于打包后核验。
#>
[CmdletBinding()]
param(
    [string]$Version = "0.2.0"
)

$ErrorActionPreference = "Stop"

# 仓库根目录 = 本脚本（tools/pack-release.ps1）的上上级
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path (Join-Path $RepoRoot "README.md"))) {
    throw "未能定位仓库根目录（根目录缺少 README.md）：$RepoRoot"
}

# ---------- 排除规则（与 .gitignore 同步） ----------
# 目录名精确排除
$ExcludedDirNames = @(
    '.git',
    '.agent-teams',          # 团队状态
    'dist',                  # 构建产物（输出目录自身）
    'node_modules',
    '__pycache__',
    'backup',                # .dsh/backup（含飞书 appSecret）
    '模组'                    # 原版 PDF 与转换源稿（不入公共仓库）
)
# 名称模式通配排除
$ExcludedNamePatterns = @(
    'coc-session*',          # 运行时玩家数据（coc-session、coc-session-final/...）
    '*.pyc',
    '*.log*'                 # 日志（含 .dsh/bin/dsh-*.log 与 .prev）
)

function Test-Excluded {
    param([string]$Name)
    if ($ExcludedDirNames -contains $Name) { return $true }
    foreach ($pat in $ExcludedNamePatterns) {
        if ($Name -like $pat) { return $true }
    }
    return $false
}

function Copy-ReleaseTree {
    param(
        [string]$SourceDir,
        [string]$DestDir
    )
    Get-ChildItem -Force -LiteralPath $SourceDir | ForEach-Object {
        $item = $_
        if (Test-Excluded -Name $item.Name) { return }
        $target = Join-Path $DestDir $item.Name
        if ($item.PSIsContainer) {
            New-Item -ItemType Directory -Force -Path $target | Out-Null
            Copy-ReleaseTree -SourceDir $item.FullName -DestDir $target
        } else {
            Copy-Item -LiteralPath $item.FullName -Destination $target -Force
        }
    }
}

# ---------- 暂存与打包 ----------
$Staging = Join-Path ([System.IO.Path]::GetTempPath()) ("coc7th-pack-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Staging | Out-Null

try {
    Copy-ReleaseTree -SourceDir $RepoRoot -DestDir $Staging

    $DistDir = Join-Path $RepoRoot "dist"
    New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
    $ZipPath = Join-Path $DistDir ("coc7th-keeper-v{0}.zip" -f $Version)

    if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }

    Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $ZipPath -CompressionLevel Optimal

    # ---------- 打包后核验：ZIP 条目不得含排除项 ----------
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zipHandle = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $zipEntries = @($zipHandle.Entries | ForEach-Object { $_.FullName })
    } finally {
        $zipHandle.Dispose()
    }
    $forbidden = $zipEntries | Where-Object {
        $_ -match '(^|/)\.git/|(^|/)\.agent-teams/|(^|/)dist/|(^|/)node_modules/|(^|/)__pycache__/|(^|/)backup/|(^|/)模组/|(^|/)coc-session'
    }
    if ($forbidden) {
        throw ("ZIP 内发现排除项，打包中止：`n" + ($forbidden -join "`n"))
    }

    Write-Host ("OK: {0}" -f $ZipPath)
    Write-Host ("ZIP 条目数: {0}；排除项命中: {1}" -f $zipEntries.Count, $forbidden.Count)
} finally {
    Remove-Item -Recurse -Force $Staging -ErrorAction SilentlyContinue
}
