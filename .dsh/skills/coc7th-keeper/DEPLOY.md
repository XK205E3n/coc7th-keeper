# 部署手册 · CoC7th 飞书跑团

> 从零开始，把 CoC7th 跑团装到飞书群。全程 9 个步骤，预计 15-20 分钟。
> 文中的 `<仓库根目录>` 指本项目克隆/解压所在目录（即 DSH 工作区）。

---

## 第 1 步：检查前置

开始之前请确认：

- ✅ **DeepSeek Harness 已装**（本手册基于 DSH Desktop 0.1.1-rc+）
- ✅ **Node.js ≥ 22.19**（DSH 自带，无需额外装）
- ✅ **Python 3.11+**（DSH 自带；PowerShell 里 `python --version` 应可正常显示）
- ✅ 一个 **飞书账号**（手机端 / 电脑端都行）
- ✅ 一台**保持开机** 的机器（推荐你的台式机或笔记本）
- ✅ **一个可用的 LLM API Key**（发布版不捆绑凭据，见第 5 步）

> 💡 **测试规模**：本方案对 **1-2 人** 跑团最优。一个飞书群就能开团。

---

## 第 2 步：装飞书机器人插件（dsh-lark-bot）

打开 PowerShell（建议在 `<仓库根目录>` 下）：

```powershell
npx dsh-lark-bot@latest setup --profile dsh-lark
```

> 这一步会自动：
> 1. 下载 dsh-lark-bot 包到本地
> 2. 装到 `dsh-lark` 这个 profile
> 3. 默认装上「安全网守护」（崩溃自愈）
> 4. 准备首次扫码

接着启动 DSH：

```powershell
dsh --profile dsh-lark
```

**首次启动**会在终端打印一个**飞书登录二维码**。

### 用手机飞书 App 扫码

> 📱 **什么是扫码**？
> 扫码 = 让 dsh-lark-bot 以你的飞书身份去开放平台自动建应用、配权限、连 WebSocket。
> 它不会读你的聊天记录，也不会以你的身份发消息；授权后你可以在飞书开放平台随时撤销。

打开飞书 App → 扫一扫 → 确认授权。

授权成功后，DSH 后台保持运行。私聊机器人已经能发消息。

> 💡 **扫码 vs 手动建应用**：
> - 扫码：30 秒搞定，基础权限秒批
> - 手动：要 30-60 分钟，部分权限审核 1-3 天
>
> 99% 的用户用扫码就够了。

---

## 第 3 步：建跑团群 + 邀请机器人

1. 在飞书 App 里 **发起群聊**
2. 选 1-2 位朋友（CoC 跑团 1-2 人足够；原作 4 人设计已精简）
3. 给群起名（如「**周末跑团·惊魂**」）
4. 进群后：**群设置** → **群机器人** → **添加机器人** → 选你的 dsh-lark-bot
5. （可选）**群管理** → 设为「免 @ 触发」

**1 个飞书群 = 1 个跑团房间**。

---

## 第 4 步：确认 coc7th-keeper skill 已在工作区（v0.2.0 单一工作区布局）

DSH 启动时扫描 `<当前工作目录>/.dsh/skills/` 寻找 skill。本项目的一键启动脚本
`bot-start.ps1` 已通过 `DSH_LARK_WORKSPACE=<仓库根目录>` 把 dsh-lark 的 agent 工作区
**锁定到仓库根目录**，因此 Agent 加载的是工作区内**唯一权威副本**：

```
<仓库根目录>\.dsh\skills\coc7th-keeper\SKILL.md
```

验证 skill 已被加载：在飞书里私聊机器人发 `/coc help`（或群聊发 `/coc modules`），
能返回指令列表即成功。

> 📌 **v0.2.0 起不再复制到 `~/.dsh/skills/`**：旧手册的「跨工作区共享 = 复制到用户级目录」
> 做法已废弃。用户目录下可能残留历史副本（v0.1.x 时代的遗留），它**不参与部署**、无需也无法同步；
> 正常运维无须触碰；如确需清理，可用 `tools/neutralize-legacy-skill.ps1`（发布工具目录提供，非正常运行必需）。

---

## 第 5 步：配置 API Key / Provider / 模型（首次必做）

**发布版不捆绑任何 API Key / Provider / 模型**，运行前必须自行配置。两条途径任选：

### 途径 A：飞书内指令（最快）

直接在飞书**私聊**机器人：

