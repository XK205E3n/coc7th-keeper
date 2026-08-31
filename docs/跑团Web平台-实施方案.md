# 跑团 Web 平台 · 具体实施方案（方案 B · 纯 Web，舍弃群聊软件）

> 版本：v0.2 ｜ 日期：2026-08-31 ｜ 前置文档：`docs/跑团Web平台计划书.md`
> 本方案基于已确认的两个决策：**① 采用方案 B（复用 coc7th-keeper 规则引擎 + 自建 Web 服务与前端）；② 完全舍弃飞书等群聊软件**——平台是独立的纯 Web 应用，所有交互只通过浏览器，不依赖 DeepSeek Harness / dsh-lark-bot / 任何群聊桥接。

---

## 0. 决策记录：舍弃飞书的影响分析

| 原有依赖 | 新方案的处理 | 影响 |
|---|---|---|
| dsh-lark-bot 桥接、飞书卡片渲染 | **全部移除**，新平台不依赖 | 交互入口唯一 = 浏览器 |
| DeepSeek Harness Agent（加载 skill 后由 LLM 生成叙事） | 改为**服务端直接调 LLM API**（OpenAI 兼容） | skill 的守密人提示词 / 隐私铁律 / 规则速查 → 编译为静态提示词文件（§6） |
| 频道上下文头（chat_type：p2p/group/topic） | 移除 | 隐私铁律的落实方式从"频道分支"改为"服务端按角色过滤 + 输出层净化"（§7） |
| `bot-start.ps1` / `tools/fix-bridge-worktrees.ps1` 等飞书运维脚本 | 不参与新平台运行（仓库保留但不再被调用） | 部署简化为一条 `python web_server.py` |
| 群聊 Bot 桥接（飞书/QQ/Telegram） | **明确不做**（YAGNI）。如未来确需，另立项目参考 DiceFrame bridge_core 范式，不在本项目范围内 | 架构图上删除 Bot Bridge 模块 |
| WebRTC 玩家直连 | 保留为**远期可选扩展**（属联机技术，非群聊软件），M3 前不做 | 架构上预留 frontend/src/peer/ 空位即可 |

**结论**：本项目 = 纯 Web 跑团应用。运行环境 = Python 3.11+ + Node 22 + 一个 OpenAI 兼容模型接口。不再需要 DSH Desktop。

---

## 1. 技术选型清单

| 层 | 选型 | 版本 | 理由 |
|---|---|---|---|
| 后端框架 | FastAPI + Uvicorn | fastapi≥0.115 / uvicorn | 自带 OpenAPI 文档、异步、SSE 支持好 |
| LLM 客户端 | openai（AsyncOpenAI） | ≥1.40 | 官方库，天然支持 DeepSeek / Ollama / 硅基流动等 OpenAI 兼容端点 |
| 数据 | 文件系统 JSON（沿用 `coc-session/`）、`data/config.json` | — | 与飞书存档互通；并发用房间级锁，后续可迁 SQLite |
| 实时 | SSE（`text/event-stream`） | 原生 + sse-starlette（可选） | 单向推送足够、可穿透性好、实现简单 |
| 鉴权 | 无数据库的 token 体系 | — | 访问密码哈希 + 邀请凭证 + 玩家/GM token（secrets.token_hex） |
| 前端 | Vue 3 + TypeScript + Vite | vue≥3.4 / vit 5 | 与 DiceFrame 同栈，组件生态成熟 |
| 前端状态 | Pinia + Vue Router | — | 标准配套 |
| UI 组件 | Naive UI | — | 功能优先、开箱即用、默认样式可后补美术 |
| 测试 | pytest（后端）+ vitest（前端） | — | 复用现有 walkthrough 冒烟思路 |
| 部署 | 本地 `python web_server.py` 起步；可选 Docker 单容器 | — | M3 再定 |

