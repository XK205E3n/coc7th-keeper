# 跑团 Web 平台 · 开发里程碑清单（审核稿 v2）

> 版本：v0.4 ｜ 日期：2026-08-31 ｜ 前置文档：`docs/跑团Web平台计划书.md`、`docs/跑团Web平台-实施方案.md`、`docs/模组拆解说明.md`
> 用途：**本文件是开发前的里程碑审核稿**。审核通过后，在另一个对话中按 M0 → M7 顺序开始编写。
> 本项目**全部由 AI 编写**，不提供工期估算。

## 已确认决策（2026-08-31 审核反馈）

| # | 决策 | 落地位置 |
|---|---|---|
| 1 | 端口 **18000** | M0 |
| 2 | **不设人类 GM**：AI 是唯一守密人；保留**开发者监视接口**（只读监视对话，不参与游戏） | M5 |
| 3 | 回合规则：**待进一步解释后确认**（见文末 §附） | M5 |
| 4 | 存档**不沿用**旧格式，按需设计**新存档格式（SQLite）** | M1 |
| 5 | 本期**仅支持 CoC7th**；DND5e 后续支持 | M1 / M7 |
| 6 | 模组为 PDF / 文本+图片混合，需拆解为项目格式；参考归档 toy-dancer-comes 拆解方式，制定 AI 读取模式；**拆解说明文档已编译** | `docs/模组拆解说明.md` |
| 7 | 全部由 AI 编写，**不提供工期** | 本文件 |

---

## 0. 总览

| 编号 | 名称 | 依赖 | 状态 |
|---|---|---|---|
| M0 | 环境基线 | — | ✅ 已完成 2026-08-31 |
| M1 | 后端服务化（规则引擎 + SQLite 存档 + REST + SSE） | M0 | ✅ 已完成 2026-08-31 |
| M2 | AI 守密人（裁判 / 叙事 / 状态应用） | M1 | ✅ 已完成 2026-08-31 |
| M3 | 前端骨架（五大工作区 + SSE 客户端） | M0（可与 M1/M2 并行） | ✅ 已完成 2026-08-31 |
| M4 | 单人 Web 闭环（跑通《惊魂》第一幕） | M2 + M3 | ✅ 已完成 2026-08-31 |
| M5 | 多人联机（邀请 / 回合 / 私密 / 房主管理 / 开发者监视） | M4 | ✅ 已完成 2026-08-31 |
| M6 | 部署加固（密码 / HTTPS / 启动 / 文档） | M5 | ✅ 已完成 2026-08-31 |
| M7 | 扩展（世界书 / 记忆 / WebRTC / DND5e） | M6 | ✅ 决策已定 2026-08-31（均不开发，附两条额外任务完成） |

**并行关系**：M3（前端骨架）不依赖 M1/M2 细节，可与 M1、M2 并行；M4 是第一个"可玩"里程碑；M5 是核心目标（多人联机）。

---

## M0 · 环境基线

**目标**：两端可启动的空壳，开发环境就绪。

**任务**：
- [x] 确认 Python 3.11+ / Node 22 可用（实测 Python 3.14.7 / Node 24.9.0）
- [x] 安装后端依赖：`fastapi` `uvicorn[standard]` `openai` `httpx`（`.venv/` 虚拟环境 + `pytest`）
- [x] `npm create vite` 初始化 `frontend/`（vue-ts 模板），安装 `pinia` `vue-router` `naive-ui`
- [x] 创建 `server/main.py`（FastAPI 空壳 + `/api/health`）与 `data/`（加入 `.gitignore`）

**产出**：`server/main.py`、`frontend/` 空壳、`data/` 目录。

**验收**：
- [x] `python server/main.py` 启动，**端口 18000**，`http://localhost:18000/api/health` 返回 `{"status":"ok"}`
- [x] `cd frontend && npm run dev` 打开页面（实测 HTTP 200，title 正常；沙箱内需放宽 EPERM，普通终端无碍）
- [x] `data/` 与 `coc-session/` 在 `.gitignore` 中

---

## M1 · 后端服务化（规则引擎 + SQLite 存档 + REST + SSE）

