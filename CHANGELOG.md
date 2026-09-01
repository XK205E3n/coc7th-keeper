# 变更日志（Changelog）

> 记录跑团 Web 平台（`server/` + `frontend/`）的更新条目。版本按里程碑推进：
> `M0 环境基线` → `M1 后端服务化` → …（详见 `MILESTONES.md`）。
> 每次里程碑完成即提交并推送到 GitHub（origin master）。

---

## [M0 · 环境基线] - 2026-08-31 ✅ 完成

首批脚手架落地。

- 新增根目录 `.gitignore`：忽略 `data/`、`coc-session/`、`.venv/`、`node_modules/`、SQLite 运行文件、pytest 缓存、旧会话记录等。
- 新增 `data/` 运行时数据目录（`config.json` / `secrets.json` / `games/`，不入库）。
- 新增后端虚拟环境 `.venv/`（Python 3.14.7），安装 `fastapi 0.141` `uvicorn 0.52` `openai 3.6` `httpx 0.28` `pytest 9.1`。
- 新增 `frontend/` Vite 脚手架（vue-ts 模板，vite 8），安装 `pinia` `vue-router` `naive-ui`。
- 新增 `server/main.py` FastAPI 入口：`/api/health` 健康检查、CORS、静态挂载，默认端口 **18000**。
- 验证：`python server/main.py` 启动、`/api/health` 返回 ok；`npm run dev` 打开页面（HTTP 200）。`data/` 与 `coc-session/` 均入 `.gitignore`。

---

## [M1 · 后端服务化] - 2026-08-31 ✅ 完成

后端骨架：规则引擎库化 + SQLite 存档 + REST + SSE，39 项 pytest 全绿。

- `server/config.py`（M1.1）：`data/config.json` / `secrets.json` 读写（服务端口 / 模型接口 / CORS / API Key），`DATA_DIR` 环境变量可覆盖（测试隔离）。
- `server/engine/`（M1.2）：从归档 skill 复制 `_common` / `roll` / `check` / `build` / `sanity` / `combat` 并库化（`roll_expr()` / `skill_check()` / `luck_check()` / `build_character()` / `sanity_check_roll()` / `perform_san_check()` / `attack_roll()` / `initiative()` / `major_wound_roll()`），CLI 入口保留向后兼容（回归测试覆盖）。
- `server/store.py`（M1.3）：SQLite 存档层（WAL 模式、每游戏 `data/games/<key>.db`、games / players / characters / rounds / messages / actions / dice_log / kp_notes / state_changes / perceptions 十表）。行动提交/修改递增 `action_version` 并写入 `actions` 历史（审计可查）；回合推进自动清空提交。
- `server/modules.py` + `modules/`（M1.4）：模组 v2 数据层（`trpg-module/v1` + `scenes.json`），扫描 `modules/`；两个 v1 模组升级为 v2——**惊魂**（7 场景，含地下室高潮 s06）、**玩具跳着舞蹈来**（10 场景，含阁楼附件/最终战），通过拆解说明 §6 校验清单；`handouts/` 附件按场景声明。
- `server/roundman.py`（M1.6）：房间级写锁（`room_lock`）+ 生命周期（create / join / advance）+ 公共视图（隐私过滤：不含 kp_notes / dice_log / password_hash）。
- `server/sse.py`（M1.7）：每房间 pub/sub 事件总线（30s 心跳注释行、每房间 50 条历史回放、perception 私密事件按 uid 定向 + 回放过滤）。
- `server/api/games.py` + `server/api/modules.py`（M1.5）：REST 端点 16 路径（创建 / 公共视图 / 加入 / 建卡 auto+直传 / 角色查询 / 行动提交 / 自由掷骰 / 审计 / 房主推进 / SSE / 模组列表详情场景预制角色），token 鉴权（X-Player-Token / X-Host-Token）。
- `server/tests/`（M1.8）：pytest 冒烟 39 项——引擎回归 + CLI 向后兼容、存档 CRUD + 20 并发写锁测试 + WAL 并发读、模组 v2 校验、REST 全链路、SSE 总线级（双连接/定向/重连回放）与真实 uvicorn 端到端。
- 验收：curl 全链路（创建→加入→建卡→掷骰→查审计→推进→模组场景→公共视图）通过；2.5 小时前清理旧项目会话数据（`archive/` 内 `coc-session*` 旧存档、运行日志、`dist/` 构建产物、`.agent-teams/` 旧会话归档、pytest 缓存残留）。

