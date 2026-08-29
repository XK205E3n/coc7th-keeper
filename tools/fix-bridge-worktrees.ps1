<#
.SYNOPSIS
  修复 dsh-lark-bot 的 per-chat git worktree 看不到运行数据 / 代码过期的问题。

.DESCRIPTION
  dsh-lark-bot 会把每个会话运行在隔离的 git worktree 里（设计特性）。
  这带来两个问题：
    1) gitignored 的运行数据（coc-session/ 玩家存档）不会出现在 worktree 中
       → 守密人 bot 读不到房间存档；
    2) worktree 是创建时 HEAD 的静态检出，仓库更新（如新版本发布）后
       worktree 里的代码不会自动跟进。

  本脚本对 ~/.dsh-lark/profiles/default/worktrees/* 下属于本仓库的每个 worktree：
    - 创建目录 Junction：<worktree>\coc-session  →  <仓库根>\coc-session
      （双向透明，bot 写、你在主仓库读，都是同一份数据）
    - 执行 git fetch origin + merge origin/master，把代码同步到最新
      （toy-dancer-comes 等新入库模组随之出现）

.USAGE
  在【普通 PowerShell】里运行（本脚本要写 ~/.dsh-lark 目录，勿在受限沙箱内跑）：

    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\fix-bridge-worktrees.ps1 -WhatIf   # 预览
    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\fix-bridge-worktrees.ps1          # 执行

  何时运行：
    - 第一次部署后；
    - 新建跑团群 / 会话被重置（/reset）之后；
    - 推送了新版本代码到 GitHub 之后（顺带同步 worktree）。

.NOTES
  Junction 用 mklink /J 创建（无需管理员权限，同盘/跨盘均可）。
  若 bot 在 worktree 里写过文件导致 merge 冲突，脚本会报告冲突文件并跳过该 worktree，
  由你手动处理（如 git -C <worktree> reset --hard origin/master）。
#>
[CmdletBinding()]
param(
    [switch]$WhatIf
)

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$ErrorActionPreference = 'Stop'

# 仓库根目录 = 本脚本（tools/fix-bridge-worktrees.ps1）的上上级
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path (Join-Path $RepoRoot 'README.md'))) {
    throw "未能定位仓库根目录（根目录缺少 README.md）：$RepoRoot"
}

$WorktreesRoot = Join-Path $env:USERPROFILE '.dsh-lark\profiles\default\worktrees'
$RuntimeDir = Join-Path $RepoRoot 'coc-session'

if (-not (Test-Path $WorktreesRoot)) {
    Write-Host '没有发现任何 bridge worktree（尚未创建过，无需修复）。' -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $RuntimeDir)) {
    Write-Host ("警告：主仓库运行数据目录不存在：{0}" -f $RuntimeDir) -ForegroundColor Yellow
    Write-Host '请确认仓库根目录有 coc-session/（跑团房间数据）。'
}

$worktrees = Get-ChildItem $WorktreesRoot -Directory -ErrorAction SilentlyContinue
Write-Host ("发现 {0} 个 worktree：{1}" -f $worktrees.Count, (($worktrees.Name) -join ', '))

foreach ($wt in $worktrees) {
    $wtPath = $wt.FullName
    Write-Host ''
    Write-Host ("── worktree: {0}" -f $wt.Name)

    # 确认该 worktree 属于本仓库：用 git 自身输出比对（免疫路径编码差异）
    $belongs = $false
    try {
        $wtGitDir = (& git -C $wtPath rev-parse --git-common-dir 2>$null).Trim()
        $mainGitDir = (& git -C $RepoRoot rev-parse --absolute-git-dir 2>$null).Trim()
        if ($wtGitDir -and $mainGitDir) {
            $norm = { param($s) $s.Replace('/', [System.IO.Path]::DirectorySeparatorChar).TrimEnd([System.IO.Path]::DirectorySeparatorChar).ToLowerInvariant() }
            if ((& $norm $wtGitDir) -eq (& $norm $mainGitDir)) { $belongs = $true }
        }
    } catch { $belongs = $false }
    if (-not $belongs) {
        Write-Host "  非本仓库 worktree（common-dir 不匹配），跳过。" -ForegroundColor DarkGray
        continue
    }

    # 1) 运行数据 junction
    $link = Join-Path $wtPath 'coc-session'
    if (Test-Path $link) {
        $item = Get-Item $link -Force
        if ($item.LinkType -eq 'Junction') {
            Write-Host '  coc-session junction 已存在，跳过。' -ForegroundColor DarkGray
        } else {
            Write-Host '  coc-session 已存在但不是 junction，跳过（请人工检查是否被错误检出）。' -ForegroundColor Yellow
        }
    } else {
        Write-Host ("  创建 junction: {0}  →  {1}" -f $link, $RuntimeDir)
        if (-not $WhatIf) {
            cmd /c mklink /J "`"$link`"" "`"$RuntimeDir`"" | Out-Null
            if (Test-Path $link) { Write-Host '  ✓ junction 已创建' -ForegroundColor Green }
            else { Write-Host '  ✗ junction 创建失败' -ForegroundColor Red }
        }
    }

    # 2) 代码同步到 origin/master
    Write-Host '  同步代码到 origin/master ...'
    if (-not $WhatIf) {
        & git -C $wtPath fetch origin 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Host '  ✗ git fetch 失败，跳过该 worktree 的合并。' -ForegroundColor Red; continue }
        $merge = & git -C $wtPath merge origin/master 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host '  ✓ 已同步到最新 master' -ForegroundColor Green
        } else {
            Write-Host '  ⚠️ merge 有冲突，请手动处理（git -C <worktree> reset --hard origin/master 可强制对齐）：' -ForegroundColor Yellow
            $merge | Select-Object -Last 6 | ForEach-Object { Write-Host ("     " + $_) }
        }
    }
}

Write-Host ''
if ($WhatIf) {
    Write-Host '【预览模式】未做任何修改。去掉 -WhatIf 后执行。' -ForegroundColor Yellow
} else {
    Write-Host '✅ 完成。现在在飞书群里发 /reset 让 bot 用新会话重试；' -ForegroundColor Green
    Write-Host '   bot 应能看到 coc-session/<房间>/room.json 与最新模组。'
}
exit 0