**目标**：规则脚本库化；**新存档格式（SQLite）**；REST API 与 SSE 事件总线；模组数据层适配 v2 格式。

**任务**：
- [x] **M1.1 FastAPI 骨架**：`config.py`（`data/config.json` / `secrets.json` 读写）、CORS、静态文件挂载
- [x] **M1.2 engine 库化**：从 `archive/coc7th-keeper-feishu/.dsh/skills/coc7th-keeper/scripts/` 复制**规则逻辑**脚本（`_common` / `roll` / `check` / `build` / `sanity` / `combat`）到 `server/engine/`，把 `main()` 提取为可导入函数（`roll_expr()` / `skill_check()` / `build_character()` / `sanity_check_roll()` / `attack_roll()` 等），保留 CLI 入口向后兼容
- [x] **M1.3 新存档格式（SQLite）**：`server/store.py` —— 每游戏一个 `data/games/<game_key>.db`，表：`games`（房间）/ `players` / `characters`（角色卡）/ `rounds`（回合）/ `messages`（叙事流）/ `actions`（行动提交与修改历史，含 `action_version`）/ `dice_log`（审计）/ `kp_notes` / `state_changes` / `perceptions`。**不沿用**旧 `coc-session/` 文件格式；`room.py` 的文件操作部分不复用（仅参考其生命周期逻辑）
- [x] **M1.4 模组数据层**：`server/modules.py` —— 扫描 `modules/` 目录，读取 **v2 格式**（`meta.json` schema `trpg-module/v1` + `scenes.json`），提供列表 / 详情 / 场景查询；现有两个 v1 模组按 `docs/模组拆解说明.md` §7 升级为 v2
- [x] **M1.5 房间 REST 化**：`api/games.py` —— 创建游戏 / 加入 / 建卡 / 角色状态 / 审计查询（另含自由掷骰 / 房主推进 / SSE 事件流）
- [x] **M1.6 并发安全**：SQLite 事务（`WAL` 模式）+ 房间级写队列（`roundman.room_lock`）
- [x] **M1.7 SSE 事件总线**：`sse.py` —— 每房间 pub/sub、30s 心跳、断线重连后回放最近事件
- [x] **M1.8 冒烟测试**：`server/tests/`（pytest）覆盖 建房间→join→build→roll→audit 全链路（39 项全绿）

**产出**：`server/` 完整后端骨架（engine / store / modules / api / sse / roundman / config）。

**验收**：
- [x] 规则逻辑回归：`roll 1d100` / `check skill "侦查" 60` / `build` 结果与归档版一致（含 CLI 向后兼容测试）
- [x] SQLite 存档可建可读；并发 10 请求不产生脏写（WAL 事务 + 房间锁；20 并发实测版本连续无丢失）
- [x] `/api/modules` 返回 v2 模组列表与场景数据（惊魂 7 场景 / 玩具跳着舞蹈来 10 场景，§6 校验清单全过）
- [x] curl 可完成：创建房间 → 加入 → 建卡 → 掷骰 → 查审计（另验证推进 / 模组场景 / 公共视图）
- [x] 两个 SSE 连接同时收到广播事件；断开重连后能回放（总线级 + 真实服务器端到端两层测试）

---

## M2 · AI 守密人（裁判 / 叙事 / 状态应用）

**目标**：替代 DSH Agent 的两阶段 AI 守密人，骰果由服务端固定，状态变动由引擎校验落库。