---

## 环境备注（开发者）

- 沙箱（DSH Desktop）内：`python -m venv`/`pip install`/`npm run dev`（vite 用 child_process）+ `pytest`（创建临时目录）需完整文件访问权限；普通终端无此限制。
- pytest 需 `--basetemp=.tmp/pytest` 或完整权限（pytest.ini 已配置 basetemp）。
- 端口 18000 为约定端口（`data/config.json` `server.port` 可改）。

---

## [M2 · AI 守密人] - 2026-08-31 ✅ 完成

两阶段 AI 守密人（裁判 → 服务端固定骰果 → 叙事 → 状态落库），14 项测试全绿。

- `prompts/gm_system.md`（M2.1）：守密人十条 + 隐私铁律（Web 化）+ 五份规则速查 + 风格表，**无飞书/群聊残留**；新增 §4.0 特性/派生公式、§4.7 官方规则补充（fumble 96-100 / 追加检定 / 幸运点 / 穿刺 / 重伤阈值 / 理智恢复 / 技能成长，含引擎偏差说明）、§7 裁判规则自检清单、§8 叙事合规清单（AI 思考流程注入）。
- `docs/CoC7th规则依据与来源.md`：规则口径溯源（Keeper Rulebook / Quick-Start / Investigator Handbook）+ 引擎偏差表。
- `server/gm/llm.py`（M2.2）：AsyncOpenAI 封装（DeepSeek/Ollama/硅基流动兼容），重试 2 次，无 key/断网 → 离线降级。
- `server/gm/adjudicate.py`（M2.3）：行动+场景+kp-notes → `dice_checks` JSON（kind 白名单 skill/sanity/luck/none、每玩家一条、target 从角色卡补齐）；LLM 不可用/坏 JSON → 关键词兜底（侦查/倾听/理智/社交/战斗/急救）。
- `server/gm/narrate.py`（M2.4）：固定骰果 → `narrative` + `state_changes`（类型白名单 + 禁用词过滤）；兜底叙事按档位生成（失败 → "没能看出更多端倪"）。
- `server/state_apply.py`（M2.5）：hp/san/item/clue/scene 五类校验落库（越界/余额不足/重复线索/未知场景拒绝）；角色卡新增 `state` 段（hp/san/clues/conditions/gold）；SAN 归 0 → 永久疯狂、HP 归 0 → 重伤表。
- `server/gm/pipeline.py`：回合管线（收集行动 → 裁判 → 引擎掷骰 → 叙事 → 落库 → 返回事件数据），M4 单人自动推进将调用。
- `server/gm/simulate.py`：CLI 模拟三类行动（`--mode skill|sanity|none`）。
- 场景调度（M2.6）：`roundman.set_current_scene` + `scene_change_payload`；管线场景切换注入 `scenes.json` 并带出 `handouts` 附件。
- 测试：`server/tests/test_gm.py` 14 项（提示词评审 / 裁判三态 / LLM 规范化与降级 / 五类状态校验 / 场景切换 / 断网管线 / CLI 模拟）。

---

## [M3 · 前端骨架] - 2026-08-31 ✅ 完成

Vue3 前端骨架（五大工作区 + SSE 客户端 + stores），构建通过 + 实机验收。