| 指令 | 作用 |
|---|---|
| `/config` | 查看 / 修改当前运行配置总览 |
| `/model` | 切换模型（如 `minimax-cn/minimax-m3`） |
| `/provider` | 切换 / 查看模型供应商 |
| `/key` | 配置 API Key——通过**安全表单**收集，密钥**不进入聊天记录** |

> 密钥请只通过 `/key` 的安全表单提交，不要在群聊 / 私聊正文里直接发。

### 途径 B：本地脚本（适合离线 / 批量 / 直接改配置文件）

在 `<仓库根目录>` 打开 PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\configure-provider.ps1 -WhatIf   # 先预览
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\configure-provider.ps1          # 真实写入
```

脚本会引导选择 provider（openai / deepseek / minimax-cn / 自定义 baseURL）、输入模型名与
API Key（`Read-Host -AsSecureString`，**绝不回显**），并自动修改三个文件：

| 文件 | 写入内容 |
|---|---|
| `%USERPROFILE%\.dsh\.credentials.yaml` | `refs.<API_KEY>`（如 `MINIMAX_CN_API_KEY`） |
| `%USERPROFILE%\.dsh\settings.yaml` | `agent-default-model: { provider, model }` |
| `%USERPROFILE%\.dsh-lark\config.json` | `profiles.default.preferences.model`（`"<provider>/<model>"`） |

写前会对每个文件各生成一份**时间戳备份**（如 `config.json.bak-YYYYMMDDTHHMMSS`）；
目标文件不存在时脚本**不会自动创建**，只打印手工创建指引与格式模板。

配置完成后重启机器人使配置生效：

```powershell
.\bot-start.ps1 -Restart
```

> ⚠️ **`preferences.model` 绝不能是空字符串**：`%USERPROFILE%\.dsh-lark\config.json` 里
> `profiles.default.preferences.model` 一旦是 `""`，桥接的模型解析链会被空串短路（`??` 不跳过空串），
> 不解析路由 → 机器人在飞书**全部失败**（2026-08-28 真实事故，修复与诊断见 `.dsh/DIAGNOSIS-20260828.md`）。
> 一定要写 `"<provider>/<model>"` 这种非空值。
>
> ⚠️ **`COC_SESSION_ROOT` 若覆盖必须仍在 DSH 工作区内**（仓库根目录或其子目录）：wrapper 默认把
> 房间数据写到 `<仓库根目录>\coc-session`，路径全在工作区内、DSH workspace-write 自动放行；
> 指到工作区之外会被 sandbox 视为跨工作区写而触发 plan-gate，跑团会断档。

---

## 第 6 步：在飞书群里开团

在群里（守密人 KP）发：

```
/coc init demo --module the-haunting --kp 你的飞书名
```

预期飞书卡片回复：

> 🏠 **房间已建**：`demo`
> 📜 **剧本**：惊魂
> 👤 **守密人**：xxx
> ⏰ **时间**：xxx

如果 bot 没有响应：

1. 在指令前 @ 一下 bot：`@coc-bot /coc init demo ...`
2. 检查 DSH 终端是否还在运行（或 `.\bot-start.ps1 -Status`）
3. 检查 bot 是否被邀请到群（群设置 → 群机器人）
4. 复查第 5 步的模型配置是否生效（重点：`preferences.model` 非空）

---

## 第 7 步：玩家加入 + 选角色

每位玩家在群里发：

```
/coc join
/coc use-pregen theron-quist
```

或：

```
/coc join
/coc build
```

agent 会自动：

- 用飞书发送者名作为角色名
- 把预制角色（或现场生成的）写入 `players/<名字>.json`
- 在飞书卡片里展示角色卡

---

## 第 8 步：守密人开场

```
/coc scene 大堂
```

agent 加载模组开场白，描述场景。

---

## 第 9 步：跑团进行中

| 谁 | 指令 | 用途 |
|---|---|---|
| 全部 | `/coc roll 1d100 --why ...` | 任意投骰 |
| 全部 | `/coc check "Spot Hidden" --why ...` | 技能检定 |
| 全部 | `/coc luck` | 幸运检定 |
| 全部 | `/coc san 3 --why ...` | 理智损失 |
| 玩家 | `/coc attack ... --target ...` | 攻击 |
| 玩家 | `/coc say <台词>` | 角色发言 |
| 守密人 | `/coc reveal <编号>` | 解锁线索 |
| 守密人 | `/coc npc <名>` | NPC 速查 |
| 守密人 | `/coc kp-note ...` | 仅守密人笔记（群聊只回「已记录」，不回显内容） |

完整指令清单见 `assets/quickstart.md` 或 `SKILL.md`。

---

## 隐私说明（最高优先级）

> 完整铁律见 `SKILL.md` §2「频道与隐私铁律」。一句话版本：

- **跑团群聊（group / topic）零 KP 数据**：守密人旁注、（PL 不可见）标注、内部提示、
  未揭示线索与真相、隐藏 NPC/怪物数值、检定失败后果剧透、`kp-notes` 摘录、机器绝对路径
  一律禁止出现在群聊输出。
- **KP 数据只在守密人私聊（p2p）且确认守密人身份、明确要求时**展示概要，**绝不回流任何群聊**。
- **检定失败只叙述检定者没能看出更多**（如「你仔细查看，没能从中看出更多端倪」），**绝不断言「没有异常」**（断言"没有"= 剧透）。
- **`/coc kp-note` 只写本地 `kp-notes.md`**，群聊只回复「已记录」。
- **路径一律相对形式**（如 `coc-session/demo/players/alice.json`），绝不出现 `D:\...` / `C:\Users\...`。

---

## 测试（不需要飞书）

> **桥接 worktree 提示**：dsh-lark-bot 会把每个群会话放在隔离 git worktree 里运行（设计特性）。`coc-session/`（存档）不入 git，需要运行 `tools/fix-bridge-worktrees.ps1` 把运行数据以 directory junction 挂载进各 worktree，并同步最新代码。**首次部署、新建群、`/reset`、推送新版本后都要重跑一次**（详见根 `README.md`「桥接 worktree 与运行数据」）。

> 所有 python 调用必须走工作区统一入口 `.dsh\bin\coc.cmd` / `.dsh\bin\coc.ps1`
> （wrapper 自动设置 `COC_SESSION_ROOT=<仓库根目录>\coc-session`、`COC_MODULES_DIR=<skill-root>\modules`，
> 路径全在工作区内，DSH workspace-write 自动放行、零 plan-gate）。

```powershell
cd <仓库根目录>
.\.dsh\bin\coc.ps1 room init demo --module the-haunting --kp dev
.\.dsh\bin\coc.ps1 room join demo alice
.\.dsh\bin\coc.ps1 room build demo alice
.\.dsh\bin\coc.ps1 roll 1d100 --by alice --why "test"
.\.dsh\bin\coc.ps1 check skill "Spot Hidden" 60 --by alice --room demo --why "test"
.\.dsh\bin\coc.ps1 sanity check --player-file "demo/players/alice.json" 3 --room demo --why "test"
.\.dsh\bin\coc.ps1 room audit demo --last 5
.\.dsh\bin\coc.ps1 build_all_cache
```

---

## 新增 / 导入模组（工作区约定）

> **所有模组（内置 + 未来新增/导入）一律放在工作区**：`.dsh/skills/coc7th-keeper/modules/<id>/`，随仓库分发。

1. 在 `modules/<id>/` 下创建：
   - `meta.json`（schema=`coc7-module/v1`，含 `id` / `number` / `cn` / `name` / `summary` / `players` / `duration` / `tags`）
   - `plot.md`（PL 视角剧本）、`kp-notes.md`（守密人真相，**绝不外发**）
   - 可选：`clues.md` / `npcs.json` / `monsters.json` / `pregens/` / `handouts/`
2. 脚本自动扫描收录，无需改代码；执行 `.\.dsh\bin\coc.ps1 build_all_cache` 重生 `/coc modules` 缓存。
3. 模组目标目录由 `COC_MODULES_DIR` 锚定（默认 `<skill-root>/modules`）；**重定位必须仍位于 DSH 工作区内**。
4. 原版 PDF 等授权源材料放仓库根 `模组/`（不入库）；转换产物放 `modules/<id>/`（入库）。
5. 第三方模组请先确认分发授权；作者条款保留在模块内 `README.md`。

---

## 故障排查

| 现象 | 原因 | 解决 |
|---|---|---|
| 终端找不到 `dsh` 命令 | DSH Desktop 没把 CLI 加到 PATH | 使用 `<仓库根目录>\.dsh\bin\dsh.cmd` 包装；或全局 npm 装 |
| `/coc init` 后无反应 | bot 没连上飞书 / DSH 未启动 / bot 未被邀请 / 模型未配置 | 检查 DSH 进程（`.\bot-start.ps1 -Status`）；检查群机器人列表；复查第 5 步 |
| 机器人每条消息都回「⚠️ Agent 运行失败」 | `~/.dsh-lark/config.json` 的 `preferences.model` 为空字符串（2026-08-28 事故） | 写入 `"provider/model"` 非空值（用 `tools/configure-provider.ps1` 或 `/model`），然后 `.\bot-start.ps1 -Restart` |
| Agent 没加载 skill | skill 路径不在扫描范围 | 确认 `SKILL.md` 在 `<仓库根目录>\.dsh\skills\`；确认 `bot-start.ps1` 设置了 `DSH_LARK_WORKSPACE=<仓库根目录>`；**不要**再用 `~/.dsh/skills/` 副本 |
| bot 说「找不到房间存档 / 没有 coc-session」 | 桥接把会话跑在隔离 git worktree 里，gitignored 的运行数据不在 worktree | 在普通 PowerShell 运行 `.\tools\fix-bridge-worktrees.ps1`（为 worktree 挂载 `coc-session` junction + 同步 origin/master），然后群里 `/reset` |
| bot 行为像旧版本 | worktree 是创建时的静态检出，代码更新后未同步 | 重跑 `.\tools\fix-bridge-worktrees.ps1` 或手动 `git -C <worktree> fetch origin && git -C <worktree> merge origin/master` |
| `/key` 等配置指令没反应 | dsh-lark-bot 版本过旧 | `npx dsh-lark-bot@latest setup --profile dsh-lark` 更新，或飞书内 `/upgrade` |
| 投骰显示 0 伤害 | DB（伤害加值）计算错 | 检查角色卡 `attributes.STR + attributes.SIZ` |
| HP 异常高 / 低 | 角色 build 算法不同 | 用 `/coc build` 重新生成 |
| 玩家飞书名冲突 | 同名玩家 | 让冲突玩家改名后重新 join |
| 飞书卡片显示原始 JSON | dsh-lark-bot 未启用 Markdown | 升级 dsh-lark-bot 到最新版 |
| npx 第一次超时 | 网络慢 / npm cache 写权限问题 | 重试或换网络 |

---

## 进阶配置

### 共享 coc-session 目录（多 DSH 实例）

默认情况下 DSH 把房间数据写到当前工作目录下的 `coc-session/`。本 skill 已内置
**workspace 统一调用入口** `.dsh/bin/coc.cmd` / `.dsh/bin/coc.ps1`，
自动锁定 `COC_SESSION_ROOT=<仓库根目录>\coc-session`，**所有 python 脚本路径
都在工作区内**，DSH workspace-write 权限自动放行，无需人工审批。

如果要把玩家房间集中管理（多 DSH 实例共享），只需设置一个环境变量：

```powershell
$env:COC_SESSION_ROOT = "D:\CoC\rooms"
dsh --profile dsh-lark
```

> 此环境变量必须由 DSH 进程继承。最简单方式：写一个启动脚本 `start-coc.ps1`：
> ```powershell
> $env:COC_SESSION_ROOT = "D:\CoC\rooms"
> dsh --profile dsh-lark
> ```
>
> ⚠️ **注意**：COC_SESSION_ROOT 路径必须**仍然位于 DSH workspace 之内**（即仓库根目录或其子目录），否则 sandbox 视为跨工作区写而触发 plan-gate。

### 多房间（多个飞书群）

每个飞书群 = 一个房间。dsh-lark-bot 自动按群隔离 Agent 会话。
不同群可以同时跑不同的剧本（`/coc init <不同房间号> --module ...`）。

### 守密人 Web 可视化（仅调试用）

```powershell
dsh web --profile dsh-lark
```

浏览器访问本地地址可以看到：
- 对话历史
- 工作区文件（`log.md` / `dice.log` / 角色卡）
- 房间状态

> 玩家不需要看这个；玩家全在飞书操作。

### 审计与可回放

每个房间的 `dice.log` 是仅追加 NDJSON，含时间戳、玩家、表达式、投骰、判定。可在 PowerShell 查看：

```powershell
Get-Content <仓库根目录>\coc-session\demo\dice.log | ConvertFrom-Json | Select-Object -Last 20 | Format-Table
```

公平性可独立验证。

### 存档与读档

```
/coc save    # 生成 snapshot-*.json（群聊只回显相对路径）
# ... 关电脑 ...
/coc load <快照路径>   # 恢复
```

---

## 卸载

```powershell
# 移除 dsh-lark-bot
npx dsh-lark-bot@latest uninstall --profile dsh-lark

# 移除 skill（连同仓库根目录一起删除即可）
Remove-Item -Recurse "<仓库根目录>"
```

---

## 下一步

- 玩家说明书：`USER_GUIDE.md`
- 5 分钟快速上手：`assets/quickstart.md`
- 规则速查：`references/`
- 项目总览与配置接口：仓库根目录 `README.md`