**任务**：
- [x] **M2.1 提示词编译**：`prompts/gm_system.md` —— 守密人十条 + 隐私铁律（Web 化）+ 五份规则速查 + 风格表（素材取自归档 skill，**无"飞书/群聊"残留表述**；另补官方规则补充 §4.7 与裁判/叙事规则自检清单 §7/§8，来源见 `docs/CoC7th规则依据与来源.md`）
- [x] **M2.2 LLM 客户端**：`gm/llm.py` —— `AsyncOpenAI` 封装、重试 2 次、失败降级（LLM 不可用时返回兜底叙事，不阻塞状态应用）
- [x] **M2.3 裁判阶段**：`gm/adjudicate.py` —— 本轮全部行动 + 场景（来自 `scenes.json` 注入）+ kp-notes → 输出 `dice_checks` JSON（`kind` 白名单：skill / sanity / luck / none）→ 服务端调引擎掷骰，**固定骰果**；LLM 不可用时关键词兜底（侦查/倾听/理智/社交/战斗等）
- [x] **M2.4 叙事阶段**：`gm/narrate.py` —— 固定骰果 + 行动 → 输出 `narrative` + `state_changes` JSON（类型白名单 + 禁用词过滤）
- [x] **M2.5 状态应用器**：`state_apply.py` —— 五类变动白名单校验落库（hp / san / item / clue / scene）；禁用词过滤（"没有异常 / 其实你漏掉"等 → 改写为"没能看出更多端倪"）；角色卡新增 `state` 段（hp/san/clues/conditions/gold）
- [x] **M2.6 场景调度**：`roundman.py` 记录 `current_scene`，场景切换时注入 `scenes.json` 数据并展示 `handouts/` 附件（`scene_change_payload` + 管线 `scene`/`handouts` 输出）

**产出**：`server/gm/` 模块（llm / prompts / adjudicate / narrate / pipeline / simulate）、`prompts/gm_system.md`、`state_apply.py`、场景调度。

**验收**：
- [x] 命令行模拟 3 类行动（技能检定 / 理智检定 / 无需检定）全部正确判定并掷骰（`python -m server.gm.simulate --mode skill|sanity|none`）
- [x] 五类状态变动全部校验落库；非法值（HP 越界、余额不足、重复线索、未知场景）被拒绝
- [x] 场景切换正确注入 `scenes.json` 数据；附件展示事件发出（s07 阁楼 → house-of-tragedies.jpeg 等）
- [x] LLM 断网时游戏不崩溃，状态应用仍完成（无 key / 坏 JSON 均降级兜底）
- [x] 提示词文件评审通过（无群聊残留、隐私铁律完整、规则自检清单已注入）

---

## M3 · 前端骨架

**目标**：五大工作区可导航，SSE 客户端与状态管理就绪。

**任务**：
- [x] **M3.1 初始化**：Vue3 + TS + Vite + Naive UI + Pinia + Vue Router（M0 脚手架 + 全量注册 + `/api` 代理）
- [x] **M3.2 五大工作区路由**：`/`（总览）、`/play/:key`（游玩）、`/characters`（角色）、`/content`（内容）、`/admin`（管理）—— 空页面可导航
- [x] **M3.3 API 客户端**：`api/client.ts`（REST 封装 + token 拦截器）、`api/sse.ts`（EventSource + 指数退避重连 + 全量校准）
- [x] **M3.4 状态管理**：`stores/game.ts`（叙事流 / 行动 / 玩家列表 / 感知）、`stores/auth.ts`（player_token / host_token 持久化）

**产出**：`frontend/` 骨架（路由 / 客户端 / stores / 空页面）。

**验收**：
- [x] 五个页面可导航（实机：5 条路由全部 200）
- [x] SSE 客户端能连接 `/api/games/{key}/events` 并收到事件；断线后自动重连（经 Vite 代理实测收到 dice_result 回放；sse.ts 指数退避 1→16s + onopen 全量校准）
- [x] token 持久化到 localStorage 并在请求头自动携带（client.ts 读 `rg_player_token` 注入 `X-Player-Token`；auth store 持久化）

---

## M4 · 单人 Web 闭环（第一个"可玩"里程碑）

**目标**：浏览器单人完整跑一局《惊魂》第一幕（AI 守密人，无人类 GM）。

