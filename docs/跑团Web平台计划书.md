# 跑团 Web 平台计划书（单人 / 多人联机 · DND / COC）

> 版本：v0.1（草案）｜ 日期：2026-08-31
> 参考对象：[DiceFrame](https://diceframe.com/)（开源自托管 AI 跑团平台，AGPL-3.0）
> 复用基础：本仓库 `coc7th-keeper`（CoC7th 守密人 skill，飞书 + DeepSeek Harness）

---

## 1. 项目概述

### 1.1 目标

在**复用当前项目（coc7th-keeper）后端规则逻辑**的基础上，参考 DiceFrame 的产品形态，开发一套**自托管的 Web 跑团平台**：

- **单人模式**：一个人 + AI 守密人（KP/GM）在浏览器里跑 DND / COC。
- **多人联机模式**：GM 建桌，玩家通过邀请链接加入，同一张"桌子"实时同步，AI 担任守密人。
- **预留多人联机接口**：架构上从第一天就按"多客户端 + 服务端权威"设计，后续可平滑接入群聊 Bot（飞书 / QQ）、WebRTC 直连等。

### 1.2 范围

| 做 | 不做（本期） |
|---|---|
| 复用并服务化现有 CoC7th 规则引擎（build / 检定 / 理智 / 战斗 / 重伤） | 不追求 UI 美术（用户明确：可忽略，按需后补） |
| 参考 DiceFrame 的 WebUI 结构（总览 / 游玩 / 角色 / 内容 / 管理） | 不复制 DiceFrame 代码（AGPL 许可约束，见 §8） |
| 单人 + 多人回合制联机（SSE 实时同步） | 本期不做语音 / 生图 / 插件商店（预留扩展点即可） |
| 预留群聊 Bot 桥接、WebRTC 直连接口 | 不做移动端 App（后续可评估） |

### 1.3 关键结论（先行摘要）

1. **DiceFrame 的核心逻辑**：叙事与状态分离、骰子与规则分离、服务端权威 + SSE 实时同步、平台无关的 Bot Bridge。这些设计理念可直接借鉴。
2. **当前项目最大资产**：完整 CoC7th 规则脚本（比 DiceFrame 内置的"轻量 CoC"更完整）、加密安全骰子 + 不可篡改审计、隐私铁律（KP 数据分级）。
3. **推荐方案**：**方案 B —— 复用 coc7th-keeper 规则引擎 + 自建轻量 Web 服务与前端**（详见 §4），而非直接 fork DiceFrame。
4. **多人联机**：中心服务器模式（HTTP + SSE）为主，预留 WebRTC 直连与群聊 Bot 桥接两个扩展口；外网部署用内网穿透或云服务器（§6 对比）。

---

## 2. 参考对象审核：DiceFrame

> 审核来源：官网 https://diceframe.com/ 、官方文档库 `diceframe/diceframe-content`（guide / deploy / bot-bridge-core / plugin-development）、主仓库 `diceframe/diceframe` README 与 `docs/zh/`（rules-and-dice / direct-connect）。

### 2.1 网站定位与核心逻辑

DiceFrame 是**开源、自托管、AI 跑团（TRPG）引擎**，支持 DND 5e、CoC 7e 与自定义规则。它的核心主张是：

> "AI GM，不抢走规则" —— 模型负责讲故事，引擎负责让 HP、物品、金币与检定真正落地。

其运行逻辑可归纳为一条**回合流水线**：

```
玩家自然语言行动（"我检查墙上的符文"）
  → 回合收集（单人立即 / 多人等所有活跃玩家提交，或 GM 强制推进）
  → GM 裁判阶段（模型整批决定：谁需要检定、用哪个属性/技能、目标值）
  → 服务端只掷一次骰，固定结果（页面按行动顺序显示判定卡片）
  → 叙事阶段（模型基于固定骰果生成叙事 + 状态标签）
  → 引擎解析状态标签，校验后写回存档（HP / 物品 / 金币 / 经验 / 场景 / 私密感知）
  → SSE 广播给所有客户端
```

**关键设计原则（值得借鉴）**：

| 原则 | 说明 | 对我们的意义 |
|---|---|---|
| 叙事与状态分离 | 模型输出 = 叙事文本 + 结构化状态标签；状态变动由引擎校验后落库，**以状态变动为准** | 防止 AI 幻觉改数值；与 coc7th-keeper"脚本是唯一权威"理念一致 |
| 骰子与规则分离 | 随机层只出骰值；规则层决定骰制/修正/目标值/成功等级；GM 只判断"是否需要检定" | 一套骰子引擎可服务 DND / COC / 自定义规则 |
| 服务端权威 | 所有状态变动由服务端校验；客户端只提交行动 | 多人一致性的根基 |
| 一次掷骰 | 裁判阶段整批决定检定，服务端只掷一次，叙事只能遵循结果 | 防作弊、防重复掷骰 |
| 平台无关 Bot Bridge | 群聊适配器只做消息收发，跑团逻辑统一走 HTTP API | 预留飞书 / QQ 桥接的现成范式 |

### 2.2 应用端 / Web 端 UI 结构

DiceFrame 的 WebUI 以**顶部五大工作区**组织（这是我们要"类似"的骨架）：

| 工作区 | 内容 |
|---|---|
| **总览（Overview）** | 创建新冒险（选语言 → 选世界模板 / AI 生成 / 自填 → 选规则与难度 → 建卡）、加入游戏、最近游戏列表 |
| **游玩（Play）** | 叙事区（GM 叙事 + 回合号）、行动输入框、状态变动区、判定卡片（骰子结果）、玩家列表（在线 / 暂离）、GM 推进按钮 |
| **角色（Characters）** | 角色卡查看 / 编辑 / 建卡（手动或 AI 草稿）、角色认领 |
| **内容（Content）** | 世界书（NPC / 地点 / 物品 / 事件 / 谜题 / 势力，按关键词注入上下文）、世界、冒险包、规则（JSON 规则系统） |
| **管理（Admin）** | 设置（模型接口 / 模型配置 / 访问密码 / 分享地址）、记忆与日志、插件商店、关于与更新 |

**多人相关 UI 元素**：邀请链接复制、角色认领、行动等待提示、暂离 / 回来、GM 强制推进、私密感知（左侧角色专属信息）、支付确认弹窗。

**移动端**：另有独立 Android 客户端（`diceframe-mobile` 仓库），本期不做。

### 2.3 技术栈与架构

| 层 | 技术 | 说明 |
|---|---|---|
| 后端 | Python（`web_server.py` + `src/`） | `engine`（状态/骰子/战斗）、`commands`（回合/标签解析/状态应用）、`generation`（世界/规则/角色生成）、`lorebook`（世界书）、`memory`（长期记忆/摘要/embedding）、`rules`（JSON 规则系统）、`webui`（HTTP API/routes/services）、`bots/bridge_core`（聊天底座） |
| 前端 | Vue 3 + TypeScript（`frontend-v2/`） | 构建产物输出到 `static-v2/`；`src/peer/` 为 WebRTC 直连协议 |
| 实时同步 | **SSE**（Server-Sent Events） | 服务端单向推送；另有实验性 WebRTC 玩家直连 |
| 存储 | 文件目录 `data/` | `config.json` / `secrets.json` / `saves/` / `templates/` / `plugins/` / `bot/cards/` |
| 部署 | Windows 便携版 / Docker（`ghcr.io/diceframe/diceframe`）/ 源码 | 默认端口：源码 18000，Docker 9876 |
| 模型 | OpenAI 兼容 / Anthropic 接口 | 主模型 + 备用 + Embedding（向量记忆，可选）+ TTS/ASR/生图（可选） |

### 2.4 多人联机方案（DiceFrame 现状）

DiceFrame 的多人联机是**中心服务器模式**：

1. **邀请链接**：GM 创建游戏 → 复制邀请链接 → 玩家打开链接加入 / 建卡 / 认领角色。
2. **回合制**：每轮每个活跃玩家提交行动；全部提交后自动推进；未提交者保留等待（无倒计时）；GM 可强制推进。
3. **实时同步**：SSE 推送叙事、状态变动、判定卡片。
4. **暂离机制**：`暂离` 玩家不阻塞回合，剧情默认跟随队伍；`回来` 恢复。
5. **私密信息**：私密感知只推给对应角色（网页左侧 / 群聊私聊）。
6. **支付确认**：付款玩家单独确认，余额校验后才扣款。
7. **外网联机**：官方不提供公网服务器，靠内网穿透（SakuraFrp / Cloudflare Tunnel / Tailscale Funnel）或端口映射；需在"分享地址"填入外网地址，邀请链接才会指向外网。
8. **实验性玩家直连**：WebRTC 数据通道直达房主，一次性链接码（5 分钟过期），房主权威，适合临时小团；不替代公网服务器。

---

## 3. 现状盘点：coc7th-keeper 可复用资产

### 3.1 可直接复用的后端逻辑（Python 脚本）

| 脚本 | 功能 | 复用方式 |
|---|---|---|
| `_common.py` | CSPRNG 骰子、骰子审计（`dice.log` 追加式）、JSON 读写、路径解析、隐私净化 `relabel()` | **原样复用**，作为服务层底层库 |
| `roll.py` | 任意骰子表达式（`1d100` / `2d6+3` / `d20`） | 原样复用 |
| `check.py` | 技能检定、对抗检定、联合检定、幸运检定（CoC7th 完整档位：大成功 / 极难 / 困难 / 成功） | 原样复用 |
| `build.py` | 角色 build（5d6 取大 3 + 教育 2d6+6） | 原样复用 |
| `sanity.py` | 理智检定、理智损失、实时 / 不定 / 临时疯狂 | 原样复用 |
| `combat.py` | 先攻、攻击、伤害、重伤表 | 原样复用 |
| `room.py` | 房间生命周期：init / join / leave / build / save / load / status / audit / kick | **改造**：CLI 参数 → REST 路由 |
| `modules.py` + `use_pregen.py` | 模组列表 / 简介 / 预制角色 | 原样复用（数据层） |
| 模组目录 | `the-haunting`（惊魂）、`toy-dancer-comes`（玩具跳着舞蹈来） | 原样复用（含 `plot.md` / `kp-notes.md` / `clues.md` / `npcs.json` / `pregens/`） |

**当前项目独有的优势**：
- **完整 CoC7th 规则**（build / 对抗 / 理智 / 战斗 / 重伤），比 DiceFrame 内置"轻量 CoC"更完整。
- **加密安全随机数 + 追加式审计日志**（`dice.log`），公平性可审计。
- **隐私铁律**（§2 频道与隐私）：KP 数据（`kp-notes.md`、隐藏 NPC / 怪物数值、未揭示线索）与玩家可见内容严格分离——这套分级在 Web 端天然对应"GM 视图 vs 玩家视图"。

### 3.2 需要改造 / 新增的部分

| 项 | 现状 | 目标 |
|---|---|---|
| 调用方式 | CLI（`coc.ps1 roll ...` → stdout JSON） | 封装为 REST API + SSE 事件流 |
| 存储 | 文件目录 `coc-session/<房间>/`（单进程假设） | 保留文件存储，加**进程内锁 / 队列**保证并发安全；后续可平滑迁移 SQLite |
| 前端 | 无（飞书卡片由 dsh-lark-bot 渲染） | 自建 Web 前端（Vue 3 + TS） |
| AI 守密人 | DeepSeek Harness Agent（加载 skill 后由 LLM 生成叙事） | Web 端直接调 LLM API（OpenAI 兼容），把 skill 的守密人提示词 / 隐私铁律编译进系统提示词 |
| 多人 | 无（飞书群天然多用户，但无回合制收集） | 回合制行动收集 + SSE 同步 + 邀请链接 + 角色认领 |
| 规则扩展 | 仅 CoC7th | 预留 DND 5e 轻量规则（d20 + 修正 ≥ DC）与自定义规则（JSON 规则描述，参考 DiceFrame `check_mechanic`） |

---

## 4. 总体方案与选型对比

### 方案 A：直接部署 / 二次开发 DiceFrame

- **做法**：下载 Windows 便携版或 Docker 部署，配置模型后直接用；需要改动时 fork 源码。
- **优点**：功能最全（AI GM / 多人 / 世界书 / 记忆 / 插件 / Bot 桥接 / 移动端），社区维护，一周内可开团。
- **缺点**：
  - **AGPL-3.0 许可**：修改版若作为网络服务对外提供，必须开源全部修改源码（§8）。
  - CoC 规则是"轻量辅助版"，**不承诺完整复刻商业规则书**——而我们已有完整 CoC7th 实现。
  - 与当前项目（DSH + 飞书 + coc7th-keeper）是两套体系，规则资产无法直接迁移。
  - 世界书 / 记忆 / 插件等重功能对"小团自用"是过度设计。

### 方案 B：复用 coc7th-keeper 规则引擎 + 自建轻量 Web 服务与前端（**推荐**）

- **做法**：把现有 Python 脚本封装为 REST API + SSE；自建 Vue 3 前端（参考 DiceFrame 五大工作区骨架）；AI 守密人直接调 LLM API（复用 skill 的守密人提示词与隐私铁律）。
- **优点**：
  - 完整 CoC7th 规则 + 审计 + 隐私铁律全部继承，**零规则重写**。
  - 架构自研、无 AGPL 传染（仅"参考"DiceFrame 的公开设计，不复制代码）。
  - 与现有 DSH / 飞书生态同源，后续可把飞书桥接作为"群聊适配器"接入。
  - 按需裁剪：先单人 + 多人，世界书 / 记忆 / 插件留扩展点。
- **缺点**：需要自建服务层与前端，工作量最大（约 4–6 周 MVP）；AI GM 的叙事质量依赖提示词调优。

### 方案 C：混合（DiceFrame 为底座 + 移植 CoC 规则）

- **做法**：部署 DiceFrame，把 coc7th-keeper 的完整 CoC 规则以"内容包 / 规则"形式移植进去。
- **优点**：兼顾 DiceFrame 的完整产品力与我们的规则资产。
- **缺点**：受 AGPL 约束（fork 即传染）；DiceFrame 规则系统是 JSON 声明式，移植完整 CoC7th（build / 理智 / 战斗 / 重伤）需要把 Python 逻辑重写为 JSON 规则，**工作量接近方案 B 且受许可限制**。

### 选型结论

> **推荐方案 B**：以 coc7th-keeper 规则引擎为内核，参考 DiceFrame 的**架构模式**（叙事/状态分离、骰子/规则分离、SSE、Bot Bridge 范式）自建轻量平台。理由：规则资产零重写、无许可风险、与现有生态同源、按需演进。
>
> 若用户更看重"尽快开团"而非"规则完整度"，可先并行部署 DiceFrame 试玩（方案 A），同时按方案 B 推进自研——两者不冲突。

---

## 5. 目标架构设计（方案 B）

### 5.1 总体架构

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ 浏览器 GM    │   │ 浏览器 玩家1 │   │ 浏览器 玩家2 │     前端（Vue 3 + TS）
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │  HTTP + SSE      │  HTTP + SSE     │  HTTP + SSE
       └──────────────────┼─────────────────┘
                          ▼
┌─────────────────────────────────────────────────────┐
│  Web 服务层（Python，新增）                            │
│  · REST API（游戏/回合/行动/角色/支付/管理）            │
│  · SSE 事件总线（叙事/状态变动/判定卡片/私密感知）       │
│  · 鉴权（访问密码 / 邀请链接 / 角色认领 / GM 权限）      │
│  · 回合调度器（行动收集 → 裁判 → 掷骰 → 叙事 → 落库）    │
├─────────────────────────────────────────────────────┤
│  规则引擎（复用 coc7th-keeper scripts/*.py）          │
│  roll / check / build / sanity / combat / room       │
│  + CSPRNG + dice.log 审计 + 隐私净化 relabel()        │
├─────────────────────────────────────────────────────┤
│  存储：coc-session/<房间>/（文件 + 进程锁）             │
│  room.json / players/ / log.md / kp-notes.md / dice.log
├─────────────────────────────────────────────────────┤
│  AI 守密人（LLM API，OpenAI 兼容）                    │
│  · 守密人提示词（编译自 skill：十条 + 隐私铁律 + 风格）  │
│  · 裁判阶段：决定检定 → 服务端掷骰 → 叙事阶段           │
└─────────────────────────────────────────────────────┘
        │ 预留扩展口（接口已定义，本期不实现）
        ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ 群聊 Bot 桥接 │  │ WebRTC 直连   │  │ 插件 / 世界书 │
│ (飞书/QQ)     │  │ (P2P 房主权威)│  │ (扩展点)      │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 5.2 后端设计

**5.2.1 规则引擎服务化**

- 新增 `web_server.py`（FastAPI 或 Flask，推荐 FastAPI：自带 OpenAPI 文档 + SSE 支持）。
- 现有脚本改造为**库调用**：`from coc_engine import roll, check, build, sanity, combat, room`，保留 CLI 入口（`coc.ps1` 继续可用，向后兼容）。
- 骰子与审计：**原样复用** `_common.py`（CSPRNG + `dice.log` 追加式），所有检定必须走引擎，禁止"口算"。

**5.2.2 回合调度器（多人核心）**

```
round N 开始
  ├─ 收集：每个活跃玩家提交行动（可修改，有次数上限；AI 只读最后一次）
  ├─ 推进条件：全部活跃玩家已提交 或 GM 强制推进
  ├─ 裁判：LLM 整批决定检定（谁 / 哪个技能 / 目标值）→ 服务端掷骰一次，固定结果
  ├─ 叙事：LLM 基于固定骰果生成叙事 + 状态标签（JSON）
  ├─ 校验落库：引擎解析状态标签 → 校验（余额 / 物品 / HP 边界）→ 写回存档
  └─ 广播：SSE 推送 判定卡片 + 叙事 + 状态变动 + 私密感知
```

**5.2.3 状态与存档**

- 沿用 `coc-session/<房间>/` 结构（`room.json` / `players/` / `log.md` / `kp-notes.md` / `dice.log`），**与飞书跑团存档天然互通**（同一份数据，两个入口）。
- 并发安全：房间级 `threading.Lock` + 写队列（单进程内）；跨进程（多 worker）时用文件锁或迁移 SQLite（预留）。
- 快照：复用 `room.py save/load`，Web 端提供"保存 / 读档"。

**5.2.4 AI 守密人**

- 直接调 LLM API（OpenAI 兼容，用户自备 Key，配置存 `data/secrets.json` 或环境变量）。
- 系统提示词 = skill 的守密人十条 + 隐私铁律（KP 数据分级）+ 场景自适应风格，编译为一份 `prompts/gm_system.md`。
- **裁判与叙事两阶段调用**（参考 DiceFrame）：裁判阶段输出结构化 JSON（`dice_checks`），叙事阶段只能遵循已固定的骰果。
- 可选：长期记忆（关键词匹配 → 可选 embedding 语义召回），本期先做关键词摘要。

### 5.3 前端设计

**5.3.1 技术选型**

- Vue 3 + TypeScript + Vite（与 DiceFrame 同栈，生态成熟）；UI 组件库用 Naive UI / Element Plus（**先功能后美术**）。
- 实时同步：原生 **SSE**（`EventSource`），服务端 `text/event-stream`；不引入 WebSocket 依赖（SSE 足够且可穿透性好）。
- 状态管理：Pinia；路由：Vue Router。

**5.3.2 页面结构（参考 DiceFrame 五大工作区，功能优先）**

| 路由 | 页面 | 核心功能 |
|---|---|---|
| `/` | 总览 | 创建冒险（语言 / 世界 / 规则 / 难度）、加入游戏（邀请链接）、最近游戏 |
| `/play/:gameKey` | 游玩 | 叙事流（回合号 + GM 叙事 + 判定卡片）、行动输入框、状态变动区、玩家列表（在线/暂离）、GM 推进按钮、私密感知面板 |
| `/characters` | 角色 | 建卡（手动 / AI 草稿 / 预制角色）、角色卡查看编辑、认领 |
| `/content` | 内容 | 模组列表与详情（复用 `modules.py`）、世界书（预留）、规则（预留 DND/自定义） |
| `/admin` | 管理 | 模型接口 / 模型配置 / 访问密码 / 分享地址 / 日志（dice.log 审计查看） |

**5.3.3 视图分级（隐私铁律的 Web 化）**

- **GM 视图**：可看 `kp-notes.md` 摘要、隐藏 NPC / 怪物数值、未揭示线索、强制推进、踢人。
- **玩家视图**：只看到自己角色可见的内容；私密感知单独推送；失败检定只显示"没能看出更多端倪"（沿用 §2.2 措辞铁律）。
- 前端**不直接下发 KP 数据**：所有 KP 内容由服务端按角色过滤后推送，前端无权限分支可绕过。

### 5.4 多人联机方案（本期实现）

| 机制 | 设计 |
|---|---|
| 邀请链接 | `POST /api/games` 创建 → 返回 `game_key` + 邀请链接（含一次性凭证）；GM 可随时重新生成 |
| 角色认领 | 玩家打开链接 → 建卡 / 认领已有角色 → 绑定 `player uid`（服务端生成，防伪造） |
| 回合制 | 每轮活跃玩家各提交一次行动；全部提交自动推进；GM 可强制推进；未提交者保留等待（无倒计时） |
| 实时同步 | SSE 事件：`action_received` / `round_advanced` / `narration` / `state_changed` / `dice_result` / `private_perception` / `payment_request` |
| 暂离 / 回来 | `away` 玩家不阻塞回合，剧情默认跟随队伍；`back` 恢复 |
| 私密信息 | 服务端按角色过滤，SSE 只推给对应连接 |
| 支付确认 | 付款玩家单独确认，余额校验后生效（参考 DiceFrame） |
| 鉴权 | 房间访问密码（可选）+ 邀请凭证 + GM 权限位（推进 / 踢人 / 强制） |

### 5.5 预留接口设计（多人联机扩展口）

**5.5.1 REST API 草案（v1）**

```
POST   /api/games                         创建游戏（规则 / 世界 / 难度）
GET    /api/games/{key}                   游戏详情（GM 视图 / 玩家视图按角色过滤）
POST   /api/games/{key}/join              加入（邀请凭证 → 建卡 / 认领）
POST   /api/games/{key}/actions           提交行动（自然语言）
POST   /api/games/{key}/advance           GM 强制推进
POST   /api/games/{key}/away|back         暂离 / 回来
POST   /api/games/{key}/pay               支付确认 / 拒绝
GET    /api/games/{key}/state             拉取全量状态（SSE 断线重连兜底）
GET    /api/games/{key}/events             SSE 事件流
GET    /api/games/{key}/audit             骰子审计（dice.log）
POST   /api/games/{key}/save|load         快照
GET    /api/modules                       模组列表 / 详情
GET    /api/admin/config                  模型 / 密码 / 分享地址（GM）
```

**5.5.2 SSE 事件格式草案**

```json
{"event": "narration", "data": {"round": 12, "text": "门后的风带着潮湿铁锈味……", "by": "gm"}}
{"event": "dice_result", "data": {"player": "alice", "skill": "侦查", "roll": 29, "level": "困难成功"}}
{"event": "state_changed", "data": {"hp": {"alice": 12}, "items": ["旧钥匙"]}}
{"event": "private_perception", "data": {"to": "alice", "text": "你注意到符文在缓慢地呼吸。"}}
```

**5.5.3 群聊 Bot 桥接（预留，参考 DiceFrame bridge_core 范式）**

- 定义平台无关的 `BridgeInput`（频道 / 用户 / 文本 / 是否提及）→ `DiceFrameBridgeService` → `BridgeResult`。
- 适配器只做消息收发：飞书（复用现有 dsh-lark-bot 经验）、QQ / NapCat、Telegram。
- 鉴权：`X-Bot-Token` 请求头（服务端生成，可轮换）。
- 群聊命令映射：`@bot 状态` / `@bot 前情` / `@bot 推进` / `@bot 暂离` / `@bot 感知` 等。

**5.5.4 WebRTC 玩家直连（预留，实验性）**

- 房主权威：玩家请求经 WebRTC 数据通道直达房主，存档 / 模型 / 规则仍由房主掌管。
- 一次性链接码（5 分钟过期），适合临时小团；不替代公网服务器。
- 前端 `src/peer/` 独立模块，无活动直连时自动回退 HTTP/SSE。

---

## 6. 多人联机部署方案对比

| 维度 | 本地局域网 | 公网（内网穿透） | 公网（云服务器） |
|---|---|---|---|
| 适用 | 同 WiFi / 同网段小团 | 朋友分布各地、临时开团 | 长期稳定开团 / 对外服务 |
| 成本 | 0 | 免费额度（SakuraFrp / Cloudflare Tunnel / Tailscale Funnel）或少量付费 | 云主机月费（轻量级即可） |
| 延迟 | 最低 | 取决于节点 | 取决于机房 |
| 稳定性 | 高（无外网依赖） | 中（隧道服务商 SLA 一般） | 高 |
| 安全 | 局域网内 | 必须设访问密码 + 优先 HTTPS | 可配 HTTPS + 密码 + 限流 |
| 实现 | 零配置，直接访问 `http://<本机IP>:<端口>` | 隧道工具 + 在"分享地址"填外网地址 | 部署到云主机，域名 + 反代（Caddy / Nginx） |
| 推荐场景 | **MVP 首选**（先跑通） | 临时小团（几小时） | 长期团 / 多人常驻 |

**结论**：MVP 阶段**本地局域网**跑通闭环；上线时按需选内网穿透（免费、快）或云服务器（稳、贵）。架构上三者只差"分享地址"配置，代码零改动。

---

## 7. 开发里程碑

| 里程碑 | 内容 | 交付物 | 预估 |
|---|---|---|---|
| **M0 后端服务化** | 现有脚本封装为库 + FastAPI 服务；房间级锁；REST API 骨架；SSE 事件总线 | `web_server.py` + `coc_engine` 包；`/api/*` 可 curl 验证 | 1–2 周 |
| **M1 单人 Web 闭环** | 前端骨架（五大工作区）；总览建冒险 → 建卡 → 游玩 → 行动 → 检定 → 叙事 → 状态落库；AI 守密人提示词编译 | 浏览器单人可完整跑一局《惊魂》 | 2–3 周 |
| **M2 多人联机** | 邀请链接 / 角色认领 / 回合收集 / SSE 同步 / GM 推进 / 暂离 / 私密感知 / 支付确认 | 2–4 人浏览器联机跑通 | 2–3 周 |
| **M3 外网部署** | 访问密码 / 分享地址 / 内网穿透或云服务器 / HTTPS | 异地玩家可加入 | 1 周 |
| **M4 扩展（可选）** | 群聊 Bot 桥接（飞书 / QQ）、DND 5e 轻量规则、世界书、WebRTC 直连 | 按需排期 | 每项 1–2 周 |

**验收标准（M2 结束）**：GM 建桌 → 3 名玩家经邀请链接加入并认领角色 → 每人提交行动 → 自动推进 → 判定卡片与叙事同步到所有人 → 骰子审计可查 → 暂离玩家不阻塞回合 → 私密感知只对目标玩家可见。

---

## 8. 风险与对策

| 风险 | 说明 | 对策 |
|---|---|---|
| **AGPL 许可** | 若 fork / 复制 DiceFrame 代码，修改版作为网络服务提供时必须开源 | 方案 B 只借鉴公开设计（架构模式、UI 结构），**不复制代码**；如需复用其代码，单独评估 AGPL 合规 |
| **隐私铁律 Web 化** | KP 数据（kp-notes / 隐藏数值 / 未揭示线索）在 Web 端泄漏 | 服务端按角色过滤后推送；前端无权限分支；沿用 §2.2 措辞铁律（失败只叙述"没能看出更多"） |
| **AI 叙事质量** | 裁判 / 叙事两阶段提示词调优不足，检定判定不准 | 裁判阶段强制输出结构化 JSON；骰果固定后叙事只能遵循；内置规则速查表进提示词 |
| **并发一致性** | 文件存储多请求并发写坏档 | 房间级锁 + 写队列；M0 即引入；后续可迁移 SQLite |
| **模型成本 / 延迟** | 每回合多次 LLM 调用 | 裁判 + 叙事合并为一次调用（可选）；本地 Ollama 可零成本试玩 |
| **规则完整性** | DND 5e 需新增规则实现 | 复用 DiceFrame 的 `check_mechanic` JSON 声明范式，先做轻量 d20，再按需深化 |
| **范围蔓延** | 世界书 / 记忆 / 插件 / 语音 / 生图诱惑大 | 全部列为"预留扩展点"，M0–M3 只做核心闭环 |

---

## 9. 附录：参考文档索引

- DiceFrame 官网：https://diceframe.com/
- 用户手册（guide.md）：https://github.com/diceframe/diceframe-content/blob/main/docs/zh/guide.md
- 部署说明（deploy.md）：https://github.com/diceframe/diceframe-content/blob/main/docs/zh/deploy.md
- 规则与骰子（rules-and-dice.md）：https://github.com/diceframe/diceframe/blob/main/docs/zh/rules-and-dice.md
- 玩家直连（direct-connect.md）：https://github.com/diceframe/diceframe/blob/main/docs/zh/direct-connect.md
- Bot Bridge 核心（bot-bridge-core.md）：https://github.com/diceframe/diceframe-content/blob/main/docs/zh/bot-bridge-core.md
- 主仓库：https://github.com/diceframe/diceframe
- 文档仓库：https://github.com/diceframe/diceframe-content
- 当前项目：本仓库 `coc7th-keeper`（skill 位于 `.dsh/skills/coc7th-keeper/`）