**依赖安装**（在仓库根目录）：
```bash
# 后端
pip install fastapi uvicorn[standard] openai httpx
# 前端
cd frontend && npm create vite@latest . -- --template vue-ts && npm i pinia vue-router naive-ui
```

---

## 2. 目标目录结构

新平台代码与现有 skill 并存于同一仓库，**互不干扰**：

```
跑团/
├── server/                        # ★ 新：Web 服务端（核心交付物）
│   ├── main.py                    #   FastAPI 入口（挂路由 + 静态文件 + 启动配置）
│   ├── config.py                  #   data/config.json / secrets.json 读写
│   ├── auth.py                    #   访问密码 / 邀请凭证 / player&gm token
│   ├── sse.py                     #   房间级事件总线（每房间 pub/sub + 心跳）
│   ├── roundman.py                #   回合调度器（状态机，§5）
│   ├── state_apply.py             #   状态标签校验与落库（§6.4）
│   ├── engine/                    #   ★ 复用：自 skill 复制并库化
│   │   ├── _common.py             #     CSPRNG / dice.log 审计 / relabel()（原样）
│   │   ├── roll.py                #     （main() 提取为 roll_expr()）
│   │   ├── check.py               #     （提取为 skill_check() / luck_check()）
│   │   ├── build.py               #     （提取为 build_character()）
│   │   ├── sanity.py              #     （提取为 sanity_check()）
│   │   ├── combat.py              #     （提取为 attack_roll() 等）
│   │   └── room.py                #     （提取为 init_room() / save_room() 等）
│   ├── gm/
│   │   ├── llm.py                 #    AsyncOpenAI 客户端封装 + 重试/降级
│   │   ├── prompts.py             #    编译守密人系统提示词（§6.1）
│   │   ├── adjudicate.py          #    裁判阶段：行动→dice_checks JSON（§6.2）
│   │   └── narrate.py             #    叙事阶段：固定骰果→叙事+状态标签（§6.3）
│   └── api/
│       ├── games.py               #   /api/games/*（§4）
│       ├── modules.py             #   /api/modules
│       └── admin.py               #   /api/admin/*
├── frontend/                      # ★ 新：Vue 3 前端
│   ├── src/
│   │   ├── views/                 #   Overview.vue / Play.vue / Characters.vue / Content.vue / Admin.vue
│   │   ├── components/            #   NarrationStream / DiceCard / PlayerList / ActionInput /
│   │   │                          #   StateChanges / PerceptionPanel / GmPanel / InviteLink
│   │   ├── api/client.ts          #   REST 客户端
│   │   ├── api/sse.ts             #   EventSource 封装 + 断线重连
│   │   ├── stores/game.ts         #   Pinia：房间状态 / 叙事流 / 行动
│   │   ├── stores/auth.ts         #   token 持久化（localStorage）
│   │   └── router.ts
│   └── index.html
├── prompts/
│   └── gm_system.md               # ★ 守密人系统提示词（编译产物：十条+隐私+规则速查+风格）
├── data/                          # ★ 运行时配置（.gitignore）
│   ├── config.json                #   模型接口 / 访问密码 / 分享地址
│   └── secrets.json               #   API Key（本地文件，不入库）
├── coc-session/                   # ★ 跑团存档（沿用现有格式，与飞书存档互通）
├── docs/                          # 计划书 + 本实施方案
└── .dsh/skills/coc7th-keeper/     # 现有 skill：脚本是 engine 的素材源，提示词是 gm_system.md 的素材源
                                   # （本项目运行时不加载 skill，只参照其内容）
```

**复用策略**：`server/engine/` 从 skill 复制 `_common/roll/check/build/sanity/combat/room/modules/use_pregen` 共 8 个脚本，做"库化"改造（把 `if __name__ == "__main__"` 下的逻辑提取为可导入函数，CLI 入口保留以向后兼容）。**原 skill 目录不改动**，飞书版可继续运行。

---

## 3. 数据模型

### 3.1 房间（`coc-session/<game_key>/room.json`）

