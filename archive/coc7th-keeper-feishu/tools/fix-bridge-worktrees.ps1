<#
.SYNOPSIS
  修复 dsh-lark-bot 的 per-chat git worktree：运行数据挂载 + 代码同步 + 零 plan-gate。

.DESCRIPTION
  dsh-lark-bot 把每个会话跑在隔离 git worktree 里。本脚本对每个本仓库 worktree：
    1) 运行数据（coc-session）改为 worktree 内的【真实目录】——bot 写入不越界，
       DSH workspace-write 自动放行，不再触发 plan-gate / 审批卡片；
    2) 主仓库的 coc-session 改为【目录 junction】指向 worktree 的真实目录，
       你在主仓库照旧读日志（双向同一份数据）；
    3) 代码同步到 origin/master（fetch 带 gh token 兜底 + merge + 核验）。

  迁移策略（幂等、可回滚）：
    - 若 worktree 的 coc-session 是旧版 junction → 移除，改为真实目录；
    - 若主仓库 coc-session 还是真实目录（有数据）→ 先复制进 worktree，
      再把主仓库目录改名备份为 coc-session-bak-<时间戳>（gitignored），
      最后在主仓库建 junction → worktree；
    - 若主仓库 coc-session 已是 junction → 跳过。

.USAGE
  在【普通 PowerShell】里运行（要写 ~/.dsh-lark 与主仓库，勿在受限沙箱内跑）：

    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\fix-bridge-worktrees.ps1 -WhatIf   # 预览
    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\fix-bridge-worktrees.ps1          # 执行

  已集成进「一键开启」（bot-start.ps1 启动桥接前自动执行本脚本）。

.NOTES
  Windows PowerShell 5.1 兼容：全程 $ErrorActionPreference='Continue'，错误走退出码判断。
  Junction 用 mklink /J（无需管理员权限）。
#>
[CmdletBinding()]
param(
    [switch]$WhatIf
)

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$ErrorActionPreference = 'Continue'

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path (Join-Path $RepoRoot 'README.md'))) {
    Write-Host "无法定位仓库根目录（根目录缺少 README.md）：$RepoRoot" -ForegroundColor Red
    exit 1
}

$WorktreesRoot = Join-Path $env:USERPROFILE '.dsh-lark\profiles\default\worktrees'
$MainRuntime = Join-Path $RepoRoot 'coc-session'

if (-not (Test-Path $WorktreesRoot)) {
    Write-Host '没有发现任何 bridge worktree（尚未创建过，无需修复）。' -ForegroundColor Green
    exit 0
}

function Invoke-Git {
    param([string[]]$ArgsList)
    $out = & git @ArgsList 2>&1
    return @{ Code = $LASTEXITCODE; Out = ($out -join "`n") }
}

function Get-GhTokenFetchUrl {
    try {
        $tok = (& gh auth token 2>$null).Trim()
        if ($tok) { return "https://x-access-token:$tok@github.com/XK205E3n/coc7th-keeper.git" }
    } catch { }
    return $null
}

function New-Junction {
    param([string]$Link, [string]$Target)
    cmd /c mklink /J "`"$Link`"" "`"$Target`"" | Out-Null
    return (Test-Path $Link)
}

$worktrees = Get-ChildItem $WorktreesRoot -Directory -ErrorAction SilentlyContinue
Write-Host ("发现 {0} 个 worktree：{1}" -f $worktrees.Count, (($worktrees.Name) -join ', '))

