# coc.ps1 - 工作区内 CoC 守密人 skill 的统一调用入口
#
# 设计目标：
#   1) 让 agent 在工作区内只用相对路径（.dsh\bin\coc.ps1 modules list），
#      避免出现 "C:\Users\xingk\..." 这类跨工作区路径触发 plan-gate。
#   2) 工作目录自动锁定到本脚本所在的项目根目录；COC_SESSION_ROOT
#      默认指向 <root>\coc-session；COC_ROOM 默认 demo。
#   3) 与 coc.cmd 完全等价，仅入口形态不同（PowerShell 友好）。
#
# 用法：
#   coc.ps1 modules list
#   coc.ps1 modules show 2
#   coc.ps1 help md
#   coc.ps1 room status demo
#   coc.ps1 roll 1d100 --by alice --why "..."
#   coc.ps1 check skill "Spot Hidden" 50 --by alice --room demo --why "..."
#   coc.ps1 sanity check --player-file "coc-session/demo/players/alice.json" 5
#   coc.ps1 combat attack 50 25 1d6+1 +0 --by alice --room demo

[CmdletBinding()]
param(
    [Parameter(Position = 0)] [string]$Command,
    [Parameter(ValueFromRemainingArguments = $true)] [string[]]$Rest
)

$ErrorActionPreference = 'Stop'

# --- 锁定工作区根目录（=本脚本所在 .dsh\bin 的上两级） ---
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$CocRoot = $Root.Path
$SkillDir = Join-Path $CocRoot '.dsh\skills\coc7th-keeper'
$Scripts  = Join-Path $SkillDir 'scripts'
$SessionRoot = Join-Path $CocRoot 'coc-session'

$env:COC_SESSION_ROOT = $SessionRoot
if (-not $env:COC_ROOM) { $env:COC_ROOM = 'demo' }
# 预设模组目标目录：显式锚定到工作区内（脚本默认即此值，此处固化声明）
if (-not $env:COC_MODULES_DIR) { $env:COC_MODULES_DIR = Join-Path $SkillDir 'modules' }

if ([string]::IsNullOrWhiteSpace($Command)) {
    @"
Usage: coc.ps1 <command> [args...]

Direct script routing (workspace-only, no absolute paths):
  modules list | show <id> | pick | ids
  help md | json
  build_help_cache
  build_modules_cache
  build_all_cache
  roll <expr> [--by X] [--why ...] [--room X] [--no-log]
  check skill <name> <val> ... | luck <val> ... | opposed ... | combined ...
  sanity check --player-file <path> <loss> ... | indef
  combat attack <atk> <def> <dmg> <db> ... | ini ... | wound ...
  room init|join|leave|build|status|audit|save|load|kick|pwd <args>
  build <name> [--age N] [--out PATH]

Composite helpers:
  use-pregen <name> --room <id> --player <name>

Environment (auto-set by this wrapper; do not export outside):
  COC_SESSION_ROOT=$SessionRoot
  COC_ROOM=$($env:COC_ROOM)
  COC_SKILL_DIR=$SkillDir
"@
    exit 0
}

# --- 映射命令 → 脚本 ---
$map = [ordered]@{
    'modules'             = 'modules.py'
    'help'                = 'help.py'
    'build_help_cache'    = 'build_help_cache.py'
    'build_modules_cache' = 'build_modules_cache.py'
    'build_all_cache'     = 'build_all_cache.py'
    'roll'                = 'roll.py'
    'check'               = 'check.py'
    'sanity'              = 'sanity.py'
    'combat'              = 'combat.py'
    'room'                = 'room.py'
    'build'               = 'build.py'
    'use-pregen'          = 'use_pregen.py'
}

if (-not $map.Contains($Command)) {
    Write-Error "Unknown coc command: $Command. Run without args for usage."
    exit 2
}

$scriptPath = Join-Path $Scripts $map[$Command]
if (-not (Test-Path $scriptPath)) {
    Write-Error "Script not found: $scriptPath"
    exit 2
}

$argList = @($Rest)
& python $scriptPath @argList
exit $LASTEXITCODE