```json
{
  "game_key": "a1b2c3d4",
  "rule": "coc7",                        // coc7 | dnd5e（预留）
  "module_id": "the-haunting",
  "world_summary": "1920年代波士顿……",
  "created_at": 1770000000000,
  "gm_token_hash": "…",                  // 创建者 = GM
  "access_password_hash": null,          // 可选：加入需密码
  "round": 3,
  "phase": "collecting",                 // lobby | collecting | adjudicating | narrating
  "players": [
    {
      "uid": "u_9f2a",                   // 服务端生成，防伪造
      "name": "爱丽丝",
      "role_file": "players/alice.json",
      "is_away": false,
      "action": null,                    // 本轮行动（AI 只读最后一次）
      "action_version": 0,               // 修改计数（有上限，如 3）
      "joined_at": 1770000000100
    }
  ]
}
```

### 3.2 角色卡（`coc-session/<game_key>/players/<name>.json`）

**沿用 skill 现有 schema 原样**（属性 / 派生值 / 技能 / 物品 / 背包 / 理智历史），保证与飞书跑团存档双向互通（同一份数据，两个入口）。

### 3.3 剧本日志与审计

- `log.md`：GM 叙事追加流（Web 端叙事流的水久化）。
- `kp-notes.md`：守密人笔记（**只进 GM 视图 / LLM 上下文，绝不进玩家视图**）。
- `dice.log`：追加式审计（**所有检定必须走引擎**，禁止口算）。

### 3.4 配置（`data/`）

- `config.json`：`model.provider/base_url/model`、备用模型、`access_password`、`share_url`、`server.port`。
- `secrets.json`：`api_key`（写入时本地加密或只存明文+文件权限提示；参考现有 `configure-provider.ps1` 的做法）。

---

## 4. API 契约（v1）

> 统一前缀 `/api`。鉴权头：普通玩家 `X-Player-Token`；GM `X-GM-Token`；邀请 `X-Join-Token`。

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| POST | `/api/games` | `{name, rule, module_id, password?}` | `{game_key, gm_token, join_url}` | 创建游戏（创建者自动成为 GM） |
| GET | `/api/games/{key}` | — | 房间状态（**按角色过滤**：GM 视图含 kp 摘要，玩家视图只含表侧） | 全量兜底（SSE 重连时拉取） |
| POST | `/api/games/{key}/join` | `{join_token, password?, name?, role_file?}` | `{player_token, player}` | 加入 / 认领 / 用预制角色 |
| POST | `/api/games/{key}/roles` | （GM）`{action: create} \| 表单角色数据` | 角色卡 | 建卡（手动 / `build.py` 自动 / 预制） |
| POST | `/api/games/{key}/actions` | `{text}` | `{accepted: true, round}` | 提交（或修改）本轮行动 |
| POST | `/api/games/{key}/advance` | （GM）— | `{triggered: true}` | GM 强制推进本回合 |
| POST | `/api/games/{key}/away`·`/back` | — | 更新 `is_away` | 暂离 / 恢复 |
| POST | `/api/games/{key}/save`·`/load` | （GM） | 快照路径（相对形式） | 复用 `room.py save/load` |
| POST | `/api/games/{key}/kick` | （GM）`{uid}` | — | 踢人 |
| GET | `/api/games/{key}/audit` | `?last=N` | 最近 N 条 `dice.log` | 审计可查 |
| GET | `/api/games/{key}/events` | — | `text/event-stream` | SSE 事件流（§4.1） |
| GET | `/api/modules` / `/api/modules/{id}` | — | 模组列表 / 详情 | 读 `modules.py` 数据层 |
| GET/PUT | `/api/admin/config` | （GM）模型 / 密码 / 分享地址 | — | 管理页 |
| POST | `/api/admin/test-llm` | （GM）`{base_url, key, model}` | 测试连接结果 | 配置向导用 |

### 4.1 SSE 事件（`/api/games/{key}/events`）

