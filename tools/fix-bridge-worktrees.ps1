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
    - 把代码同步到 origin/master：
        * 先尝试 git fetch origin（需要仓库凭据，通常用 gh auth setup-git 配一次）；
        * 失败时自动改用 gh auth token 的运行时 URL 推送式 fetch（token 不落配置）；
        * 再 git merge origin/master（冲突会明确报告并停手，不强制覆盖）。

.USAGE
  在【普通 PowerShell】里运行（本脚本要写 ~/.dsh-lark 目录，勿在受限沙箱内跑）：

    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\fix-bridge-worktrees.ps1 -WhatIf   # 预览
    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\fix-bridge-worktrees.ps1          # 执行

  已集成进「一键开启」（bot-start.ps1 启动桥接前自动执行本脚本）。

.NOTES
  Windows PowerShell 5.1 兼容：全程 $ErrorActionPreference='Continue'，错误一律走退出码/返回值判断，
  git 的原生命令 stderr 不会再触发 NativeCommandError 中断。
  Junction 用 mklink /J 创建（无需管理员权限，同盘/跨盘均可）。
#>
[CmdletBinding()]
param(
    [switch]$WhatIf
)

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

# 关键：PS5.1 下 'Stop' + 原生命令 stderr 会中断脚本；这里统一 'Continue'，用退出码判断
$ErrorActionPreference = 'Continue'

# 仓库根目录 = 本脚本（tools/fix-bridge-worktrees.ps1）的上上级
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path (Join-Path $RepoRoot 'README.md'))) {
    Write-Host "无法定位仓库根目录（根目录缺少 README.md）：$RepoRoot" -ForegroundColor Red
    exit 1
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

function Invoke-Git {
    param([string[]]$ArgsList)
    $out = & git @ArgsList 2>&1
    return @{ Code = $LASTEXITCODE; Out = ($out -join "`n") }
}

function Get-GhTokenFetchUrl {
    # 用 gh auth token 构造临时 fetch URL（token 不落配置、不写盘）
    try {
        $tok = (& gh auth token 2>$null).Trim()
        if ($tok) { return "https://x-access-token:$tok@github.com/XK205E3n/coc7th-keeper.git" }
    } catch { }
    return $null
}

$worktrees = Get-ChildItem $WorktreesRoot -Directory -ErrorAction SilentlyContinue
Write-Host ("发现 {0} 个 worktree：{1}" -f $worktrees.Count, (($worktrees.Name) -join ', '))

foreach ($wt in $worktrees) {
    $wtPath = $wt.FullName
    Write-Host ''
    Write-Host ("── worktree: {0}" -f $wt.Name)

    # 1) 确认该 worktree 属于本仓库：用 git 自身输出比对（免疫路径编码差异）
    $belongs = $false
    $wtGitDir = $null; $mainGitDir = $null
    try {
        $wtGitDir = (& git -C $wtPath rev-parse --git-common-dir 2>$null | Select-Object -First 1).Trim()
        $mainGitDir = (& git -C $RepoRoot rev-parse --absolute-git-dir 2>$null | Select-Object -First 1).Trim()
        if ($wtGitDir -and $mainGitDir) {
            $norm = { param($s) $s.Replace('/', [System.IO.Path]::DirectorySeparatorChar).TrimEnd([System.IO.Path]::DirectorySeparatorChar).ToLowerInvariant() }
            if ((& $norm $wtGitDir) -eq (& $norm $mainGitDir)) { $belongs = $true }
        }
    } catch { $belongs = $false }
    if (-not $belongs) {
        Write-Host "  非本仓库 worktree（common-dir 不匹配），跳过。" -ForegroundColor DarkGray
        continue
    }

    # 2) 运行数据 junction
    $link = Join-Path $wtPath 'coc-session'
    if (Test-Path $link) {
        $item = Get-Item $link -Force -ErrorAction SilentlyContinue
        if ($item -and $item.LinkType -eq 'Junction') {
            Write-Host ('  coc-session junction 已存在（→ {0}），跳过。' -f $item.Target) -ForegroundColor DarkGray
        } elseif ($item) {
            Write-Host '  coc-session 已存在但不是 junction，跳过（请人工检查是否被错误检出）。' -ForegroundColor Yellow
        }
    } else {
        Write-Host ("  创建 junction: {0}`n             →  {1}" -f $link, $RuntimeDir)
        if (-not $WhatIf) {
            cmd /c mklink /J "`"$link`"" "`"$RuntimeDir`"" | Out-Null
            if (Test-Path $link) { Write-Host '  ✓ junction 已创建' -ForegroundColor Green }
            else { Write-Host '  ✗ junction 创建失败（请检查目标目录与权限）' -ForegroundColor Red }
        }
    }
    # junction 可读性复核
    if (-not $WhatIf -and (Test-Path $link) -and (Test-Path (Join-Path $link '1\room.json'))) {
        Write-Host '  ✓ 存档可读（coc-session/1/room.json 通过 junction 可见）' -ForegroundColor Green
    }

    # 3) 代码同步到 origin/master（fetch 带凭据兜底）
    if ($WhatIf) { Write-Host '  [预览] 将执行 fetch + merge origin/master' -ForegroundColor DarkGray; continue }

    Write-Host '  同步代码到 origin/master ...'
    $r = Invoke-Git -ArgsList @('-C', $wtPath, 'fetch', 'origin')
    if ($r.Code -ne 0) {
        Write-Host ('  ⚠️ git fetch origin 失败（{0}），尝试 gh token 兜底...' -f $r.Code) -ForegroundColor Yellow
        $tokenUrl = Get-GhTokenFetchUrl
        if ($tokenUrl) {
            $r2 = Invoke-Git -ArgsList @('-C', $wtPath, 'fetch', $tokenUrl, 'master')
            if ($r2.Code -eq 0) { Write-Host '  ✓ fetch 成功（gh token 兜底）' -ForegroundColor Green }
        } else {
            $r2 = @{ Code = 1 }
        }
        if ($r2.Code -ne 0) {
            Write-Host '  ✗ fetch 全部失败。请先在普通终端执行一次：gh auth setup-git' -ForegroundColor Red
            Write-Host '    然后重跑本脚本；或手动：git -C <worktree> fetch origin && git -C <worktree> merge origin/master'
            continue
        }
    } else {
        Write-Host '  ✓ fetch origin 成功' -ForegroundColor Green
    }

    $m = Invoke-Git -ArgsList @('-C', $wtPath, 'merge', 'origin/master')
    if ($m.Code -eq 0) {
        $head = (Invoke-Git -ArgsList @('-C', $wtPath, 'rev-parse', '--short', 'HEAD')).Out.Trim()
        Write-Host ("  ✓ 已同步到 {0}" -f $head) -ForegroundColor Green
        $tdc = Test-Path (Join-Path $wtPath '.dsh\skills\coc7th-keeper\modules\toy-dancer-comes')
        Write-Host ("  toy-dancer-comes 模组可见: {0}" -f $(if ($tdc) { '是 ✓' } else { '否 ✗' }))
    } else {
        Write-Host '  ⚠️ merge 有冲突，未强制覆盖。手动处理（下列其一）：' -ForegroundColor Yellow
        Write-Host '     git -C <worktree> reset --hard origin/master     # 丢弃 worktree 本地改动，强制对齐'
        Write-Host "     （或用编辑器解决冲突后再 commit）"
        $m.Out | Select-Object -Last 4 | ForEach-Object { Write-Host ("       " + $_) }
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
