<#
.SYNOPSIS
  交互式配置 DeepSeek Harness / dsh-lark-bot 的 API Key、Provider、Model（本地脚本）。
  请在【普通 PowerShell】里运行（不是受限沙箱 / 自动审批模式）。

.DESCRIPTION
  修改三个目标文件（默认 DSH_HOME 为 ~/.dsh）：

    %USERPROFILE%\.dsh\.credentials.yaml   凭据文档：refs.<API_KEY>（如 MINIMAX_CN_API_KEY）
    %USERPROFILE%\.dsh\settings.yaml       默认模型：agent-default-model: { provider, model }
    %USERPROFILE%\.dsh-lark\config.json    桥接模型：profiles.default.preferences.model（"<provider>/<model>"）

  设计约束：
    - API Key 用 Read-Host -AsSecureString 收集，写入全程不把密钥打印到控制台（只显示长度）。
    - 写前对每个存在的目标文件生成一份时间戳备份：<file>.bak-YYYYMMDDTHHMMSS。
    - 目标文件不存在时【不自动创建】，只打印手工创建指引与格式模板。
    - 全程 UTF-8 读写。
    - 默认真实写入；加 -WhatIf 仅预览将做的改动，不写任何文件。

.WARNING
  %USERPROFILE%\.dsh-lark\config.json 的 profiles.default.preferences.model 绝不能是
  空字符串——空串会短路桥接的模型路由解析，导致机器人在飞书【全部失败】
  （2026-08-28 真实事故，诊断见项目内 .dsh/DIAGNOSIS-20260828.md）。
  本脚本始终写入 "provider/model" 非空值；请勿事后手工清空。

.USAGE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\configure-provider.ps1 -WhatIf   # 预览
  powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\configure-provider.ps1          # 真实写入

  写入完成后重启机器人使其生效（在项目根目录）：
    .\bot-start.ps1 -Restart
#>
[CmdletBinding()]
param(
    [switch]$WhatIf
)

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::InputEncoding  = [System.Text.Encoding]::UTF8
} catch {}

$ErrorActionPreference = 'Stop'
$Preview = [bool]$WhatIf

# ---------------------------------------------------------------- 路径
$DshHome    = Join-Path $env:USERPROFILE '.dsh'
$LarkHome   = Join-Path $env:USERPROFILE '.dsh-lark'
$CredFile   = Join-Path $DshHome '.credentials.yaml'
$Settings   = Join-Path $DshHome 'settings.yaml'
$LarkConfig = Join-Path $LarkHome 'config.json'

# ---------------------------------------------------------------- 工具函数
function Format-YamlValue {
    param([string]$Value)
    # 单引号包裹并转义内部单引号，保证任意字符串在 YAML 中安全
    return "'" + ($Value -replace "'", "''") + "'"
}

function Get-Slice {
    param([object[]]$Lines, [int]$Start, [int]$EndExclusive)
    if ($Start -lt 0) { $Start = 0 }
    if ($EndExclusive -gt $Lines.Count) { $EndExclusive = $Lines.Count }
    if ($Start -ge $EndExclusive) { return @() }
    return @($Lines[$Start..($EndExclusive - 1)])
}

function Backup-File {
    param([string]$Path, [string]$Stamp)
    if (-not (Test-Path $Path)) { return }
    $bak = "$Path.bak-$Stamp"
    if ($Preview) {
        Write-Host "    [预览] 将备份 → $bak" -ForegroundColor DarkYellow
    } else {
        Copy-Item -Path $Path -Destination $bak -Force
        Write-Host "    备份 → $bak" -ForegroundColor DarkGray
    }
}

# 在 credentials.yaml 中设置 refs.<Key> = <Value>（存在则整体替换该键行，不存在则插到 refs 块内）
function Set-CredentialsRef {
    param([string]$Path, [string]$Key, [string]$Value)
    $raw  = [System.IO.File]::ReadAllText($Path)
    if (-not $raw.EndsWith("`n")) { $raw += "`n" }
    $lines = @($raw -split "\r?\n")
    $newLine = '  ' + $Key + ': ' + (Format-YamlValue $Value)

    # 1) 已有同名键：整行替换
    $keyRe = '(?m)^[ \t]*' + [regex]::Escape($Key) + ':[ \t]*.*$'
    if ($raw -match $keyRe) {
        return [regex]::Replace($raw, $keyRe, $newLine)
    }

    # 2) 已有 refs: 块：找到块结束位置（下一个顶格键或文件尾）并插入
    $refsIdx = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^refs:[ \t]*$') { $refsIdx = $i; break }
    }
    if ($refsIdx -ge 0) {
        $blockEnd = $lines.Count
        for ($j = $refsIdx + 1; $j -lt $lines.Count; $j++) {
            if ($lines[$j] -match '^[A-Za-z0-9_.-]+:[ \t]*(#.*)?$') { $blockEnd = $j; break }
        }
        $head = Get-Slice $lines 0 $blockEnd
        $tail = Get-Slice $lines $blockEnd $lines.Count
        return (@($head) + @($newLine) + @($tail) -join "`n")
    }

    # 3) 无 refs 块：文件末尾追加 refs 段
    $note = "# refs: API Key 引用（由 configure-provider.ps1 写入）" + "`n"
    return $raw + $note + 'refs:' + "`n" + $newLine + "`n"
}