```json
{"event":"round_started","data":{"round":3,"scene":"你踏入潮湿的走廊……"}}
{"event":"action_received","data":{"player":"爱丽丝","round":3}}
{"event":"dice_result","data":{"player":"爱丽丝","skill":"侦查","roll":29,"level":"困难成功","target":60}}
{"event":"narration","data":{"round":3,"text":"门后的风带着潮湿铁锈味……"}}
{"event":"state_changed","data":{"hp":{"alice":12},"san":{"alice":55},"items":["旧钥匙"]}}
{"event":"perception","data":{"to":"u_9f2a","text":"你注意到符文在缓慢地呼吸。"}}   // 只推给目标连接
{"event":"turn_advanced","data":{"round":4,"phase":"collecting"}}
{"event":"phase_changed","data":{"phase":"adjudicating"}}
{"event":"player_status","data":{"uid":"u_x","is_away":true}}
```

---

## 5. 回合调度器（roundman.py）状态机

```
LOBBY ──GM 下令开局──▶ PLAYING
收集(collecting) ──全部活跃玩家已提交 或 GM advance──▶ 裁判(adjudicating)
裁判 ──dice_checks JSON──▶ 引擎掷骰（check.py/sanity.py/roll.py，写 dice.log）
     ──固定骰果──▶ 叙事(narrating)：LLM 输出 narrative + state_changes
     ──▶ 状态应用(state_apply.py)：校验→落库→清空行动→round++→广播
     ──▶ 回到 收集(collecting)，广播 round_started
```

**规则**：
- 每轮每个**活跃玩家**（`is_away=false`）可提交 / 修改行动（修改有次数上限，AI 只读最后一次）。
- 未提交的活跃玩家**保留等待，无倒计时**（沿用 DiceFrame 设计——不做超时踢人，避免误伤）。
- `away` 玩家不阻塞回合，剧情默认"跟随队伍，不主动做重大决定"（提示词约束）。
- 单人模式：提交一条行动立即自动推进（同一状态机，活跃玩家=1）。
- 所有骰子由**服务端掷一次**，结果在叙事阶段不可更改。

**并发安全**：每房间一把 `threading.Lock`（roundman 内 `with room_lock(key)` 包住整段 收集→应用 临界区）；SSE 发布在锁外进行。跨进程部署前再评估 SQLite。

---

## 6. AI 守密人设计（替代 DSH Agent）

### 6.1 系统提示词（`prompts/gm_system.md`，编译产物）

素材全部取自现有 skill，**编译为静态文件**（不再依赖 Agent 会话）：

1. **角色定位**：守密人十条（不替玩家说话 / 不替玩家决定检定时机 / 失败要有戏剧后果 / 理智损失 ≥5 暂停 / 体力 ≤0 查重伤 / 敏感题材警告 / 查规则速查不凭印象 / KP 视角不外泄 / 审计公平 / 节奏适配）。
2. **隐私铁律（Web 化）**：KP 数据（kp-notes / 隐藏数值 / 未揭示线索）只服务端可见；玩家视图只出现表侧内容；失败只叙述"没能看出更多端倪"，**绝不断言"没有异常"**（沿用 §2.2 措辞铁律）。
3. **规则速查**：`references/` 五份速查表内容（规则摘要 / 技能表 / 武器 / 理智 / 法术）。
4. **风格表**：神秘冷峻 / 紧张紧凑 / 慢热会话（沿用 skill §6）。
5. **模组上下文**：开局注入 `module_id` 的 `plot.md`（PL 视角）+ `kp-notes.md`（守密人视角，只进 GM 上下文）。

### 6.2 裁判阶段（adjudicate.py）

- **输入**：`gm_system.md` + 场景摘要（kp-notes + log.md 尾部）+ 本轮全部行动 + 相关角色卡。
- **输出（强制 JSON schema）**：