- `vite.config.ts`：`/api` → `http://localhost:18000` 开发代理。
- `src/router.ts` + `src/App.vue`：五条懒加载路由（`/` 总览、`/play/:key` 游玩、`/characters` 角色、`/content` 内容、`/admin` 管理）+ 顶栏导航。
- `src/api/client.ts`：REST 封装（`apiFetch<T>`、token 注入、`ApiError` 带 detail、12 个便捷方法、`STORAGE_KEYS` 常量）。
- `src/api/sse.ts`：EventSource + 8 事件统一回调 + onerror 接管重连（1→2→4→8→16s 指数退避）+ onopen 回调 `onReconnect()`（全量校准）。
- `src/stores/auth.ts` / `src/stores/game.ts`：token 持久化（localStorage）；叙事流/行动/玩家/感知状态机（`perception.to` 过滤私密）。
- `src/views/*.vue` ×5 空页面（Overview 演示 health 检查）。
- 验收：`npm run build`（vue-tsc + vite）通过；实机五路由 200、代理 health ok、SSE 经代理收到 dice_result 回放。
- 已知项：naive-ui 全量引入 chunk 较大（M4 可分包）；EventSource 无法带自定义头，定向感知依赖 `perception.to` 过滤（store 已实现）。

---

## [M4 · 单人 Web 闭环] - 2026-08-31 ✅ 完成

第一个"可玩"里程碑：浏览器单人跑《惊魂》第一幕（AI 守密人，无人类 GM），58 项 pytest 全绿。

- **后端自动推进（M4.4）**：`POST /actions` 提交后，活跃玩家全部就绪（单人即提交即推进）→ `roundman.pipeline_lock` 串行执行 `gm/pipeline.run_round`（裁判 → 引擎掷骰 → 叙事 → 状态落库）→ 广播 `dice_result` / `narration` / `state_changed` / `perception`（定向）/ `scene_changed` / `handout` / `round_started`；`kp_notes` 只落库绝不广播。
- **消息端点**：`GET /api/games/{key}/messages?last=N`（需玩家 token）——SSE 重连/刷新后的全量校准，叙事流恢复。
- **开局注入**：建团带 `module_id` 时 `current_scene`=首场景 + 开场消息（scene 消息）+ kp-notes.md 全文注入守密人上下文。
- **附件图片服务**：`GET /api/modules/{id}/handouts/{path}`（FileResponse，防路径穿越）。
- **前端**：Overview（创建冒险/模组下拉/加入/最近游戏 localStorage）、Characters（建卡三步：预制/AI 草稿/手动九属性 + CharacterSheet 展示）、Play（NarrationStream 按回合分组 + ActionInput 提交/修改/等待态 + DiceCard + StateChanges + 自由掷骰 + PlayerList + PerceptionPanel + 附件图片渲染）、Content（模组列表+场景数）。
- **store 增强**：`loadMessages` 合并去重（内容签名 + 本地 id 基址 1e9）、`onEvent` 支持 scene_changed/handout/state_changed、perception 定向过滤 + 同文本去重。
- 验收：HTTP 全链路实机（建团→开局 s01→建卡→行动→自动推进→轮次+1→叙事流/审计落库→失败措辞合规）；前端 `npm run build` 通过；58 项测试全绿。
- 已知项：房主即玩家 1（create 的 host_token 兼作 player_token）；自由掷骰不落 messages 表（刷新后仅审计可查）；最近游戏直进若 token 不匹配有顶部警告（M5 按游戏存 token）。

---

## [M5 · 多人联机（核心目标）+ TODO-A/B] - 2026-08-31 ✅ 完成

2–4 人浏览器联机：回合制 + 实时同步 + 隐私隔离 + 房主管理 + 开发者只读监视。AI 唯一守密人，不设人类 GM。**70 项 pytest 全绿** + 3 玩家 HTTP E2E 实机验收。