**任务**：
- [x] **M4.1 总览页**：创建冒险（名称 / 模组下拉，数据来自 `/api/modules`）、加入游戏、最近游戏列表（localStorage `rg_recent_games`）
- [x] **M4.2 角色页**：建卡三步（预制角色 `getModulePregens` / AI 草稿 `action:auto` / 手动填写九属性）、角色卡展示（属性 / 派生 / 技能 / 物品 / 理智历史）
- [x] **M4.3 游玩页**：`NarrationStream`（按回合分组的叙事流：场景 / 行动回显 / 判定卡片 / 叙事 / 状态变动 / 附件图片）、`ActionInput`（提交 / 修改 / 等待态）、`DiceCard`、`StateChanges`、自由掷骰按钮、`PlayerList`、`PerceptionPanel`
- [x] **M4.4 单人联调**：单人模式提交行动 → 自动推进（`roundman.pipeline_lock` + `gm/pipeline.run_round`）→ 裁判 → 掷骰 → 叙事 → 落库 → 广播（dice_result / narration / state_changed / perception / scene_changed / handout / round_started）
- [x] **M4.5 消息与附件数据面**：`GET /api/games/{key}/messages`（叙事流全量校准/刷新恢复）+ `GET /api/modules/{id}/handouts/{path}`（附件图片服务，`NarrationStream` 渲染、失败回退文本）

**产出**：可玩的单人 Web 版（功能优先，无美术）。

**验收**：
- [x] 浏览器单人跑完《惊魂》第一幕：建卡 → 行动 → 检定 → 叙事 → HP/SAN 落库（HTTP 全链路实机验证：开局注入 s01 → 建卡 → 行动自动推进 → 轮次+1 → 叙事流/审计落库；HP/SAN 落库由管线+状态应用测试覆盖）
- [x] 叙事流 / 审计写入 SQLite；审计可查（`GET /api/games/{key}/messages` + `/audit`）
- [x] 失败检定只显示"没能看出更多端倪"，无 KP 数据泄漏（禁用词过滤 + 事件不含 kp_notes）
- [x] **人工测试（浏览器实测）通过 2026-08-31**：创建冒险 → 开局注入 → 建卡 → 行动自动推进 → 技能/理智检定 → 叙事 → 轮次推进（至第 6 轮）→ 失败措辞合规 → 刷新重连叙事完整 → 非法表达式/空行动被拒 → 附件图片可访问。期间修复两处：顶栏「游玩」跳转错配（`aa62950`）、理智检定卡片渲染 + 判定存档（`ceaab9b`）

---

## M5 · 多人联机（核心目标）

**目标**：2–4 人浏览器联机，回合制 + 实时同步 + 隐私隔离。**AI 是唯一守密人，不设人类 GM**；房主仅管理房间；开发者经只读监视接口查看对话。

**任务**：
- [x] **M5.1 邀请与身份**：`auth.py` —— 邀请链接（含一次性凭证、可轮换）、角色认领（房主=玩家1）、玩家 token、可选访问密码（盐化 sha256）
- [x] **M5.2 回合收集器**：`roundman.py` —— 全活跃玩家提交后自动推进（M4 已实现）；**未提交玩家保留等待、无倒计时**（已确认 a-A）；**房主可强制推进（仅防卡死，不参与剧情、不看 kp-notes）**（已确认 b-A）；暂离不阻塞（away/back）；**行动修改不限制次数**（已确认 c-B：每次修改递增 `action_version` 并写入 `actions` 表供审计，AI 只读最后一次）
- [x] **M5.3 私密感知与视图过滤**：`state_apply.py` + `sse.py` —— `perception` 事件只推给目标 uid（后端 to_uid 定向 + 前端 `?token=` 绑定 + store 二次过滤）；玩家视图响应不含 kp 字段
- [x] **M5.4 房主管理**（非 GM，不参与剧情）：分享链接（复制/轮换）、移除玩家（kick + player_removed 广播）、**强制推进（防卡死，已确认 b-A）**、查看房间状态
- [x] **M5.5 开发者监视接口（只读）**：`api/dev/*`（需独立 `dev_token`）—— 监视对话流（`messages`）、`kp_notes`、`dice_log` 审计、LLM 调用记录（`llm_log` 表 + 管线记录）、房间状态。**只读，不参与游戏，不修改任何状态**（players 输出剔除 token_hash）
- [x] **M5.6 多人端到端测试**：pytest（test_m5.py 11 项）+ HTTP 3 玩家实机脚本

**产出**：多人联机版（含房主管理 + 开发者监视接口）。