```json
{
  "dice_checks": [
    {"player_uid": "u_9f2a", "kind": "skill", "skill": "侦查", "target": 60, "reason": "检查符文是否异常"},
    {"player_uid": "u_b41c", "kind": "sanity", "loss": 1, "reason": "直视符文"}
  ],
  "private_notes": "（KP 内部观察，写入 kp-notes.md，绝不进玩家视图）"
}
```

- `kind` 白名单：`skill`（走 `check.py`）、`sanity`（走 `sanity.py`，含疯狂判定）、`luck`（走 `check.py luck`）、`none`。
- **裁判输出不含叙事**；骰果由服务端引擎掷出并固定，LLM 无法影响结果。

### 6.3 叙事阶段（narrate.py）

- **输入**：同前 + **固定骰果**（每名检定的玩家：技能 / 骰值 / 档位）。
- **输出（强制 JSON schema）**：

```json
{
  "narrative": "门后的风带着潮湿铁锈味……",
  "state_changes": [
    {"type": "hp",  "player_uid": "u_9f2a", "delta": -2},
    {"type": "san", "player_uid": "u_b41c", "delta": -1},
    {"type": "item","player_uid": "u_9f2a", "action": "gain", "item": "旧钥匙"},
    {"type": "clue","player_uid": "u_9f2a", "clue_id": "c01", "text": "符文在缓慢地呼吸。"},
    {"type": "scene","text": "沉没回廊"}
  ]
}
```

### 6.4 状态应用器（state_apply.py）—— 与 DiceFrame 同理念："叙事可以自由，状态必须可信"

| 类型 | 校验规则 | 落库 |
|---|---|---|
| `hp` | 0 ≤ 当前 + delta ≤ 上限；跌至 ≤0 自动走 `combat.py` 重伤表 | `players/*.json` |
| `san` | 损失后按 `sanity.py` 判定临时 / 不定 / 永久疯狂 | `players/*.json` + 理智历史 |
| `item` | gain/lose/consume，与背包核对 | `players/*.json` |
| `clue` | 只加到**指定玩家**的已解锁线索表；内容写入玩家视图（`perception` 事件）与 kp-notes 对照 | `players/*.json` / `kp-notes.md` |
| `scene` | 场景名白名单（来自模组 `world.json` / plot 章节）或直接记录 | `room.json` |
| `gold`（预留 DND） | 余额校验 | `players/*.json` |

**不一致处理**：叙事文本与状态变动冲突时，**以状态变动为准**（与 DiceFrame 一致），并在 log.md 记录。

### 6.5 LLM 调用策略

- `AsyncOpenAI(base_url, api_key)`；模型走 `data/config.json`（支持 DeepSeek / OpenAI / Ollama / 硅基流动）。
- 裁判 + 叙事合并为**一次调用**（可选开关，省成本）：要求 LLM 在同一个 JSON 里输出 `dice_checks` 与"待叙事稿"，服务端掷骰后把骰果回填重写叙事——第一版为稳妥起见分两次调用，优化阶段再合并。
- 失败重试 2 次 + 降级：LLM 不可用时返回引擎侧兜底叙事（"检定结果已记录，叙事服务暂不可用"），**不阻塞状态应用**。
- 长期记忆：第一版 = 每 N 轮对 `log.md` 做一次 LLM 摘要并注入上下文；embedding 语义召回列为远期可选。

---

## 7. 隐私铁律 Web 化（落实清单）

> 原则：**KP 数据不出服务端**。前端不存在任何读取 KP 数据的接口或权限分支。