- **M5.1 邀请与身份（`server/auth.py` 新建）**：密码盐化 sha256；邀请凭证（轮换制，旧码立即失效，不出现在公共视图）；`POST /join` 必须携带 `X-Join-Token`，设了访问密码则校验密码（401 邀请无效 / 403 密码错误 / 409 名字占用 / 404 房间不存在）；`POST /invite` 房主轮换。
- **M5.2 回合收集器**：全活跃玩家提交自动推进（M4 已有）；`away/back` 暂离不阻塞；未提交保留等待无倒计时；房主强制推进（`advance`，仅防卡死）；行动修改不限制（action_version 审计）。
- **M5.3 私密感知与视图过滤**：SSE 支持 `?token=` 查询参数（EventSource 带不了头）绑定 uid 定向；`perception` 只推目标；公共视图不含 kp 字段与 invite_token；store 按 `to===uid` 二次过滤。
- **M5.4 房主管理**：邀请链接复制/轮换（GmPanel）、移除玩家（`kick` + `player_removed` 广播 + 被踢 token 失效，不能踢房主）、强制推进、房间状态。
- **M5.5 开发者监视接口（`api/dev.py` 新建，只读）**：须 `X-Dev-Token`（data/config.json `dev_token`，默认关闭）；`/dev/games` 列表、`/dev/games/{key}/{messages|kp_notes|dice_log|state_changes|perceptions|llm_log|room}`；players 剔除 token_hash；测试断言调用后状态不变（只读）。
- **LLM 调用记录**：store 新增 `llm_log` 表；pipeline 对 adjudicate/narrate 分别记录（stage/ok/ms/detail），离线也记（ok=False）。
- **TODO-A（✅）**：离线兜底裁判三层自然语言推断（显式技能名 / 理智特判 / 意图短语 / 其余 none），验收四用例全过（test_gm.py 15 项）。
- **TODO-B（✅）**：自由掷骰落 `messages`（kind=dice，刷新可恢复）；凭证按游戏多槽存储（`rg_tokens` map），最近游戏直进不再凭证错配。
- **store 迁移**：games 表 `invite_token` 列（`_migrate` 自动 ALTER）、`delete_player`、llm_log 表。
- 前端：auth store 多槽化；sse `?token=`；Overview 邀请链接 `?key=&invite=` 自动加入 + 邀请码/密码输入；GmPanel（邀请/强制推进）；PlayerList 暂离切换 + 房主移除；Admin 开发者监视页；game store 支持 player_status/player_removed。
- 测试：`server/tests/test_m5.py` 11 项（邀请/密码/轮换/暂离/全员推进/踢人/SSE token/自由骰落库/dev 只读/llm 记录/凭证隔离）；test_api.py 适配邀请制；全套 **70 项绿**。
- 验收：3 玩家 HTTP E2E（带密码建团 → 邀请加入 → 双建卡 → 未提交等待 → 暂离不阻塞 → 全员活跃推进 round+1 → 回归 → 踢人 → 凭证隔离 → 刷新恢复叙事流）。
- 已知项：M6 继续加固（访问限流/日志脱敏/HTTPS/部署文档）；dev_token 生产环境应高强度随机；前端多槽 token 迁移自动清理旧单槽键。

---

## [M7 决策 + 额外任务（聊天 / 视觉优化 / 线索台账）] - 2026-08-31 ✅

M7 四子项按用户细则定案（7.1 世界书不开发、7.2 记忆仅 API 可选、7.3 不做 WebRTC、7.4 不开发 DND5e——详见 `MILESTONES.md`），并完成三条额外任务。**88 项 pytest 全绿** + 前端构建通过 + headless 截图视觉验证。