# 在 settings.yaml 中设置 agent-default-model: { provider, model }
function Set-AgentDefaultModel {
    param([string]$Path, [string]$ProviderId, [string]$Model)
    $raw  = [System.IO.File]::ReadAllText($Path)
    if (-not $raw.EndsWith("`n")) { $raw += "`n" }
    $lines = @($raw -split "\r?\n")

    $admIdx = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^agent-default-model:[ \t]*$') { $admIdx = $i; break }
    }

    if ($admIdx -lt 0) {
        # 没有 agent-default-model：先处理 flow 风格的行（如 'agent-default-model: { provider: x }'）
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match '^agent-default-model:[ \t]+') { $admIdx = $i; break }
        }
    }

    if ($admIdx -lt 0) {
        # 完全没有：文件末尾追加块
        return $raw + 'agent-default-model:' + "`n" +
               '  provider: ' + (Format-YamlValue $ProviderId) + "`n" +
               '  model: '     + (Format-YamlValue $Model) + "`n"
    }

    $isFlow = ($lines[$admIdx] -match '^agent-default-model:[ \t]+')
    if ($isFlow) {
        # flow 风格整行替换为块风格
        $head = Get-Slice $lines 0 $admIdx
        $tail = Get-Slice $lines ($admIdx + 1) $lines.Count
        return (@($head) + @('agent-default-model:', '  provider: ' + (Format-YamlValue $ProviderId), '  model: ' + (Format-YamlValue $Model)) + @($tail) -join "`n")
    }

    # 块风格：替换块内 provider / model 行，缺失则补齐
    $blockEnd = $lines.Count
    for ($j = $admIdx + 1; $j -lt $lines.Count; $j++) {
        if ($lines[$j] -match '^[A-Za-z0-9_.-]+:[ \t]*(#.*)?$') { $blockEnd = $j; break }
    }
    $block = Get-Slice $lines ($admIdx + 1) $blockEnd
    $out = @('agent-default-model:')
    $hasProvider = $false; $hasModel = $false
    foreach ($ln in $block) {
        if ($ln -match '^\s+provider:') { $out += '  provider: ' + (Format-YamlValue $ProviderId); $hasProvider = $true; continue }
        if ($ln -match '^\s+model:')     { $out += '  model: '     + (Format-YamlValue $Model); $hasModel = $true; continue }
        $out += $ln
    }
    if (-not $hasProvider) { $out += '  provider: ' + (Format-YamlValue $ProviderId) }
    if (-not $hasModel)     { $out += '  model: '     + (Format-YamlValue $Model) }

    $head = Get-Slice $lines 0 $admIdx
    $tail = Get-Slice $lines $blockEnd $lines.Count
    return (@($head) + @($out) + @($tail) -join "`n")
}

# 在 config.json 中设置 profiles.default.preferences.model = "<provider>/<model>"
function Set-LarkModel {
    param([string]$Path, [string]$ModelSpec)
    $json = Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $json.profiles)        { throw "config.json 缺少 profiles 节点（$Path）" }
    if ($null -eq $json.profiles.default) { throw "config.json 缺少 profiles.default 节点（$Path）" }
    $def = $json.profiles.default
    if ($null -eq $def.preferences) {
        $def | Add-Member -NotePropertyName preferences -NotePropertyValue ([pscustomobject]@{})
    }
    $def.preferences | Add-Member -NotePropertyName model -NotePropertyValue $ModelSpec -Force
    return ($json | ConvertTo-Json -Depth 12)
}

function Write-Utf8File {
    param([string]$Path, [string]$Content)
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $enc)
}