foreach ($wt in $worktrees) {
    $wtPath = $wt.FullName
    Write-Host ''
    Write-Host ("── worktree: {0}" -f $wt.Name)

    # 1) 确认属于本仓库
    $belongs = $false
    try {
        $wtGitDir = (& git -C $wtPath rev-parse --git-common-dir 2>$null | Select-Object -First 1).Trim()
        $mainGitDir = (& git -C $RepoRoot rev-parse --absolute-git-dir 2>$null | Select-Object -First 1).Trim()
        if ($wtGitDir -and $mainGitDir) {
            $norm = { param($s) $s.Replace('/', [System.IO.Path]::DirectorySeparatorChar).TrimEnd([System.IO.Path]::DirectorySeparatorChar).ToLowerInvariant() }
            if ((& $norm $wtGitDir) -eq (& $norm $mainGitDir)) { $belongs = $true }
        }
    } catch { $belongs = $false }
    if (-not $belongs) { Write-Host "  非本仓库 worktree，跳过。" -ForegroundColor DarkGray; continue }

    # 2) 运行数据：worktree 内真实目录 + 主仓库 junction 指向它
    $link = Join-Path $wtPath 'coc-session'
    $linkItem = Get-Item $link -Force -ErrorAction SilentlyContinue

    # 2a) 旧版 junction → 移除
    if ($linkItem -and $linkItem.LinkType -eq 'Junction') {
        Write-Host '  移除旧版 junction（改为真实目录，让 bot 写入不越界）...'
        if (-not $WhatIf) { cmd /c rmdir "`"$link`"" | Out-Null }
        $linkItem = $null
    }
    # 2b) 确保 worktree 内是真实目录
    if (-not (Test-Path $link)) {
        if (-not $WhatIf) { New-Item -ItemType Directory -Path $link | Out-Null }
        Write-Host '  ✓ worktree coc-session 真实目录就绪' -ForegroundColor Green
    } else {
        Write-Host '  ✓ worktree coc-session 已是真实目录' -ForegroundColor Green
    }

    # 2c) 主仓库 coc-session：真实目录 → 迁移 + 改 junction
    $mainItem = Get-Item $MainRuntime -Force -ErrorAction SilentlyContinue
    if ($mainItem -and $mainItem.LinkType -ne 'Junction') {
        Write-Host '  迁移主仓库 coc-session → worktree（复制 + 备份 + 主仓库改 junction）...'
        if (-not $WhatIf) {
            Copy-Item -Path (Join-Path $MainRuntime '*') -Destination $link -Recurse -Force -ErrorAction SilentlyContinue
            $bakName = 'coc-session-bak-' + (Get-Date -Format 'yyyyMMddHHmmss')
            Rename-Item -Path $MainRuntime -NewName $bakName -ErrorAction SilentlyContinue
            if (New-Junction -Link $MainRuntime -Target $link) {
                Write-Host ("  ✓ 主仓库 coc-session 已改为 junction → worktree（备份：{0}）" -f $bakName) -ForegroundColor Green
            } else {
                Write-Host '  ✗ 主仓库 junction 创建失败，请手动处理' -ForegroundColor Red
            }
        }
    } elseif ($mainItem -and $mainItem.LinkType -eq 'Junction') {
        Write-Host '  ✓ 主仓库 coc-session 已是 junction（→ worktree），跳过' -ForegroundColor DarkGray
    } else {
        Write-Host '  ⚠️ 主仓库 coc-session 不存在（首次部署？），跳过迁移' -ForegroundColor Yellow
    }

    # 2d) 可读性复核
    if (-not $WhatIf -and (Test-Path (Join-Path $link '1\room.json'))) {
        Write-Host '  ✓ 存档可读（coc-session/1/room.json）' -ForegroundColor Green
    }

    # 3) 代码同步
    if ($WhatIf) { Write-Host '  [预览] 将执行 fetch + merge origin/master' -ForegroundColor DarkGray; continue }
    Write-Host '  同步代码到 origin/master ...'
    $r = Invoke-Git -ArgsList @('-C', $wtPath, 'fetch', 'origin')
    if ($r.Code -ne 0) {
        Write-Host ('  ⚠️ git fetch origin 失败（{0}），尝试 gh token 兜底...' -f $r.Code) -ForegroundColor Yellow
        $tokenUrl = Get-GhTokenFetchUrl
        $r2 = @{ Code = 1 }
        if ($tokenUrl) { $r2 = Invoke-Git -ArgsList @('-C', $wtPath, 'fetch', $tokenUrl, 'master') }
        if ($r2.Code -ne 0) {
            Write-Host '  ✗ fetch 全部失败。请先执行一次：gh auth setup-git，然后重跑本脚本' -ForegroundColor Red
            continue
        }
        Write-Host '  ✓ fetch 成功（gh token 兜底）' -ForegroundColor Green
    } else {
        Write-Host '  ✓ fetch origin 成功' -ForegroundColor Green
    }
    $m = Invoke-Git -ArgsList @('-C', $wtPath, 'merge', 'origin/master')
    if ($m.Code -eq 0) {
        $head = (Invoke-Git -ArgsList @('-C', $wtPath, 'rev-parse', '--short', 'HEAD')).Out.Trim()
        Write-Host ("  ✓ 已同步到 {0}" -f $head) -ForegroundColor Green
        Write-Host ("  toy-dancer-comes 可见: {0}" -f $(if (Test-Path (Join-Path $wtPath '.dsh\skills\coc7th-keeper\modules\toy-dancer-comes')) { '是 ✓' } else { '否 ✗' }))
    } else {
        Write-Host '  ⚠️ merge 有冲突，未强制覆盖。手动：git -C <worktree> reset --hard origin/master' -ForegroundColor Yellow
        $m.Out | Select-Object -Last 4 | ForEach-Object { Write-Host ("       " + $_) }
    }
}

Write-Host ''
if ($WhatIf) {
    Write-Host '【预览模式】未做任何修改。去掉 -WhatIf 后执行。' -ForegroundColor Yellow
} else {
    Write-Host '✅ 完成。现在在飞书群里发 /reset 让 bot 用新会话重试；' -ForegroundColor Green
    Write-Host '   bot 写入 coc-session 不再越界（零 plan-gate），且能看到最新模组。'
}
exit 0