| 原 skill 规则 | Web 端落实 |
|---|---|
| 群聊禁止 KP-only 内容 | `GET /api/games/{key}` 与所有 SSE 输出经**统一过滤层**：字段白名单按 `player_uid` 裁剪后再序列化 |
| 失败只叙述"没能看出更多端倪" | 叙事提示词硬性约束 + 输出后校验（LLM 输出含"没有异常/其实你漏掉"等禁用词则改写） |
| kp-notes 不外泄 | `kp-notes.md` 只在服务端读入 GM 上下文；GM 视图的 kp 摘要在页面标注"仅 GM 可见"，且**永不进入 SSE 公共流**（GM 摘要走单独事件 `gm_kp_summary`，仅推给 GM 连接） |
| 隐藏 NPC / 怪物数值不显示 | 玩家视图只显示观察到的外观 / 行为 / 台词；数值字段只在 GM 视图与 LLM 上下文 |
| 路径隐私 | 所有输出沿用 `relabel()`：显示 `coc-session/<房间>/...` 相对形式，禁止绝对路径 |
| 理智/体力阈值暂停 | 服务端检测（理智损失 ≥5、体力 ≤0）→ 广播暂停事件，等待玩家决定（沿用 skill §4 规则 4/5） |

**测试要点**：以玩家身份调每个 API，断言响应 JSON 中不含 `kp` / `monsters` / `hidden` 字段；SSE 流中 `perception` 事件只能被目标连接收到。

---

## 8. 前端设计（功能优先，美术后补）

### 8.1 路由与页面

| 路由 | 视图 | 功能点（全部功能优先） |
|---|---|---|
| `/` | Overview.vue | 创建冒险（名称 / 规则 / 模组下拉，数据来自 `/api/modules`）/ 加入游戏（粘贴邀请链接）/ 最近游戏（localStorage 索引）/ 进入管理 |
| `/play/:key` | Play.vue | 顶部栏（游戏名/回合/规则/轮次）；`NarrationStream` 叙事流（场景/行动回显/判定卡片/叙事/状态变动，按回合分组）；`ActionInput` 行动框（提交/修改/等待态）；`PlayerList`（在线/暂离/已提交）；`GmPanel`（GM 专属：强制推进/暂离/踢人/保存读档/kp 摘要）；`PerceptionPanel`（我的私密感知）；自由掷骰按钮 |
| `/characters` | Characters.vue | 角色卡展示（属性/派生/技能/物品/理智历史）；建卡三步（选预制 / AI 草稿 / 手动填写）；角色认领列表 |
| `/content` | Content.vue | 模组列表与详情（复用 `/api/modules`）；世界书 / 规则编辑（M4 预留区） |
| `/admin` | Admin.vue | 模型接口向导（provider/base_url/key/model + 测试连接）、访问密码、分享地址、`dice.log` 审计列表、关于（版本） |

### 8.2 实时机制

- `api/sse.ts`：`EventSource('/api/games/{key}/events')` + 断线重连（指数退避）+ 收到 `round_started` 时用 `GET /api/games/{key}` 全量校准。
- `stores/game.ts`：叙事流 append、行动状态、玩家列表、我的感知、GM 面板标志。
- `stores/auth.ts`：`gm_token` / `player_token` 持久化到 localStorage，请求拦截器自动带头。

### 8.3 组件清单（`frontend/src/components/`）

`NarrationStream.vue`、`DiceCard.vue`、`StateChanges.vue`、`ActionInput.vue`、`PlayerList.vue`、`PerceptionPanel.vue`、`GmPanel.vue`、`InviteLink.vue`、`CharacterSheet.vue`、`AdminModelConfig.vue`。

---

## 9. 实施步骤（含依赖分析与验收）

> 估算基准：1 名开发者，熟悉 Python + Vue；全职约 18–24 个工作日（≈4–5 周），兼职（每日 2–3h）约 8–12 周。
> 步骤按**依赖顺序**排列：S1 是 S2/S3 的地基；S2 前端骨架与 S1 可部分并行；S3 依赖 S2 的游玩页。

### S0 · 环境基线（0.5 天）

- 任务：确认 Python 3.11+ / Node 22；安装后端依赖；`npm create vite` 初始化 `frontend/`；`data/` 加入 `.gitignore`。
- 产出：两端可启动的空壳（`python server/main.py` 返回 200；`npm run dev` 出页面）。
- 验收：`http://localhost:18000` 打开前端空壳；`/api/health` 返回 ok。

