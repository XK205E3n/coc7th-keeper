# CoC7th 守密人 · 飞书跑团（coc7th-keeper）

> 在飞书里跑《克苏鲁的呼唤》第七版（CoC7th），1-2 人友好。AI 担任守密人（KP），玩家只需要在飞书群里发 `/coc ...` 指令。

DeepSeek Harness 常驻后台 + 飞书群消息（dsh-lark-bot 桥接）+ `coc7th-keeper` skill —— 让 AI 在飞书群里担任守密人。玩家**不需要**安装任何桌面工具；而你（部署者）**不需要**在仓库里配置任何密钥——**发布版不捆绑任何 API Key / Provider / 模型，全部由你自己配置**（见 [配置你自己的 API Key / Provider / 模型](#配置你自己的-api-key--provider--模型)）。

---

## 目录

- [简介与架构](#简介与架构)
- [功能与隐私承诺](#功能与隐私承诺)
- [依赖清单](#依赖清单)
- [快速开始](#快速开始)
- [配置你自己的 API Key / Provider / 模型](#配置你自己的-api-key--provider--模型)
- [目录结构](#目录结构)
- [版权与分发](#版权与分发)
- [路线图](#路线图)
- [开发与测试](#开发与测试)

---

## 简介与架构

```
飞书群消息  ──►  dsh-lark-bot（WebSocket 长连接）
                       │
                       ▼ 注入消息（含可信频道上下文 chat_type：p2p / group / topic）
              DeepSeek Harness 后台 Agent（本机进程）
                       │
                       ▼ 加载
              coc7th-keeper skill
                       │
                       ▼ 调用
              scripts/*.py（加密安全随机数 + JSON；经 .dsh/bin/coc.cmd | coc.ps1 统一入口）
                       │
                       ▼ 输出
              Markdown 中文叙述（跑团数据落 coc-session/<房间>/）
                       │
                       ▼ dsh-lark-bot 自动转飞书卡片
               飞书群消息
```

- **Agent 不处理飞书协议**——消息注入、卡片渲染、多群隔离全部由 dsh-lark-bot 承担。
- **Agent 按频道上下文执行隐私分支**——`chat_type` 决定当前回复会发到私聊还是跑团群，skill 据此执行隐私铁律（见下）。

---

## 功能与隐私承诺

### 功能

- ✅ **飞书即一切**：玩家在飞书群发 `/coc ...`，机器人把消息注入 DeepSeek Harness 中的 Agent，Agent 加载 skill 后调用 Python 规则脚本，再以飞书卡片回传结果。整个过程不需要打开桌面 GUI。
- ✅ **完整的 CoC7th 规则**：build、技能检定、对抗、幸运、理智、战斗、重伤。
- ✅ **加密安全随机数**：基于 Python `secrets.SystemRandom`，每次投骰写入审计日志（`dice.log`，仅追加、不可篡改）。
- ✅ **AI 守密人**：守密人十条 + 场景自适应风格（神秘冷峻 / 紧张紧凑 / 慢热会话）。
- ✅ **内置模组**：《惊魂》（官方入门）、《玩具跳着舞蹈来》（第三方授权，本地使用）。
- ✅ **复用 DSH 社区飞书集成**：`PlutoKeating/dsh-lark-bot` —— 扫码建应用、自更新、群聊隔离、Markdown 卡片。

### 隐私承诺（最高优先级）

> 完整的隐私铁律见 skill 内 `SKILL.md` §2「频道与隐私铁律」。核心承诺：

- **跑团群聊（group / topic）永不显示 KP 数据**：守密人旁注、内部提示、（PL 不可见）标注、未揭示的线索与真相、隐藏 NPC / 怪物数值、检定失败后果剧透、`kp-notes.md` 摘录、机器绝对路径，一律禁止出现在群聊输出。
- **KP 数据只在守密人私聊（p2p）且确认守密人身份、明确要求时**展示概要，并且**绝不回流到任何群聊**——私聊看到的就留在私聊。
- **检定失败只叙述检定者没能看出更多**（例如「你仔细查看，没能从中看出更多端倪」），绝不解释「其实你没发现 X、线索在 Y 处」，也绝不断言「没有异常」（断言"没有"同样是剧透）。
- **守密人笔记只写本地 `kp-notes.md`**（`/coc kp-note`），群聊只回复「已记录」，绝不回显内容。
- **路径一律相对形式**：群聊输出使用 `coc-session/<房间>/...`，绝不出现 `D:\...` / `C:\Users\...` 机器绝对路径。

---

## 依赖清单

| 依赖 | 版本 | 说明 |
|---|---|---|
| DeepSeek Harness Desktop | 0.1.x+ | 后台运行环境（Agent 宿主） |
| dsh-lark-bot | latest（社区插件） | 飞书桥接：扫码建应用、WebSocket 长连接、卡片渲染、多群隔离 |
| Node.js | ≥ 22 | DSH 自带 |
| Python | 3.11+ | DSH 自带；规则脚本运行时 |
| LLM API Key / Provider / Model | 用户自备 | 见 [配置章节](#配置你自己的-api-key--provider--模型) |

> ⚠️ **发布版仍依赖 DeepSeek Harness 后台**：本项目**不是独立服务**，而是运行在 DSH 里的 skill + 文档 + 工具脚本。没有 DSH 后台（`dsh --profile dsh-lark`），飞书机器人无法工作。

---

## 快速开始

> 完整部署手册见 skill 内 `DEPLOY.md`（本仓库 `.dsh/skills/coc7th-keeper/DEPLOY.md`）。

```powershell
# 1. 安装飞书桥接（一条命令，会引导扫码）
npx dsh-lark-bot@latest setup --profile dsh-lark

# 2. 启动守密人后台（首次运行打印飞书登录二维码）
dsh --profile dsh-lark
#    或使用本项目一键脚本：.\bot-start.ps1（后台常驻 + 健康检查 + 崩溃自愈可选）

# 3. 在飞书 App 建跑团群 + 邀请机器人（群设置 → 群机器人 → 添加你的 dsh-lark-bot）

# 4. 先配好模型（见下节），然后在群里（守密人）发：
/coc init demo --module the-haunting --kp 你的飞书名

# 5. 玩家加入：
/coc join
/coc use-pregen theron-quist
```

详细步骤、故障排查与卸载见 `DEPLOY.md`；玩家视角说明书见 `USER_GUIDE.md`。

---

## 配置你自己的 API Key / Provider / 模型

发布版**不捆绑任何凭据与模型**，运行前你必须自行配置。有两条途径，任选其一：

### 途径 A：飞书内指令（推荐，最快）

dsh-lark-bot 内置以下指令，直接在飞书私聊机器人即可：

| 指令 | 作用 |
|---|---|
| `/config` | 查看 / 修改当前运行配置总览 |
| `/model` | 切换模型（例如 `minimax-cn/minimax-m3`） |
| `/provider` | 切换 / 查看模型供应商 |
| `/key` | 配置 API Key——通过**安全表单**收集，密钥**不进入聊天记录** |

> 密钥在群聊里发会被记录，务必只通过 `/key` 的安全表单提交。

### 途径 B：本地脚本（适合批量 / 离线 / 想直接改配置文件）

在本仓库目录用 PowerShell 运行交互式脚本 `tools/configure-provider.ps1`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\configure-provider.ps1 -WhatIf   # 先预览
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\configure-provider.ps1          # 真实写入
```

脚本会引导你选择 provider（openai / deepseek / minimax-cn / 自定义 baseURL）、输入模型名与 API Key（`Read-Host -AsSecureString`，**绝不回显**），并自动修改三个文件：

| 文件 | 写入内容 |
|---|---|
| `%USERPROFILE%\.dsh\.credentials.yaml` | `refs.<API_KEY>`（如 `MINIMAX_CN_API_KEY`） |
| `%USERPROFILE%\.dsh\settings.yaml` | `agent-default-model: { provider, model }` |
| `%USERPROFILE%\.dsh-lark\config.json` | `profiles.default.preferences.model`（`"<provider>/<model>"`） |

写前会对每个文件各生成一份**时间戳备份**（如 `config.json.bak-YYYYMMDDTHHMMSS`）；目标文件不存在时脚本**不会自动创建**，只打印手工创建指引与格式模板。

改完后重启机器人使其生效：

```powershell
.\bot-start.ps1 -Restart
```

> ⚠️ **`preferences.model` 绝不能是空字符串**：`%USERPROFILE%\.dsh-lark\config.json` 里
> `profiles.default.preferences.model` 一旦是 `""`，桥接的模型解析链会被空串短路（`??` 不跳过空串），
> 不解析路由 → 机器人在飞书**全部失败**（2026-08-28 真实事故，见 `.dsh/DIAGNOSIS-20260828.md`）。
> 配置工具与文档都保证写入 `"<provider>/<model>"`，请勿手工清空。
>
> ⚠️ **`COC_SESSION_ROOT` 若覆盖必须仍在 DSH 工作区内**（即仓库根目录或其子目录）：脚本 wrapper
> 默认把房间数据写到 `<workspace>\coc-session`，路径全在工作区内、DSH workspace-write 自动放行；
> 一旦把会话目录指到工作区之外，sandbox 会视为跨工作区写而触发 plan-gate，跑团会断档。

---

## 目录结构

```
<仓库根目录>（= DSH 工作区）
├── README.md / CHANGELOG.md / VERSION / LICENSE
├── bot-start.ps1 / bot-stop.ps1         # 机器人一键启停（后台常驻 + 健康检查）
├── 一键开启.bat / 一键关闭.bat          # 双击版启停
├── .dsh/
│   ├── bin/
│   │   ├── coc.cmd / coc.ps1            # 工作区统一脚本入口（所有 Python 调用必须走这里）
│   │   └── dsh.cmd                      # 固定 DSH_HOME 的 dsh CLI 包装
│   └── skills/coc7th-keeper/            # skill 权威副本（单一工作区布局，唯一部署来源）
│       ├── SKILL.md                     #   守密人系统提示词（含 §2 隐私铁律）
│       ├── README.md / DEPLOY.md / USER_GUIDE.md
│       ├── scripts/                     #   Python 规则脚本（roll/check/build/sanity/combat/room/...）
│       ├── modules/                     #   模组目标目录（COC_MODULES_DIR 锚点，全部在工作区内）
│       │   ├── the-haunting/            #     《惊魂》（Chaosium 官方免费，随仓库分发）
│       │   └── toy-dancer-comes/        #     《玩具跳着舞蹈来》（第三方授权，随仓库分发，作者条款见模块内 README）
│       ├── references/                  #   规则速查 + 预渲染缓存（help/modules）
│       ├── assets/quickstart.md         #   5 分钟快速上手
│       └── bridge/README.md             #   飞书接入说明（已选定 dsh-lark-bot）
├── tools/
│   └── configure-provider.ps1           # 本地配置 API Key / Provider / Model（自动备份）
├── coc-session/                         # 跑团运行时数据（不入库）
└── 模组/                                # 模组原 PDF 存放（不入库）
```

---

## 版权与分发

- **本项目（skill 脚本、文档与工具）**：MIT 协议，© 2026 XK205E3n —— 见 [LICENSE](LICENSE)。
- **《惊魂》（`the-haunting`）**：Chaosium 官方免费 quickstart 短模组的**爱好者改编**（公平使用范围），随本仓库分发。
- **《玩具跳着舞蹈来》（`toy-dancer-comes`）**：作者 **Yukishiro** 的第三方授权模组，**按项目所有者决定随本仓库分发**；作者原条款（禁止商业用途、禁止修改后二次发布、欢迎非盈利衍生创作）完整保留于模块内 `README.md`，使用者请自行确认授权范围。**模组原版 PDF 不进入仓库**（见下）。
- **模组原版 PDF 与转换源稿（`模组/` 目录）**：为购买/授权所得文件，**不入库、不随发布分发**；仅本地使用。
- **飞书集成**：`dsh-lark-bot`（AGPLv3）—— [PlutoKeating/dsh-lark-bot](https://github.com/PlutoKeating/dsh-lark-bot)。

---

## 模组目录约定（内置与未来导入）

- **所有模组（内置 + 未来新增/导入）一律放在工作区**：`.dsh/skills/coc7th-keeper/modules/<id>/`，随仓库分发。
- 新增模组 = 在该目录下创建 `meta.json`（schema=`coc7-module/v1`，含 `id`/`number`/`cn`/`name`/`summary`/`players`/`duration`/`tags`）+ `plot.md`（PL 视角）+ `kp-notes.md`（守密人真相，绝不外发）+ 可选 `clues.md`/`npcs.json`/`monsters.json`/`pregens/`/`handouts/`；脚本自动扫描收录，无需改代码。
- 模组目标目录由 `COC_MODULES_DIR` 环境变量锚定（默认 `<skill-root>/modules`）；**若重定位，必须仍位于 DSH 工作区内**（否则 sandbox 视为跨工作区写而触发审批）。
- 新增/修改模组后执行 `.\.dsh\bin\coc.ps1 build_all_cache` 重生 `/coc modules` 缓存。
- 原版 PDF 等授权源材料放 `模组/`（不入库），转换产物放 `modules/<id>/`（入库）。

---

## 路线图

- **本地 Web 历史查看器**：接口已预留（`dsh web` 可查看对话历史、房间文件、骰子审计），**暂不开发**。
- **飞书是唯一前端**：所有玩家交互走飞书；桌面 GUI 只用于部署与调试，不是日常入口。

---

## 开发与测试

不需要飞书即可验证脚本（walkthrough 冒烟测试，全部走工作区统一入口）：

```powershell
# 冒烟：投骰 / 模组列表 / 技能检定
.\.dsh\bin\coc.ps1 roll 1d100 --by dev --why "smoke"
.\.dsh\bin\coc.ps1 modules list
.\.dsh\bin\coc.ps1 check skill "Spot Hidden" 50 --by dev --room demo --why "smoke"

# 重生预渲染缓存（改了 help.py 或模组 meta 之后必须跑）
.\.dsh\bin\coc.ps1 build_all_cache
```

更完整的脚本级测试命令见 `.dsh/skills/coc7th-keeper/README.md` 的「测试」一节。