# 打印缺失文件的 手工创建指引 + 格式模板（不自动创建）
function Show-ManualTemplate {
    param([string]$Label, [string]$Path)
    Write-Host ''
    Write-Host ("【手工创建指引】{0}：{1}" -f $Label, $Path) -ForegroundColor Yellow
    Write-Host '  请用记事本/编辑器创建该文件（UTF-8 无 BOM），格式模板如下：'
    if ($Path -like '*.credentials.yaml') {
        Write-Host '  ─────────────────────────────'
        Write-Host '  version: 1'
        Write-Host ''
        Write-Host '  refs:'
        Write-Host "    OPENAI_API_KEY: 'sk-你的密钥'"
        Write-Host "    DEEPSEEK_API_KEY: 'sk-你的密钥'"
        Write-Host "    MINIMAX_CN_API_KEY: 'sk-你的密钥'"
        Write-Host '  ─────────────────────────────'
    } elseif ($Path -like '*\settings.yaml') {
        Write-Host '  ─────────────────────────────'
        Write-Host '  agent-default-model:'
        Write-Host '    provider: minimax-cn'
        Write-Host '    model: minimax-m3'
        Write-Host '  ─────────────────────────────'
    } else {
        Write-Host '  ─────────────────────────────'
        Write-Host '  {'
        Write-Host '    "profiles": {'
        Write-Host '      "default": {'
        Write-Host '        "preferences": {'
        Write-Host '          "model": "minimax-cn/minimax-m3"'
        Write-Host '        }'
        Write-Host '      }'
        Write-Host '    }'
        Write-Host '  }'
        Write-Host '  ─────────────────────────────'
        Write-Host '  ⚠️  preferences.model 绝不能是空字符串（否则桥接不解析路由，机器人在飞书全部失败）。'
    }
}

# ---------------------------------------------------------------- 检测
Write-Host '==============================================' -ForegroundColor Cyan
Write-Host ' configure-provider.ps1 · API Key / Provider / Model' -ForegroundColor Cyan
Write-Host '==============================================' -ForegroundColor Cyan
if ($Preview) {
    Write-Host '【预览模式 -WhatIf】只展示将做的改动，不写任何文件。' -ForegroundColor Yellow
} else {
    Write-Host '【真实写入模式】写前会对目标文件做时间戳备份。' -ForegroundColor Green
}
Write-Host ''

$targets = @(
    @{ Label = '.credentials.yaml（凭据）';   Path = $CredFile },
    @{ Label = 'settings.yaml（默认模型）';   Path = $Settings },
    @{ Label = 'config.json（桥接模型）';     Path = $LarkConfig }
)

$missing = @()
foreach ($t in $targets) {
    if (Test-Path $t.Path) {
        Write-Host ("  [√] {0,-24} {1}" -f $t.Label, $t.Path) -ForegroundColor Green
    } else {
        Write-Host ("  [×] {0,-24} {1}  （不存在）" -f $t.Label, $t.Path) -ForegroundColor Red
        $missing += $t.Label
    }
}

if ($missing.Count -eq 3) {
    Write-Host ''
    Write-Host '三个目标文件都不存在。本脚本【不会自动创建】任何文件，请先手工创建：' -ForegroundColor Yellow
    foreach ($t in $targets) { Show-ManualTemplate -Label $t.Label -Path $t.Path }
    exit 1
}

# ---------------------------------------------------------------- 输入
Write-Host ''
Write-Host '--- 选择 Provider ---' -ForegroundColor Cyan
Write-Host '  1) openai'
Write-Host '  2) deepseek'
Write-Host '  3) minimax-cn'
Write-Host '  4) 自定义（OpenAI 兼容 baseURL 网关）'
$choice = Read-Host '  请选择 (1-4)'

switch ($choice) {
    '1' { $ProviderId = 'openai';      $EnvKey = 'OPENAI_API_KEY';      $NeedBaseUrl = $false }
    '2' { $ProviderId = 'deepseek';    $EnvKey = 'DEEPSEEK_API_KEY';    $NeedBaseUrl = $false }
    '3' { $ProviderId = 'minimax-cn';  $EnvKey = 'MINIMAX_CN_API_KEY';  $NeedBaseUrl = $false }
    '4' {
        $ProviderId = Read-Host '  请输入自定义 provider id（如 my-gateway，将作为 agent-default-model.provider 与 "<id>/<model>" 的 id）'
        if ([string]::IsNullOrWhiteSpace($ProviderId)) { throw 'provider id 不能为空' }
        $NeedBaseUrl = $true
        $defaultKey = (($ProviderId -replace '[^A-Za-z0-9]', '_').ToUpper()) + '_API_KEY'
        $EnvKey = Read-Host "  请输入凭据环境变量名（默认 $defaultKey）"
        if ([string]::IsNullOrWhiteSpace($EnvKey)) { $EnvKey = $defaultKey }
    }
    default { throw '无效选择，请重新运行脚本并输入 1-4' }
}