- **局内聊天（新增）**：`POST /api/games/{key}/chat`（`{text, expr?}`）——纯文本或联掷（`expr` 时骰果入 `dice_log` 审计并随消息广播）；SSE 新增 `chat` 事件；消息落 `messages`（kind=chat，刷新恢复）；前端 `ChatPanel`（与自由掷骰整合：输入框 + 发送/掷骰按钮，骰子带 🎲 结果行）；game store 拆分独立 `chats` 流（不进叙事流）。
- **视觉 UI 优化（暗色主题）**：App.vue 包 `n-config-provider` + naive-ui `darkTheme` + 定制 `themeOverrides`（暗紫主色 `#a78bfa`、深底 `#121016`/卡片 `#1a1720`、高对比文字）；全局 `style.css` 暗色调；暗色顶栏/页脚；游玩页常驻信息区块——**场景栏 SceneBar**（场景名/地点/摘要/回合/阶段）、**角色信息栏 CharacterBar**（我的 HP/SAN/MP/MOV/DB + 线索/物品数，状态变动后自动刷新）、玩家列表、私密感知、行动、聊天。经 Edge headless + modlens 视觉分析验证渲染与对比。
- **线索台账（用户建议更新）**：`modules.list_clues` 解析模组 `clues.md` → 建团时初始化每局台账副本（store `clue_ledger` 表：id/文案/locked-unlocked/获得时间与者）；获得线索经 `state_apply` 解锁；**管理员**经 `/api/dev/games/{key}/clues`（total/unlocked/locked）查询；**KP**：管线裁判+叙事阶段自动注入台账文本（`[C-01] [已获得] 文案…`，AI 易读格式，绝不进玩家视图）——顺带修复 M2 遗留：narrate 阶段此前未注入 KP 上下文。
- **修复（生产 bug）**：前端静态托管下 SPA 深链 `/play/xxx` 直接访问 404——`main.py` 加非 `/api` 404 → `index.html` 兜底（M6.3 完善）。
- 测试：`test_m7.py` 7 项（聊天文本/联掷审计/SSE 广播、台账初始化/解锁/幂等、dev 查询、KP 注入）+ 限流器测试间隔离修复（conftest 每测试换全新默认限流器）；全套 **88 项绿**。
- 已知项：多人聊天/视觉在真实浏览器的最终观感建议人工复核（本环境已用 headless 截图 + 视觉模型验证）；世界书按 `docs/模组拆解说明.md` §8 预留格式，需要时再拆。

---

## [M6 · 部署加固] - 2026-08-31 ✅ 完成

可对外开团（局域网 / 内网穿透 / 云服务器），**76 项 pytest 全绿**。

- **M6.1 访问控制**：每局访问密码哈希存储（M5.1 已实现，测试覆盖）；`data/config.json` `share_url` 配置位 + 前端 `VITE_SHARE_URL` 环境变量——邀请链接外网化（缺省自动用浏览器当前地址）。
- **M6.2 HTTPS**：`docs/部署/HTTPS反代.md`——Caddy 一行 `reverse_proxy` + 自动证书；Nginx 反代完整配置（`proxy_buffering off` / `proxy_read_timeout 3600s` 保证 SSE 透传）+ certbot 获取证书 + 常见坑。
- **M6.3 启动与打包**：`start-web.ps1`（UTF-8 BOM，双版本兼容）/ `start-web.bat`（`chcp 65001`）——首次自动 `npm install && npm run build` 后启动，`-Dev` 开发模式；`Dockerfile` 多阶段（node:22 构建前端 → python:3.12-slim + uvicorn 单容器托管静态产物，`VOLUME /app/data`）+ `.dockerignore`。
- **M6.4 部署文档**：`docs/部署/部署指南.md`——三档对比（对照计划书 §6）、本地局域网（host 0.0.0.0 + 防火墙/ipconfig）、SakuraFrp、Cloudflare Tunnel（`cloudflared tunnel --url http://localhost:18000`）、云服务器（systemd/Docker + 反代）、邀请链接外网化说明、**排错 FAQ 表**（SSE 断连/防火墙/隧道/反代 404/Docker 卷权限等）。
- **M6.5 安全清单**：`server/ratelimit.py` 每 IP 滑动窗口限流中间件（config `rate_limit` 可配，仅 /api，超限 429，测试覆盖）；uvicorn 改 `log_level="warning"` 关闭访问日志（不落 IP 明细）；`docs/部署/安全清单.md` 逐项核对（secrets 权限/data 不公开/限流/日志脱敏/dev_token 默认关闭 + Linux 600 建议）。
- 测试：`server/tests/test_m6.py` 6 项（限流单元 per_minute/burst、中间件 429、测试间重置、安全默认值、secrets 往返/损坏回退）；全套 **76 项绿**；前端构建通过；start-web.ps1 语法解析通过（无 BOM 会被老版本 PS 误按 GBK 读，已加 BOM）。
- 验收：异地 HTTPS+密码加入的**部署环境实测**需公网/浏览器，本环境无法执行——凭据流程已由 M5 测试覆盖，HTTPS 由反代文档保证；部署文档覆盖三档 + 排错。
- 已知项：Dockerfile 未在本环境实际构建（无 docker）；多实例部署时限流为内存实现，需换 Redis。