**验收（8 条）**：
- [x] 1. 创建者建桌 → 获得邀请链接（创建者 = 房主，非 GM）；轮换后旧码失效
- [x] 2. 3 名玩家分别用浏览器打开邀请链接加入（`?key=&invite=` 自动加入），各建卡 / 认领角色
- [x] 3. 每人提交自然语言行动；全部活跃玩家提交后自动推进；判定卡片同步到所有人
- [x] 4. 叙事 + 状态变动同步；`dice_log` 可查；叙事流完整（刷新可恢复）
- [x] 5. 某玩家暂离后不阻塞回合；回来恢复
- [x] 6. 私密线索只对目标角色可见；玩家身份调用任意 API 取不到 kp 字段与 invite_token
- [x] 7. 刷新页面（掉线重连）后经全量拉取恢复叙事流（messages 端点 + SSE 回放去重）
- [x] 8. 开发者用 `dev_token` 可只读查看对话流 / kp-notes / 审计 / LLM 记录；**无法修改任何状态**（测试断言调用后状态不变）

---

## M6 · 部署加固

**目标**：可对外开团（局域网 / 内网穿透 / 云服务器三档）。

**任务**：
- [x] **M6.1 访问控制**：访问密码（哈希存储——M5.1 盐化 sha256 已实现，加入校验测试覆盖）、`share_url` 配置 + 前端 `VITE_SHARE_URL` 邀请链接外网化
- [x] **M6.2 HTTPS**：`docs/部署/HTTPS反代.md` —— Caddy（自动证书，SSE 透传默认正常）+ Nginx 反代配置（`proxy_buffering off` 关键）+ 证书获取
- [x] **M6.3 启动与打包**：`start-web.ps1` / `start-web.bat`（首次自动构建前端 + 启动 / `-Dev` 开发模式）；`Dockerfile` 单容器（多阶段：Node 构建前端 → python:3.12-slim + uvicorn + 静态产物）+ `.dockerignore`；**SPA 深链兜底**（非 `/api` 404 回 `index.html`，`/play/xxx` 可直接访问）
- [x] **M6.4 部署文档**：`docs/部署/部署指南.md` —— 本地局域网（host 0.0.0.0 + 防火墙）/ SakuraFrp / Cloudflare Tunnel（`cloudflared tunnel --url`）/ 云服务器（域名+反代+systemd/Docker），对照计划书 §6 三档对比，含排错 FAQ
- [x] **M6.5 安全清单**：`docs/部署/安全清单.md` —— `secrets.json` 权限、`data/` 不公开（未挂载+反代兜底）、**访问限流中间件**（每 IP 滑动窗口，config 可配，超限 429，测试覆盖）、日志脱敏（uvicorn `log_level=warning` 关访问日志）、`dev_token` 管理（默认关闭）

**验收**：
- [x] 异地玩家经 HTTPS 输入密码加入游戏并正常跑一轮（密码加入在 M5 测试覆盖；HTTPS/反代按 `docs/部署/HTTPS反代.md` 配置后可达——需部署环境实测，本环境无公网/浏览器）
- [x] 部署文档覆盖三档方案，含排错步骤（`docs/部署/部署指南.md` §7 FAQ + 三档对比表）

---

## M7 · 扩展（决策已定 2026-08-31）

| 编号 | 内容 | 决策 | 说明 |
|---|---|---|---|
| M7.1 | 世界书 | ❌ **不开发** | 目前仅考虑模组，不做世界书。如有需求，按 `docs/模组拆解说明.md` 新增的「世界书拆解格式（预留）」节拆出专门的世界书文档（固定格式 + 阅读逻辑） |
| M7.2 | 长期记忆 | ⏸ **可选 · 仅 API 接入** | 本期不开发。将来若做：仅考虑 API 接入，**不本地部署模型**承担算力/思考（embedding 语义召回等） |
| M7.3 | WebRTC 玩家直连 | ❌ **不做** | 与现有联机逻辑（HTTP + SSE）属并行方案，保持唯一稳定联机方式即可 |
| M7.4 | DND 5e 支持 | ❌ **暂不开发** | 留作后期可扩展想法（`system: dnd5e`，d20 + 修正 ≥ DC，优势/劣势 2d20，参考 DiceFrame `check_mechanic` JSON 声明范式） |

### 额外任务（✅ 已完成 2026-08-31，随 M7 决策一并落地）