### S1 · 后端服务化（4–6 天）—— M0

| 步骤 | 任务 | 涉及文件 | 验收 |
|---|---|---|---|
| S1.1 | FastAPI 骨架 + 配置读写 + CORS | `main.py` `config.py` | 配置可读写；`/api/health` |
| S1.2 | **engine 库化**：8 个脚本复制进 `server/engine/`，main() 提取为函数，保留 CLI | `server/engine/*.py` | 用现有 smoke 命令回归：`roll 1d100` / `check skill "侦查" 60` / `room init` 结果与飞书版一致 |
| S1.3 | 房间 REST 化 | `api/games.py`（创建/加入/角色/审计） | curl 可建房间、建卡、掷骰、查审计 |
| S1.4 | 房间级锁 + 写队列 | `roundman.py` | 并发 10 请求不写坏 room.json |
| S1.5 | SSE 事件总线（pub/sub + 心跳 30s） | `sse.py` | 两个 SSE 连接同时收到广播事件；断线重连后回放最近事件 |
| S1.6 | 冒烟测试脚本 | `server/tests/`（pytest） | 覆盖：建房间→join→build→roll→audit 全链路 |

### S2 · 单人 Web 闭环 + AI 守密人（6–8 天）—— M1

| 步骤 | 任务 | 涉及文件 | 验收 |
|---|---|---|---|
| S2.1 | 编译守密人系统提示词 `prompts/gm_system.md`（十条+隐私+速查+风格） | `prompts/`、`gm/prompts.py` | 提示词文件评审通过（无"飞书/群聊"残留表述） |
| S2.2 | LLM 客户端封装（AsyncOpenAI + 重试 + 降级） | `gm/llm.py` | 配 DeepSeek / Ollama 均可连接；`/api/admin/test-llm` 通过 |
| S2.3 | 裁判阶段 pipeline（行动→dice_checks→引擎掷骰→固定骰果） | `gm/adjudicate.py` `roundman.py` | 命令行模拟 3 类行动：技能检定 / 理智检定 / 无需检定 |
| S2.4 | 叙事阶段 + 状态应用器 | `gm/narrate.py` `state_apply.py` | HP/SAN/物品/线索/场景五类变动全部校验落库；禁用词过滤生效 |
| S2.5 | 前端骨架（五大工作区路由 + Naive UI + Pinia） | `frontend/src/router.ts` 等 | 五个空页面可导航 |
| S2.6 | 总览页 + 角色页（创建/加入/建卡/预制） | `Overview.vue` `Characters.vue` | 浏览器创建《惊魂》游戏并建卡成功 |
| S2.7 | 游玩页（叙事流 + 行动框 + 判定卡片 + 状态变动） | `Play.vue` + 组件 | **单人完整跑完《惊魂》第一幕**：行动→检定→叙事→HP/SAN 落库，log.md / dice.log 同步写入 |

### S3 · 多人联机（5–7 天）—— M2

| 步骤 | 任务 | 涉及文件 | 验收 |
|---|---|---|---|
| S3.1 | 邀请链接 + 角色认领 + token 体系 | `auth.py` `api/games.py` | 无密码下 3 个浏览器经链接加入并各认领角色 |
| S3.2 | 回合收集器（全活跃提交自动推进 / GM 强制 / 暂离不阻塞 / 行动可修改有上限） | `roundman.py` | 2 个浏览器联调：A 提交后等待 B；B 暂离后 A 单独推进 |
| S3.3 | 私密感知 + 玩家视图过滤（SSE 按 uid 投递） | `state_apply.py` `sse.py` | 角色 A 的线索事件 B 收不到；玩家视图不含 kp 字段 |
| S3.4 | GM 视图与控制（强制推进 / 踢人 / 保存读档 / kp 摘要） | `GmPanel.vue` `api/games.py` | GM 可强制推进与踢人；快照可读档 |
| S3.5 | 多人端到端测试（pytest + 手动脚本） | `server/tests/` | **验收标准 §9.1** 全部通过 |