### M4 修复与人工测试（2026-08-31）

- **fix**（`aa62950`）：顶栏「游玩」导航写死 `/play/demo` 导致与当前房间凭证错配、页面卡"加载中"——改为跳转当前游戏；Play 页凭证错配自动跳回；房间不存在显示明确错误页。
- **fix**（`ceaab9b`）：理智检定卡片被误当自由掷骰渲染（表达式/结果空白）——新增 `san_check` 专用样式（理智检定/当前理智/掷骰/未损失或损失N点/实时疯狂提示）；pipeline 判定消息存档完整结果，刷新后理智卡片仍可正确渲染。
- **docs**（`4692212`）：MILESTONES 新增「待办 · 后续优化」——TODO-A 自然语言技能推断（用户需求，暂缓开发）、TODO-B M4 遗留小项。
- **人工测试通过**：用户浏览器实测创建→建卡→行动→自动推进→检定→叙事→失败措辞→刷新重连→非法输入→附件图片，全部符合预期；M4 验收正式闭环。

---

## [M7 后续增强 · LLM 输出上限与隐私铁律] - 2026-09-01 ✅

配置真实 LLM（OpenCode Go / MiMo-V2.5）后实测发现：推理模型先输出 `reasoning_content` 再输出 `content`，长叙事易被 `max_tokens=2000` 截断。本次拓充上限并新增「截断 → 请求房主调高」闭环，同时立下 **reasoning_content 隐私铁律**。**91 项 pytest 全绿** + 前端构建通过。

- **max_tokens 拓充（可配 + 每局可覆盖）**：`data/config.json` `model.max_tokens` 默认 **4000**（原 2000）；`games` 表新增 `max_tokens` 列（`_migrate` 自动 ALTER，NULL=用 config 默认）；`LLMClient.from_config(max_tokens=...)` 支持每局覆盖。
- **截断检测**：`llm.chat_detailed()` 返回 `LLMResult(content/truncated/finish_reason)`——`finish_reason=length` 标记截断；`chat()` 保持返回最终输出文本（向后兼容）。
- **截断 → 请求房主调高**：管线聚合 `truncated` 标志 → 落一条 `system` 消息（叙事流可见，刷新可恢复）+ SSE `llm_limit_hit` 事件（round/stage/当前上限/建议值）→ 房主面板黄色横幅「一键调高到 N」；新端点 `POST /api/games/{key}/llm-limit`（房主，1000–32000，越界 400，非房主 401）→ 广播 `llm_limit_changed` 同步所有在线玩家；公共视图暴露 `max_tokens`。
- **reasoning_content 隐私铁律（用户明确要求）**：LLM 客户端**只读取 `message.content`（最终输出）**，`reasoning_content`（思考过程）一律不读、不返回、不落库、不广播——content 为 None 时返回 None，绝不降级用思考内容；测试断言思考内容不出现在任何返回值/消息/事件中。
- 前端：GmPanel 新增「AI 输出上限」输入 + 保存 + 截断横幅一键调高；NarrationStream 渲染 `system` 消息（warning 样式）；game store 处理 `llm_limit_hit`/`llm_limit_changed`（按签名与服务端持久化消息去重）。
- 测试：`server/tests/test_llm_limit.py` 7 项（截断检测、reasoning 不泄露、正常完成、config 优先级、管线透传、调限端点鉴权/越界、system 消息落库）；全套 **91 项绿**。
- 部署文档：`docs/部署/部署指南.md` 新增 §3.3 localtunnel（免安装免注册临时测试）+ §3.4 隧道地址易变对照表 + FAQ 确认页条目。