- [x] **局内聊天框**：玩家可随时对话；与自由掷骰整合——同一输入框发文本或掷骰（联掷结果入 `dice_log` 审计并随聊天消息广播分享）。`POST /api/games/{key}/chat`（body `{text, expr?}`）+ SSE `chat` 事件 + `ChatPanel` 组件；消息落 `messages`（kind=chat），刷新恢复；store 独立 `chats` 流。
- [x] **视觉 UI 优化（暗色主题）**：naive-ui `darkTheme` + 定制 `themeOverrides`（暗紫主色 + 高对比文字）、全局暗色调 `style.css`、暗色顶栏/页脚；游玩页新增**常驻信息区块**——场景栏（场景名/地点/摘要/回合/阶段）、角色信息栏（我的 HP/SAN/派生/线索/物品）、玩家列表、私密感知、行动、聊天；经 headless Edge 截图 + 视觉模型分析验证（前后对比）。
- [x] **线索台账（更新）**：建团时从模组 `clues.md` 解析生成每局**线索台账副本**（`clue_ledger` 表）；玩家获得线索时状态 `locked→unlocked`（记录时间/获得者）；**管理员**经 dev 接口 `/api/dev/games/{key}/clues` 查询（`total/unlocked/locked`）；**AI 守密人（KP）**在裁判/叙事阶段自动注入台账（AI 易读格式，含已获得标记），供调度与记录。

### 后续增强（✅ 已完成 2026-09-01，随真实 LLM 接入一并落地）

> 配置真实 LLM（OpenCode Go / MiMo-V2.5）后实测发现：推理模型先输出 `reasoning_content` 再输出 `content`，长叙事易被 `max_tokens=2000` 截断。本次拓充上限并新增「截断 → 请求房主调高」闭环，同时立下 **reasoning_content 隐私铁律**。

- [x] **max_tokens 拓充（可配 + 每局可覆盖）**：`data/config.json` `model.max_tokens` 默认 **4000**（原 2000）；`games` 表新增 `max_tokens` 列（`_migrate` 自动 ALTER，NULL=用 config 默认）；`LLMClient.from_config(max_tokens=...)` 支持每局覆盖。
- [x] **截断检测**：`llm.chat_detailed()` 返回 `LLMResult(content/truncated/finish_reason)`——`finish_reason=length` 标记截断；`chat()` 保持返回最终输出文本（向后兼容）。
- [x] **截断 → 请求房主调高**：管线聚合 `truncated` 标志 → 落一条 `system` 消息（叙事流可见，刷新可恢复）+ SSE `llm_limit_hit` 事件（round/stage/当前上限/建议值）→ 房主面板黄色横幅「一键调高到 N」；新端点 `POST /api/games/{key}/llm-limit`（房主，1000–32000，越界 400，非房主 401）→ 广播 `llm_limit_changed` 同步所有在线玩家；公共视图暴露 `max_tokens`。
- [x] **reasoning_content 隐私铁律（用户明确要求）**：LLM 客户端**只读取 `message.content`（最终输出）**，`reasoning_content`（思考过程）一律不读、不返回、不落库、不广播——content 为 None 时返回 None，绝不降级用思考内容；测试断言思考内容不出现在任何返回值/消息/事件中。
- [x] 前端：GmPanel 新增「AI 输出上限」输入 + 保存 + 截断横幅一键调高；NarrationStream 渲染 `system` 消息（warning 样式）；game store 处理 `llm_limit_hit`/`llm_limit_changed`（按签名与服务端持久化消息去重）。
- [x] 测试：`server/tests/test_llm_limit.py` 7 项（截断检测、reasoning 不泄露、正常完成、config 优先级、管线透传、调限端点鉴权/越界、system 消息落库）；全套 **91 项绿**。
- [x] 部署文档：`docs/部署/部署指南.md` 新增 §3.3 localtunnel（免安装免注册临时测试）+ §3.4 隧道地址易变对照表 + FAQ 确认页条目。

---

## 当前待办 · 下一步（未完成项，按需推进）

> 功能开发已到收尾；以下为**验证/体验/可选扩展**项。勾选状态如实反映完成进度。