$Model = Read-Host '  请输入模型名（如 minimax-m3 / gpt-4o / deepseek-chat）'
if ([string]::IsNullOrWhiteSpace($Model)) { throw '模型名不能为空' }

$BaseUrl = ''
if ($NeedBaseUrl) {
    $BaseUrl = Read-Host '  请输入 baseURL（如 https://your-gateway.example/v1）'
    if ([string]::IsNullOrWhiteSpace($BaseUrl)) { throw '自定义 provider 必须提供 baseURL' }
}

Write-Host ''
Write-Host '--- 输入 API Key（不回显）---' -ForegroundColor Cyan
$ApiKey = ''
while ([string]::IsNullOrWhiteSpace($ApiKey)) {
    $secure = Read-Host -AsSecureString -Prompt '  请输入 API Key（输入内容不回显；Ctrl+C 可中止）'
    if ($null -eq $secure -or $secure.Length -eq 0) { continue }
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $ApiKey = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}
Write-Host ("  已读取 API Key（长度 {0}，内容不回显）" -f $ApiKey.Length) -ForegroundColor DarkGray

$ModelSpec = "$ProviderId/$Model"

# ---------------------------------------------------------------- 预览/写入
$stamp = Get-Date -Format 'yyyyMMddTHHmmss'
Write-Host ''
Write-Host '--- 计划写入 ---' -ForegroundColor Cyan
Write-Host ("  provider : {0}" -f $ProviderId)
Write-Host ("  model    : {0}" -f $Model)
if ($NeedBaseUrl) { Write-Host ("  baseURL  : {0}" -f $BaseUrl) }
Write-Host ("  桥接 model（preferences.model）: {0}" -f $ModelSpec)
Write-Host ''

$wrote = @()
foreach ($t in $targets) {
    if (-not (Test-Path $t.Path)) {
        Write-Host ("  [跳过] {0} 不存在（不自动创建，模板见下方）" -f $t.Label) -ForegroundColor DarkYellow
        continue
    }
    Backup-File -Path $t.Path -Stamp $stamp
    if ($t.Path -eq $CredFile) {
        $new = Set-CredentialsRef -Path $t.Path -Key $EnvKey -Value $ApiKey
        if (-not $Preview) { Write-Utf8File -Path $t.Path -Content $new }
        Write-Host ("  [写入] {0} → refs.{1}" -f $t.Label, $EnvKey) -ForegroundColor Green
        $wrote += $t.Label
    } elseif ($t.Path -eq $Settings) {
        $new = Set-AgentDefaultModel -Path $t.Path -ProviderId $ProviderId -Model $Model
        if (-not $Preview) { Write-Utf8File -Path $t.Path -Content $new }
        Write-Host ("  [写入] {0} → agent-default-model: {1}" -f $t.Label, $ModelSpec) -ForegroundColor Green
        $wrote += $t.Label
    } else {
        try {
            $new = Set-LarkModel -Path $t.Path -ModelSpec $ModelSpec
            if (-not $Preview) { Write-Utf8File -Path $t.Path -Content $new }
            Write-Host ("  [写入] {0} → profiles.default.preferences.model = {1}" -f $t.Label, $ModelSpec) -ForegroundColor Green
            $wrote += $t.Label
        } catch {
            Write-Host ("  [失败] {0}：{1}" -f $t.Label, $_.Exception.Message) -ForegroundColor Red
            Write-Host '         该文件未修改，请手工编辑（模板见下）或先在 DSH GUI Models 页保存一次。' -ForegroundColor DarkYellow
        }
    }
}

# ---------------------------------------------------------------- 缺失文件模板
foreach ($t in $targets) { Show-ManualTemplate -Label $t.Label -Path $t.Path }

# ---------------------------------------------------------------- 收尾
if ($Preview) {
    Write-Host ''
    Write-Host '【预览结束】未做任何修改。确认无误后去掉 -WhatIf 重新运行。' -ForegroundColor Yellow
    exit 0
}

Write-Host ''
Write-Host '✅ 配置写入完成（如中途有 [跳过] / [失败]，请按上面的模板手工补齐）。' -ForegroundColor Green
Write-Host '   使配置生效：'
Write-Host '     cd <仓库根目录>'
Write-Host '     .\bot-start.ps1 -Restart'
Write-Host ''
Write-Host '⚠️  提醒：%USERPROFILE%\.dsh-lark\config.json 的 preferences.model 绝不能是空字符串，' -ForegroundColor Yellow
Write-Host '    否则桥接不解析路由、机器人在飞书全部失败（2026-08-28 真实事故）。'
Write-Host '    COC_SESSION_ROOT 若覆盖，必须仍在 DSH 工作区（仓库根目录）之内。' -ForegroundColor Yellow
exit 0