### S4 · 部署与加固（2–3 天）—— M3

- S4.1：访问密码 + `share_url` 配置 + 邀请链接外网化；HTTPS 反代文档（Caddy / Nginx）。
- S4.2：启动脚本（`start-web.ps1` / `start-web.bat`）+ 可选 Dockerfile（单容器：uvicorn + 前端静态产物）。
- S4.3：部署文档：本地局域网 / SakuraFrp / Cloudflare Tunnel / 云服务器（对照计划书 §6 三档）。
- S4.4：安全清单：`secrets.json` 权限、`data/` 不公开、访问限流、日志脱敏。
- 验收：异地玩家经 HTTPS 输入密码加入游戏并正常跑一轮。

### S5 · 扩展（可选，按需排期）—— M4

- S5.1 DND 5e 轻量规则（`rule: dnd5e`，d20 + 修正 ≥ DC，优势/劣势 2d20 取高取低，复用 DiceFrame `check_mechanic` JSON 声明范式）。
- S5.2 世界书（NPC / 地点 / 物品 / 事件条目，按关键词注入 LLM 上下文）。
- S5.3 长期记忆 embedding 语义召回（Ollama nomic-embed-text / bge-m3）。
- S5.4 WebRTC 玩家直连（`frontend/src/peer/`，一次性链接码，房主权威）。

### 9.1 M2 验收标准（对照计划书 §7）

1. GM 浏览器建桌 → 获得邀请链接与 GM 控制权。
2. 3 名玩家分别用浏览器打开邀请链接加入，各建卡 / 认领角色。
3. 每人提交自然语言行动；全部提交后自动推进；`dice_result` 判定卡片同步到所有人。
4. 叙事 + `state_changed` 同步；`dice.log` 可查；`log.md` 完整。
5. 某玩家 `暂离` 后不阻塞回合；`回来` 恢复。
6. 私密线索只对目标角色可见；玩家身份调用任意 API 取不到 kp 字段。
7. 掉线重连（刷新页面）后经全量拉取恢复叙事流。

---

## 10. 风险与对策（更新）

| 风险 | 说明 | 对策 |
|---|---|---|
| AI 守密人质量 | 从"Agent+技能"改为"两阶段提示词"，叙事质量与判定准确性依赖提示词 | 裁判 JSON schema 强约束；骰果固定；规则速查进提示词；用《惊魂》第一幕做回归语料反复调优 |
| LLM 输出非法 JSON | 两阶段解析失败 | 解析失败重试 2 次 → 兜底：只应用 dice_checks 已知部分 + 保守叙事；**绝不静默改写状态** |
| 文件并发 | 多玩家同时写同一房间 | S1.4 房间锁前置；压测后仍有问题再迁 SQLite |
| 存档兼容 | 与飞书旧存档互通 | 沿用同一 schema 与目录；提供只读兼容测试（用 `coc-session-final/demo` 现有存档验证） |
| 范围蔓延 | 世界书 / 记忆 / DND / 直连诱惑大 | 全部列入 S5 可选项，S1–S4 只做核心闭环 |
| 规则完整性（DND） | CoC 完整、DND 从零 | 第一版只上 CoC（含两内置模组）；DND 按 S5.1 轻量起步 |

---

## 11. 建议的启动顺序（下一步）

1. **确认本方案**（尤其：端口 18000、`coc-session/` 复用、GM=创建者、回合规则是否接受）。
2. 执行 **S0 + S1**（环境基线 + 后端服务化）：产出可 curl 的 REST 骨架与 SSE 总线——这是后续所有工作的地基，风险最低、收益最大。
3. S1 完成后即可并行推进 S2.1–S2.4（AI 守密人）与 S2.5–S2.7（前端），单人闭环最先可见。