- [x] **真实浏览器多人复核**：✅ **headless 双浏览器自动化版已通过（2026-09-01）**——新建受控房间（the-haunting）→ 房主（桌面 1440）+ 邀请玩家（移动 390）双 Edge → 双建卡 → 聊天文本+联掷 → 双提交自动推进 4 轮真实 AI 叙事 → 每轮双视角截图（`.tmp/shots/D3-r*.png`）；验收：叙事流每轮递增、**聊天流隔离 `chatInNarration=0`**、移动端单列可用。用户真人体验观感仍可选（`.\start-web.ps1 -Dev`）
- [ ] **Docker 镜像构建验证**：`docker build -t coc-web . && docker run -p 18000:18000 -v coc-web-data:/app/data coc-web`（本开发环境无 docker，需在本地执行）
- [ ] **异地 HTTPS + 访问密码加入一轮**：按 `docs/部署/部署指南.md`（含 §3.3 localtunnel / §3.4 地址易变对照）+ `HTTPS反代.md` 部署后实测（需公网/云环境）
- [x] **配置真实 LLM 体验 AI 叙事**：已配置 **OpenCode Go / MiMo-V2.5**（`data/config.json` `model.base_url=https://opencode.ai/zen/go/v1` + `model=mimo-v2.5`，`data/secrets.json` 填 `api_key`；实测普通对话 + JSON 模式均通）；不配则离线兜底（规则判定+模板叙事，功能完整）
- [ ] **（可选）世界书第一份**：确认需要后，按 `docs/模组拆解说明.md` §8 预留格式拆解，新建 `server/worlds.py` 读取层
- [ ] **（可选）长期记忆（仅 API）**：每 N 轮 LLM 摘要注入上下文；embedding 语义召回按需（不本地部署模型）

---

## §附 · 回合规则（已确认）

> 审核反馈第 3 点"需要进一步解释"。以下为回合规则的完整说明，确认后写入 M5 细节。

### 3.1 单人模式
提交一条行动 → **立即自动推进**（AI 裁判 → 服务端掷骰 → 叙事 → 状态落库 → 下一轮）。无等待。

### 3.2 多人模式（核心流程）
```
第 N 轮开始（广播 round_started）
  ├─ 每个活跃玩家提交自己的行动（可修改，有次数上限；AI 只读最后一次）
  ├─ 推进条件：所有活跃玩家都已提交  → 自动推进
  │            或 房主强制推进（防卡死，已确认 b-A）
  ├─ AI 裁判：整批决定谁需要检定、用什么技能、目标值（输出 dice_checks JSON）
  ├─ 服务端掷骰一次，固定结果（写 dice_log）
  ├─ AI 叙事：基于固定骰果生成叙事 + 状态标签
  ├─ 引擎校验状态变动 → 落库（SQLite）
  └─ 广播：判定卡片 + 叙事 + 状态变动 + 私密感知 → 第 N+1 轮
```

### 3.3 需要你确认的三个子项

| 子项 | 方案 A（默认建议） | 方案 B | 方案 C | 状态 |
|---|---|---|---|---|
| **a. 未提交玩家** | 保留等待，**无倒计时**（回合卡住直到提交或房主推进） | 超时自动推进（如 10 分钟未提交视为跳过本轮） | 超时自动标记暂离 | ✅ **已确认 a-A** |
| **b. 房主强制推进** | 允许（房主仅防卡死，不参与剧情、不看 kp-notes） | 不允许（只能等玩家提交） | 允许 + 需全员同意 | ✅ **已确认 b-A** |
| **c. 行动修改上限** | 每轮最多修改 3 次 | 不限制 | 提交后不可修改 | ✅ **已确认 c-B（不限制）** |

> **c 的详细解释**：见下方"行动修改上限（c）说明"。

### 3.4 行动修改上限（c）说明

**"行动修改"是什么**：多人模式下，玩家提交行动后、回合推进前（即其他玩家还没全部提交时），可以**修改自己已提交的行动内容**。例如先写"我检查柜子"，看到场景变化后改成"我检查书桌"。AI 裁判时只读**最后一次**提交的版本。

**为什么需要上限**：
- 修改本身**不推进回合**（推进只取决于"是否已提交"），所以无限修改不会卡住别人，但会带来三个问题：
  1. **反复横跳**：玩家看到别人行动后无限改自己的行动，拖慢团队节奏（CoC 是协作游戏，但过度博弈体验差）；
  2. **审计膨胀**：每次修改都要记录版本（`action_version`），无限修改导致存储与审计噪音；
  3. **实现复杂度**：无上限意味着服务端要支持任意次版本记录。

**三个方案权衡**：

| 方案 | 体验 | 风险 | 实现 |
|---|---|---|---|
| **A：每轮最多改 3 次** | 足够日常微调（补充细节 / 修正错字 / 根据新信息调整），通常 1–2 次就够 | 极端情况（写错 3 次）只能等下一轮 | 简单：`action_version` 计数，超 3 拒绝 |
| **B：不限制** | 最自由 | 可被滥用（无限横跳）；审计膨胀 | 需支持任意版本记录 |
| **C：提交后不可改** | 最严格 | 玩家怕写错而**不敢提交**，反而拖慢回合（提交 = "我准备好了"的信号，不可改会让人犹豫） | 最简单 |

**建议：A（每轮最多 3 次）**。补充细节：上限是**每轮**的（每轮重置），不是累计；修改不触发任何检定或推进；AI 只读最后一次版本。

> ✅ **已确认 c-B（不限制）**：行动修改不限制次数。实现：每次修改递增 `action_version` 并写入 `actions` 表（提交 / 修改历史，审计可查）；AI 只读最后一次版本；修改不触发检定或推进。`actions` 表在 M1.3 存档设计中加入。

---

## 待办 · 后续优化（已完成 2026-08-31，随 M5 一并落地）

> M4 人工测试期间用户提出的改进需求，已于推进 M5 时一并完成实现并验证。

### TODO-A：AI 裁判自然语言技能推断（✅ 已完成）

- **现状（完成前）**：离线兜底裁判靠关键词规则，玩家需在行动里写括号技能名才稳定命中。
- **目标**：玩家纯自然语言行动 → AI 自行推断技能 → 查角色卡取目标值 → 掷骰 → 叙事，**无需括号标注**。
- **已实现**（`server/gm/adjudicate.py` 三层判定，测试 `test_gm.py:test_fallback_natural_language_inference` 覆盖）：
  1. 显式技能名检索（含括号标注兼容）
  2. 理智特判（看见词+恐怖词组合 / 明确理智词 / `san`）
  3. 意图短语规则（翻找/撬锁/侧耳/搭讪/套话/威胁/察言观色/射击/格斗/攀爬/急救等）
  4. 其余 → none
- **验收四用例全部通过**：`我翻遍整个房间寻找暗门`→侦查；`我撬开抽屉的锁`→开锁；`我盯着那团血肉模糊的东西`→理智检定；`我沿着走廊走着`→无需检定。

### TODO-B：M4 遗留小项（✅ 已完成）

- 自由掷骰结果落 `messages` 表（kind=dice，刷新后可恢复）——已完成（TODO-B#1）。
- 凭证按游戏多槽存储（`rg_tokens` map，最近游戏直进不再凭证错配）——已完成（TODO-B#2，随 M5.1）。

---

## 附：审核确认点（更新）

1. ✅ 端口 18000 —— 已确认
2. ✅ 不设人类 GM；AI 唯一守密人；开发者监视接口（只读）—— 已确认
3. ✅ 回合规则 —— **已确认**：a-A（未提交保留等待、无倒计时）+ b-A（房主可强制推进防卡死）+ c-B（行动修改不限制，AI 只读最后一次）
4. ✅ 存档不沿用，新格式 SQLite —— 已确认
5. ✅ 本期仅 CoC7th；DND5e 后续 —— 已确认
6. ✅ 模组拆解格式与说明文档 —— 已编译 `docs/模组拆解说明.md`，请一并审核
7. ✅ 全部由 AI 编写，不提供工期 —— 已确认

> 审核通过后，请在新对话中说明"按 MILESTONES.md 从 M0 开始"，即可开始编写。
