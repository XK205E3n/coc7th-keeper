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

M7 四子项按用户细则定案（7.1 世界书不开发、7.2 记忆仅 API 可选、7.3 不做 WebRTC、7.4 不开发 DND5e——详见 `MILESTONES.md`），并完成三条额外任务。**84 项 pytest 全绿**（注：当时文档误记 88，实际收集 84）+ 前端构建通过 + headless 截图视觉验证。

- **局内聊天（新增）**：`POST /api/games/{key}/chat`（`{text, expr?}`）——纯文本或联掷（`expr` 时骰果入 `dice_log` 审计并随消息广播）；SSE 新增 `chat` 事件；消息落 `messages`（kind=chat，刷新恢复）；前端 `ChatPanel`（与自由掷骰整合：输入框 + 发送/掷骰按钮，骰子带 🎲 结果行）；game store 拆分独立 `chats` 流（不进叙事流）。
- **视觉 UI 优化（暗色主题）**：App.vue 包 `n-config-provider` + naive-ui `darkTheme` + 定制 `themeOverrides`（暗紫主色 `#a78bfa`、深底 `#121016`/卡片 `#1a1720`、高对比文字）；全局 `style.css` 暗色调；暗色顶栏/页脚；游玩页常驻信息区块——**场景栏 SceneBar**（场景名/地点/摘要/回合/阶段）、**角色信息栏 CharacterBar**（我的 HP/SAN/MP/MOV/DB + 线索/物品数，状态变动后自动刷新）、玩家列表、私密感知、行动、聊天。经 Edge headless + modlens 视觉分析验证渲染与对比。
- **线索台账（用户建议更新）**：`modules.list_clues` 解析模组 `clues.md` → 建团时初始化每局台账副本（store `clue_ledger` 表：id/文案/locked-unlocked/获得时间与者）；获得线索经 `state_apply` 解锁；**管理员**经 `/api/dev/games/{key}/clues`（total/unlocked/locked）查询；**KP**：管线裁判+叙事阶段自动注入台账文本（`[C-01] [已获得] 文案…`，AI 易读格式，绝不进玩家视图）——顺带修复 M2 遗留：narrate 阶段此前未注入 KP 上下文。
- **修复（生产 bug）**：前端静态托管下 SPA 深链 `/play/xxx` 直接访问 404——`main.py` 加非 `/api` 404 → `index.html` 兜底（M6.3 完善）。
- 测试：`test_m7.py` 7 项（聊天文本/联掷审计/SSE 广播、台账初始化/解锁/幂等、dev 查询、KP 注入）+ 限流器测试间隔离修复（conftest 每测试换全新默认限流器）；全套 **84 项绿**（实际收集数）。
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

---

## [M8 · 视觉与可用性微调] - 2026-08-31

针对独立审阅报告与视觉审阅报告指出的"代码写完 ≠ 能用"问题，逐项落地中。本节先记已完成的小项。

- **fix · 骰卡纯白底改深蓝**（E3n 指定 B 档 · 任务书 T-B4）：`frontend/src/components/DiceCard.vue`
  - 背景 `var(--card-color, #fff)` → `var(--dice-bg, #17233c)`（深蓝，对比度 12.5:1）
  - 边框 `var(--border)` 灰紫 → `var(--dice-border, #35507f)` 蓝调
  - 标签文字 `var(--text-3)` 紫灰 → `var(--dice-label, #93a9cc)` 蓝调
  - 成功/失败色硬编码 `#18a058` / `#d03050`（Naive UI 亮色主题）→ `var(--success-color, #4ade80)` / `var(--error-color, #f87171)`（style.css 暗色 token）
  - 根因：`--card-color` 全仓从未定义，兜底 `#fff` 必然生效——补两个新 token `--dice-bg` `--dice-border` `--dice-label`，未来同类卡可复用
  - 验收：`.tmp/shots/09-dice-darkblue.png` 同机位截图确认（种子房间 `3e981bc6` / host_token `a2a45cbc44fa7b9c879b573532be2b93`）；桌面端三类骰卡（技能成功/失败、理智、自由掷骰）都覆盖
  - 影响面：DiceCard 样式 scoped，只在 `NarrationStream.vue:72` 引用，无外溢
  - **未变更**：前端构建、pytest、其他前端文件
- 文档：`docs/review/视觉审阅报告-2026-08-31.md` P1 第 6 条标 ✅ + 修复优先级第 0 条标 ✅；`docs/planning/下一步工作任务书-2026-08-31.md` T-B4 标 ✅、DoD 项勾掉、附录 C 划掉原条目（注：两文件 2026-09-01 起迁至 `docs/review/` `docs/planning/`，见下「M8 补记五」）

### M8 · 任务书阶段 A–C（2026-09-01 ✅ 完成，DeepSeek v4 Flash + modlens 执行）

按 `docs/planning/下一步工作任务书-2026-08-31.md` 完成响应式 / 导航 / 空状态 / 鉴权 / 信息架构全部必做任务，每个任务经 Edge headless 三断点截图 + modlens 视觉验收（≥4/5），**91 项 pytest 全绿 + `npm run build`（含 vue-tsc）通过 + 新依赖 0**。

- **T-A1 全局断点骨架**：`frontend/src/style.css` 建立三档响应式约定（mobile ≤640 / tablet 641–1024 / desktop ≥1025，注释统一）；`App.vue` 顶栏移动端换行不溢出、主区边距收紧
- **T-A2 Play 页响应式重排**：`Play.vue` 移动端改单列（叙事优先），新增「收起/展开信息面板」按钮（`sideOpen` ref，仅 ≤640 生效，折叠侧栏）；平板 641–1024 右栏收紧 330→280px——修复移动端叙事被压缩至 ~44px 窄条（任务书 B.2 P0）
- **T-A3 四视图响应式**：`Overview.vue`（grid `minmax(min(300px,100%),1fr)` 防 320px 溢出、recent-row 窄屏换行）、`Characters.vue`（pregen 列窄屏纵向、属性网格窄屏 3 列）、`Content.vue`（module-meta 窄屏换行、长 id 防溢出）、`Admin.vue`（窄屏表单/按钮单列铺满）；其中 Overview/Characters/Content 由 3 个子代理并行完成
- **T-B1 顶栏 active 联动**：`router.ts` 每条路由加 `meta.activeMenu` + `App.vue` 新增 `isActive()` 精确匹配（游玩项拆分 `activeKey`，无游戏时跳 `/` 不高亮）——修复「总览/游玩」双高亮（任务书 B.1 P0，Vue Router 祖先匹配）；CDP eval 验证 5 页各恰好 1 个高亮
- **T-B2 空状态组件统一**：新建 `frontend/src/components/EmptyState.vue`（图标+文案+引导动作三件套；按钮在 `n-empty` 外渲染，规避 `#action` 插槽未渲染问题），替换 Overview（最近游戏→滚动聚焦创建卡）/Characters（无预制→切 AI 草稿）/Content（无模组→重新加载）/Admin（无房间→重新查询）/CharacterBar（未建卡→去建卡）5 处空态
- **T-B3 Admin 未鉴权态**：`Admin.vue` 未填 dev_token 时 9 个查询按钮（列出房间/房间概览/7 资源）全部 disabled + 黄色提示「请先填写上方开发者凭证，查询按钮方可使用」（eval：9/9 disabled）
- **T-C1 技能搜索 + 分组**：`CharacterSheet.vue` 技能表改为搜索框（中文输入经 `CN_TO_EN` 映射匹配英文技能名，如「急救」→ First Aid）+ 四组折叠（战斗/社交/学术/其他，组头带计数）。期间修复两个真 bug：①中文搜不到英文技能名（补映射表）；②naive-ui `n-collapse` 动态 `v-for` 列表内容区在数据变化时不更新（缓存旧 DOM）——改为固定 4 个折叠项 + 组内数据走 `groupItems(name)` 实时函数，验证「急救」过滤后全表仅 First Aid 一行、无匹配显示「未找到匹配技能」
- **修复（后端 bug，E3n 授权突破任务书红线）· auto 建卡 SAN 双乘**：`server/engine/build.py` `san = pow_ * 5` → `san = pow_`（POW 已是百分制 15–90，再乘 5 得 400+；CoC7th SAN 初始 = POW 百分制值）；同步修正 docstring 与 `server/tests/test_engine.py` 编码错误惯例的断言。实测新角色 SAN = POW（50/65/75/80），游戏内理智检定恢复正常（此前 d100 恒成功、SAN 永不损失）。**遗留**：`modules/` 下 3 个预置角色卡与 1 处文档仍标 SAN 300/325（同错误惯例），需另行授权修正
- **阶段 D 双人复核（headless 自动化）**：`.tmp/dual-check.mjs` 新建受控房间（the-haunting）→ 房主（桌面 1440）+ 邀请玩家（移动 390）双浏览器 → 双建卡 → 聊天（文本+联掷）→ 双提交自动推进 4 轮真实 LLM 叙事 → 每轮双视角截图并存于 `.tmp/shots/D3-r*.png`。验收：①叙事流每轮递增（round-card 1→4）②`chatInNarration` 恒 0（聊天消息从未插入叙事流，DOM 硬验证）③移动端单列可用 ④SAN 数值正常。发现并回避：`advance` 端点仅回合 +1 不生成叙事（自动推进才会跑 LLM 管线）；旧测试房间因旧玩家从不提交阻塞自动推进（改用新建房间）
- **T-C3 阅读模式（可选任务，已完成）**：`NarrationStream.vue` 点击叙事/场景/系统文本打开全屏阅读模态（Teleport + 半透明遮罩覆盖右栏与页面其余内容，字体 1.2x=16.8px、可滚动，Esc/按钮/点遮罩关闭）——验证：opened/closed 断言 + 视觉截图 `.tmp/shots/reader-open.png`
- 验收截图：`.tmp/shots/` 02 桌面 / 06 移动 / 07 平板 / 08 移动折叠 / 09–12 各 view 移动端 / 13、15 技能搜索分组 / D3-r1..4 双人复核 / reader-open 阅读模式
- **未完成（需外部环境）**：Docker 构建验证、异地 HTTPS 部署实测（README/MILESTONES 保留）
- **待用户确认**：pregens SAN 修正授权（modules/ 变更）；测试房间 `3e981bc6` 内积累的「复检xxxx」测试玩家清理

### M8 补记 · 角色卡模板与编辑说明（2026-09-01 ✅ 完成）

与 `docs/模组拆解说明.md` 同规格的**角色卡规范文档**，解决「玩家用 AI 生成角色卡后如何直接上传」的标准姿势。

- **新增 `templates/character-sheet-template.json`**：可直接上传的完整角色卡模板（`coc7-character/v1` 全字段：schema/name/cn/meta/attributes 9 项/derived 5 项/46 项默认技能/inventory/notes/sanity/state）；属性 50 基准（EDU 60），派生值按引擎公式自洽（HP 10 / MP 10 / SAN 50 / DB "0" / MOV 8）
- **新增 `docs/角色卡模板与编辑说明.md`**：§1 设计目标 → §2 JSON 总览与字段速查表 → §3 模板用法 → §4 属性/派生公式（含 **SAN = POW 强调，禁止 POW×5** 历史教训）→ §5 引擎口径 → §6 完整技能表（四组分类）→ §7 上传方式（前端/API curl）→ **§8 AI 生成提示词模板**（玩家提要求的标准姿势，含 3 方案输出要求）→ §9 上传前自检清单 + 常见错误表 → 附录（与 auto 生成一致性）
- **实测验证「可直接上传写入」**：`.tmp/verify-template.py` 新建临时房间 → 直传模板 JSON → HTTP 200，schema/属性/派生/SAN 50/state(10/50)/46 技能全部正确落库 + GET 复核通过；验证房 db 已清理
- 备注：建卡 API 仍为「直传零校验」（M9 候选 B1）——文档 §1/§9 已明确要求严格按字段约束

### M8 补记二 · pregens SAN 修正 + 粘贴上传入口 + 测试数据清理（2026-09-01 ✅ 完成）

三件事一并落地（E3n 授权），随字符卡模板文档配套收尾：

- **fix · 预置角色卡 SAN 回归（modules/）**：引擎 SAN 修复后遗留的 3 张预制卡仍标 SAN 300/325（旧 `POW×5` 惯例）——已修正为 `SAN = POW`：`the-haunting/pregens/theron-quist.json`（POW 65 → SAN 65）、`delphine-mcquire.json`（POW 60 → SAN 60，顺带 `DB "+0"` 规范化 `"0"`）、`toy-dancer-comes/pregens/relay.json`（POW 65 → SAN 65，备注措辞更新）；`toy-dancer-comes/README.md` §5.3 总上限描述同步（325 → 65，余裕叙述改写）。pytest 91 项全绿复测
- **feat · 角色页「粘贴 JSON」上传入口（frontend/src/views/Characters.vue）**：建卡三步新增第 4 个标签页——textarea 粘贴完整 `coc7-character/v1` JSON + 角色名输入 + 「校验并上传」；前端轻量自检（JSON 可解析 / schema 匹配 / 角色名非空），`derived.SAN ≠ attributes.POW`（勿乘 5）给出黄色提示不拦截；上传成功回跳「预制角色」tab 并显示「角色卡已就绪」。E2E 实测（headless + CDP）：点 tab → 填 JSON（贴纸角色，SAN=POW=70）→ 上传 → 角色卡就绪显示 ✓；`npm run build`（vue-tsc）通过
- **chore · 测试数据清理**：房间 `3e981bc6`——踢除 7 个历史测试玩家（审/审B/复检71068/复检56411/复检A75928/复检B75928/复检45913，kick API 200），清空 characters 表 5 张旧测试角色卡（A侦探 SAN 450 等残留，此前会污染新玩家的「已就绪」判定，暴露 `myCharacter` 回退 `characters[0]` 的展示问题）；保留房主艾伦/玛拉/调查员。附带：`.gitignore` 补 `.workbuddy/`
- 文档：`docs/角色卡模板与编辑说明.md` §7.1 更新为「UI 已支持粘贴上传」

### M8 补记三 · 模组拆解说明对齐程序核对修订（2026-09-01 ✅ 完成）

对照 `server/modules.py` / `gm/pipeline.py` / `api/games.py` 逐条审计 `docs/模组拆解说明.md`，修正 5 处「文档 ≠ 程序」偏差并升版 v1.1：

- **§3.4 clues.md 格式修正**：早期示例（`## C01 · 标题` + 字段列表）**不会被程序解析**——改为程序真实解析格式 `- [ ] **C-XX** 线索正文…`（`list_clues` 正则），并补条目边界规则（正文延续到下一 `- [ ] **C-` 或 `#` 标题行）
- **fix · `list_clues` 正文吞并 `##` 小节标题**（server/modules.py）：正则 lookahead 增加 `^#{1,6}\s` 边界——此前 the-haunting/toy-dancer 的 `## 小节` 标题会被并入上一条线索正文（台账/ KP 注入文本含「## 一楼」噪声）；修正后 16/27 条正文全干净。条数、id、台账测试（test_m7）不受影响，pytest 91 项全绿
- **§3.2/§3.5 标注非消费文件**：`plot.md`、`npcs.json`、`monsters.json` **程序当前不读取/不注入**（早期文档称其参与 AI 读取模式，不实）——注明真实 AI 信息来源为「场景对象整体注入 + kp_notes 表 + 线索台账」
- **§4 AI 读取模式表重写**：开局注入实为「首场景 scene 消息 + kp-notes.md 全文 → kp_notes 表 + clues.md → 线索台账」（不含 meta/plot）；场景注入为场景对象整体（`json.dumps`）；新增「运行时 KP 上下文」（kp_notes 表尾 + `_format_clue_ledger` 台账文本）与「不注入」行列
- **§3.6/§6 契约补全**：场景按 `scene_flow` 排序 + 首场景开场；场景必须含 `id`（`name` 可选，用于切换按名查找）；场景 `checks/clues/npcs/handouts/next` 字段语义；§6 校验清单同步（clues 格式、场景 id、非消费文件备注、`validate_module` 对应说明）
- 杂项：§2 目录注释「见 §4.7」→「见 §3.7」（编号残留）
- 验证：`validate_module` 两模组 OK；`list_clues` 16/27 条、正文 0 含标题；pytest 91 全绿

### M8 补记四 · 顶栏双高亮修复 + 操作指引 + 模组源文件不入库（2026-09-01 ✅ 完成）

独立复核发现 M8 阶段 A-C 遗留的 P1 双高亮 bug，本轮修复 + 补交付物。

- **fix · 顶栏双高亮**：`App.vue:129-134` 删掉 `.app-nav-link.router-link-active` 选择器（Vue Router 4 默认祖先匹配 → 两条同 `to` 链都被加 `router-link-active` → CSS 把两者都涂成高亮色），只保留 `.is-active` 精确匹配。CDP eval 验证 5 页（`/`、`/play/:key`、`/characters`、`/content`、`/admin`）各恰好 1 个 `.is-active=true`，视觉上仅 1 项高亮。`router-link-active` 类仍由 vue-router 自动加（不影响功能，仅 CSS 不再消费）
- **docs · 操作指引**：`docs/操作指引.md` 新增（~340 行），端到端操作手册：5 分钟上手 / 部署三档 / 公网联机四方案 / LLM 配置（4 兼容 OpenAI 协议服务）/ 游玩指导（房主/玩家/检定/角色卡）/ 故障排查 7 类 / 进阶（开发者监视/自定义模组/API/性能基线）。面向「拿到代码想跑起来玩」的人
- **chore · 模组源文件不入库**：`模组源文件/`（两个 PDF 约 7MB：coc7e 鱼人与派、不要叫醒沉睡的猫）加入 `.gitignore` —— 拆解后的 JSON 形式已在 `modules/`，原文不必要也不应入库
- **chore · 验证**：独立复跑 `pytest -q`（91 项全绿）、`npm run build`（通过，含 vue-tsc）、CDP 截图 5 页顶栏 active 状态（`.tmp/shots/V1-V5`）

### M8 补记五 · 模组拆解说明 standalone 化（2026-09-01 ✅ 完成）

应 E3n 要求重构 `docs/模组拆解说明.md`：该文档成为**拆解任务的唯一自包含参考**（不指向任何下级参考，外部工作者仅凭本文档即可完成拆解）。

- **删除全部 archive 引用**：头部「参考 archive/…」行、`meta.json` 示例 `source.notes` 中的 archive 路径、§6 校验清单「放 archive/模组/」字样、原 §7「示例参考」单元均移除——archive 目录不随项目发布，不再作为参考
- **§7 改为「已发布样例」**：指向 `modules/` 下已上线模组（`the-haunting` / `toy-dancer-comes`），并注明场景数/线索数/预制角色，供对照拆解
- **§3.2/§3.3 补 standalone 结构细则**：`plot.md`（背景/开场/场景清单/场景详情/结局 + 模板框架）、`kp-notes.md`（真相/NPC 隐藏面/未揭示线索/失败预案/数值参考 + 模板框架）——此前仅「沿用 toy-dancer-comes 写法」，现写入完整可照做的格式
- **§3.1/§3.6 补字段表**：meta.json 与 scenes.json 增加必填/可选字段速查表（程序校验字段与推荐字段明确标注）
- **标题精简**：`## 4. AI 读取模式`（去掉「三种注入 · v1.1 对照实测修订」形容）、`## 8. 世界书（预留）`（去掉决策说明行）——结构标题不加多余形容
- 程序行为说明保留在文档体（§4 注入表 / §3.4-3.6 程序现状），不写入"建议参考"类文本
- 验证：grep 确认全文无 `archive` / `coc7th-keeper-feishu` / `v1 拆解` 残留；文档结构自包含

### M8 补记六 · 模组拆解说明 standalone 复核补全（2026-09-01 ✅ 完成）

E3n 复核补记五后仍不满足 standalone 要求，本轮补齐 4 处遗留：

- **§3.8 新增 `pregens/` 预制角色格式规范**（此前最大缺口）：`coc7-character/v1` 完整示例 + 必填/可选字段表 + 派生公式（HP/MP/SAN=POW 勿乘5/DB 查表/MOV 修正）+ 技能英文键要求——外部工作者不再需要读角色卡文档即可拆预制角色
- **§5 第 5 条去掉外部文档指向**：「按角色卡规范（见 docs/角色卡模板与编辑说明.md）」→「按 §3.8 角色卡格式」（全文不再指向任何外部文档）
- **头部删元声明行**：「本文档是拆解任务的唯一参考：…见 §3/§4/§5/§6」整行移除（自我声明类文本不入正文），版本行精简
- **§3.5 建议语气改中性规定**：「本文件仍建议拆出…供未来与世界书共用」→「拆解时应提供本文件，内容与场景条目、kp-notes 保持一致；影响 AI 判定的关键信息以场景条目与 kp-notes 为准」
- **§6 校验清单补 pregens 项**：schema/attributes/derived/skills 齐全 + 派生自洽（SAN == POW）
- **标题继续精简**：「拆解步骤（源材料 → 模组包）」「scenes.json（场景结构化）」「世界书（预留）」「目录与格式（草案）」「阅读逻辑（草案）」均去括号形容
- 验证：grep 无 `archive` / `建议` / `见 docs` / `（预留` / `（草案` 残留；§3.1–3.8 结构完整

### M8 补记七 · docs 目录分层：内部工作档案隔离（2026-09-01 ✅ 完成）

E3n 要求：`docs/` 根目录只保留**给玩家阅读**或**给外部 AI 参考**的文档，AI 内部工作产物（审阅 / 任务书 / 完成报告 / 复检素材）不得混放。本轮完成归档分层。

- **新增 `docs/AI工作记录/`**（单一归档目录，扁平存放 + `README.md` 索引）
  - 迁出 `docs/` 根目录 6 项：`独立审阅报告-2026-08-31.md`、`视觉审阅报告-2026-08-31.md`、`视觉复检-双人-2026-09-01/`（8 张 PNG）、`下一步工作任务书-2026-08-31.md`、`下一步工作-任务书-2026-09-01.md`、`对话记录-跑团Web平台规划.md`
  - 索引文档 `docs/AI工作记录/README.md` 说明目录定位（非玩家文档）、6 项产物清单与交接约定（交任务书时须同附相关审阅报告 + CHANGELOG + 操作指引）
- **根目录保留**（玩家 / 外部 AI 参考）：`操作指引.md`、`模组拆解说明.md`、`角色卡模板与编辑说明.md`、`CoC7th规则依据与来源.md`、`跑团Web平台计划书.md`、`跑团Web平台-实施方案.md`、`部署/`（部署指南 / HTTPS 反代 / 安全清单）
- **相对路径修正**：两份任务书原以 `docs/xxx.md` 引用同级文档，改为同目录裸文件名；指向根目录文档的统一为 `../xxx.md`；仓库根 `README.md` 统一为 `../../README.md`。修正 1 处错误链接（`../README.md` 实际指向 `docs/README.md`，不存在）与 5 处漏加 `../` 的链接目标
- **CHANGELOG 历史条目同步**：M8 阶段 A–C 与骰卡改色两条记录中的任务书 / 视觉审阅报告路径更新为新位置
- **README 同步**：文档表新增「AI 工作记录（内部）」行 + CoC7th 规则依据行；目录结构树补 `docs/AI工作记录/` 并标注 `docs/` 根定位（玩家 / 外部 AI 参考）
- 验证：全仓 grep 无残留旧路径；`docs/AI工作记录/` 内 5 份 md 的站内相对链接逐一核对可解析；无代码改动（不触发 pytest / build）

### M8 补记八 · archive 旧项目归档目录整体删除（2026-09-01 ✅ 完成）

E3n 要求：确认核心资产已全部迁移或抛弃后，彻底删除 `archive/`。删除前完成**迁移审计 + 运行完整性实测**，两项均通过才动手。

- **迁移审计（逐文件比对，非估算）**
  - A 类 · 已 100% 迁移且现行版更优：11 张 handouts 图（**md5 逐一相同**，仅嵌套目录拉平）、the-haunting 4 份文本、toy-dancer 4 份文本（`diff` 完全相同）、3 张 pregens + toy-dancer README（差异仅现行含 M8 SAN 修正）、6 个引擎脚本（现行含 `SAN=POW` 修复）
  - B 类 · 飞书平台专属，Web 版无对应：`.dsh/bin/` 17 个、`tools/*.ps1` 4 个、6 个飞书 CLI 脚本、`references/help-cache.*` / `modules-cache.*`、旧项目 README/CHANGELOG/LICENSE/VERSION、`.dsh/backup/`（空目录）
  - `SKILL.md`（44KB 原始 skill）：与现行守密人文本（`prompts/gm_system.md` + `server/gm/*`）**仅 3% 行重合**，CoC 规则部分已全量迁进 `server/engine/` 与 `docs/CoC7th规则依据与来源.md`；剩余 97% 为飞书消息路由逻辑，无保留价值
- **运行完整性实测**（证明删掉素材源后模组仍能完整跑）：`validate_module` 双模组 0 错误；场景流 the-haunting 7/7、toy-dancer 10/10，`scene_flow` = 场景全集且所有 `next` 跳转可达；11 个 handouts **逐个 HTTP 200 可取**（1.63MB）；线索解析 the-haunting 16 条 / toy-dancer 27 条、`##` 噪声 0；预置卡建卡 **SAN=65 == POW=65**、33 项技能；新建 toy-dancer 房间真实 AI 推进 4 轮（12–15s/轮），产出 1 场景 + 4 叙事 + 4 骰卡
- **执行**：`git rm -r archive/` 移除 87 个已跟踪文件，`rm -rf` 清除未跟踪残余（含 `__pycache__` 13 个 pyc）；删除前完整备份到 `.tmp/archive-backup-20260901.tar.gz`（4.87MB，含未入库的 PDF 与转写稿，不在 git 内）
- **原版 PDF 保留在本地**：`archive/…/Yukishiro-玩具跳着舞蹈来.pdf`（3.1MB 版权材料）移出到 `模组源文件/`（已被 `.gitignore` 忽略，不入库），另外两份日语模组 PDF 同目录，共 3 份
- **引用清理 5 处**：`README.md` 文档表行与目录树、`docs/CoC7th规则依据与来源.md` 来源表与派生公式、`server/engine/__init__.py` 模块 docstring、`modules/toy-dancer-comes/meta.json` 的 `source.notes`
- **顺带修正规则文档错误**：`docs/CoC7th规则依据与来源.md` 第 19 行仍写 `SAN=POW×5`，与 M8 已修的引擎口径 `SAN=POW` 冲突 → 改为 `SAN=POW`
- 验证：全仓 grep（排除 `.git`/`node_modules`/`.venv`/`.workbuddy`/`.tmp`）源码与文档无 `archive` / `coc7th-keeper-feishu` 残留；仅 CHANGELOG / MILESTONES / 规划对话记录中的**历史陈述**保留原文（CHANGELOG 是历史事实源，不改写既有条目）

### M8 闭环清单

- ✅ 顶栏双高亮 bug 修掉
- ✅ archive 旧项目归档目录删除（迁移审计 + 运行实测双通过）
- ✅ pregens SAN 修正（pow×5 → =POW）
- ✅ 测试房间 3e981bc6 测试玩家清理（7 个）
- ⏳ 真实浏览器多人复核（headless 双人版已过，建议用户真人一次）
- ⏳ Docker 构建验证（开发环境无 docker，需用户本地执行）
- ⏳ 公网部署异地 HTTPS 实战（文档齐，需用户执行）

### M8 补记九 · 三模组专名核对与修正 + 2 个新模组入库（2026-09-01 ✅ 完成）

E3n 要求对照三份原版 PDF（`模组源文件/` 下的 3 份版权材料，本地存档，`.gitignore` 忽略）核对姓名/地名。完成双向比对（PDF 文本层 + handout 截图 + 罗马音自创项回溯）。

**A. 实质性错误修正 3 处**

| # | 文件 | 错误 → 正确 | 依据 |
|---|---|---|---|
| 1 | `modules/sleeping-cat/npcs.json` | `nanami_kirito` → `nanami_kiriko`（七海桐子 = Nanami Kiriko，**不是** Kirito/「桐人」） | 七海=ななみ / 桐子=きりこ |
| 2 | `modules/sleeping-cat/npcs.json` | `kamakura_saeba` → `kamakura_sawa`（镰仓佐羽 = Kamakura Sawa，**不是** Saeba/「冴羽」） | 镰仓=かまくら / 佐羽=さわ |
| 3 | `modules/toy-dancer-comes/handouts/maps/qiulin-park-map.jpeg` → `qiulin-court-map.jpeg` | 原文是「**秋林苑**」（别墅园区），不是公园（park） | PDF 全文 10 次「秋林苑」、0 次「秋林公园」 |

- 同步：`modules/sleeping-cat/scenes.json` 5 处 NPC id 引用；`server/tests/test_api.py:142` 硬编码路径；`docs/模组拆解说明.md` 2 处示例
- 同步 4 处引用：`modules/toy-dancer-comes/{scenes.json,plot.md,README.md}` 全部改为 `qiulin-court-map.jpeg`

**B. 预置卡文件名对齐**

- `modules/sleeping-cat/pregens/teen-nanami.json` → `teen-shizuku.json`（角色名是 Shizuku；且「七海」是 NPC 七味桐桐的本名姓，预置卡不应撞姓造成混淆）
- 命名一致性：adult-misaki/Misaki、teen-haru/Haru、teen-shizuku/Shizuku ✓

**C. 2 个新模组入库**（下游 AI 已拆好的未提交产物）

- `modules/yuren-pie/`（鱼人与派，原 PDF `coc7e迷你模組-魚人與派.pdf`，作者 CH2050，4 页短篇）：4 场景 / 4 handouts / 12 线索 / 3 预置卡（Foreign Student / Nerd / Old Money，对应原文 p.4 跑团实例「書呆子、外國留學生、有錢的老男人」）✓
- `modules/sleeping-cat/`（不要叫醒沉睡的猫，原 PDF `眠り猫おこすべからず.pdf`，作者内山靖二郎 / 译者洛萨_Lotharthunder，17 页）：8 场景 / 6 handouts / 26 线索 / 3 预置卡（Misaki/Haru/Shizuku 自创，原文未给预置卡）✓
- 4 模组全量校验：`validate_module` 0 错误、scene_flow 全部覆盖、next 跳转全可达、handouts 0 缺失、`##` 噪声 0、SAN == POW 全部正确

**D. 已确认正确（核对过程留档）**

- toy-dancer-comes：沈珂成、沈青鸣、谢尔顿·夏普、亨利·卡塔、托尼、安迪、玩具修理者、松德克、威尔逊、三津田信三、小林泰三、赫伯特·韦斯特 — 全部对齐原文（含两张手写图：house-of-tragedies.jpeg 1907 松德克、shen-investigation.jpeg 1928 威尔逊/1991 武藏名护池）
- sleeping-cat：七味桐桐、七海桐子、镰仓佐羽、沉眠之猫、Shiro、结缘之钟、Siesta、静眠山、阿特拉克·纳克亚 — 全部对齐原文 + 6 张 handout 截图逐一确认
- yuren-pie：作者 CH2050、深潜者属性（STR70/CON50/SIZ80/DEX50/INT65/POW50/HP13/DB 1D4/格斗 45%/闪避 25%/护甲 1/理智 0/1D6）— 全部对齐

**E. 已知存疑（保留并标注，不擅改）**

- `modules/toy-dancer-comes/kp-notes.md:19/31/187`：「武藏名护池」三字来自 PDF 手写展板图（`shen-investigation.jpeg`），作为虚构地名无明显日本地理参照。原文已自标"手写辨认可能存在误差"待办。**未改**

**F. 验证**

- `pytest -q --basetemp=.tmp/pytest` → 91 项全绿（exit 0）
- 4 模组 `validate_module` + 场景流 + handouts + 线索 + 预置卡 全维度校验通过
- 全仓 grep `qiulin-park` 仅在 `.git/worktrees/` 与 `.tmp/edge-profile/` 缓存中（构建产物，不入库）
- 全仓 44 条 Markdown 相对链接 0 断链

### M8 补记十 · P2 体验瑕疵修复（T-A1~T-A5，2026-09-01 ✅ 完成）

承接任务书 `docs/AI工作记录/下一步工作-任务书-2026-09-01.md`，对前端做 P2 体验瑕疵修复。**仅改动 `frontend/src/**`，后端/引擎/数据库/依赖/部署一律未动。**（DoD 所述「M8 补记四」为陈旧引用，补记四已用于 P1 顶栏修复，故本条目记为补记十。）

**T-A1 `CharacterSheet.vue` 技能搜索覆盖度补全**
- `CN_TO_EN` 5 个失效 key 改映射到真实存在的技能名：化学/物理/生物 → `science`（合并在 Science 技能下）、藏匿 → `stealth`、计算机 → `elec repair`。
  - 偏离任务书原案：原书写「计算机 → computer use」，但模板 46 技能中**无** Computer Use（仅有 Elec Repair），故落到最接近的 Elec Repair 以保证静态校验 100% 命中；独立 Computer Use 技能属模板/后端范畴，不在本任务范围。
- 补口语词：开锁 → `locksmith`、心理学 → `psychology`（原仅有「心理」）。
- 学术分组 keywords 补 `science`，使 Science 归入学术组。
- 验收：`.tmp/verify_search2.py` → 57 个中文 key，**0 个搜不到**（原 5 个 MISS）。

**T-A2 `Characters.vue:70` 粘贴 JSON schema 校验文案 bug**
- `String(char.schema) ?? '（缺失）'` → `char.schema ?? '(缺失)'`：`String(undefined)` 返回字面量 `"undefined"` 导致 `??` 永不触发；修复后无 schema 时显示「当前：(缺失)」。

**T-A3 `EmptyState.vue` 改用 `#extra` 插槽**
- 按钮从 `<n-empty>` 外的 `.empty-action` hack div 移入 n-empty 真实 `#extra` 插槽；删除无用 `title` prop。外部 API（actionLabel/to/@action）不变，5 个使用点无需改动。
- **五个空状态全部实跑验证**（含补记阶段补拍）：Admin（1440）/ CharacterBar「尚未建卡」（1440+390 隔离浏览器）/ Overview「最近游戏」（1440+390 隔离浏览器）/ Characters「无预制」/ Content「无模组」。DOM 断言一致：`btnInsideNEmpty:true`、`emptyActionHackExists:false`。

**T-A4 `NarrationStream.vue` 阅读模态无障碍**
- 打开锁 `document.body.style.overflow='hidden'`（移动端背景不再滚动），关闭/`onUnmounted` 解锁；面板加 `aria-modal="true"`；打开后 `nextTick` 焦点移到关闭按钮，关闭后还原 `prevFocus`。

**T-A5 四 view 微观一致性（含一项环境限制）**
- T-A5.1 `CharacterSheet.vue`：「其他」分组默认折叠（多数空）。
- T-A5.2 `Play.vue:161` `watch(gameKey)` 切房时重置 `sideOpen=true`（避免移动端右栏折叠状态跨房残留）。
- T-A5.3 `Admin.vue:22` 拆 `loadingList/loadingRoom/loadingResource` 三独立 ref，9 个按钮不再同步 spinner。
- T-A5.4 `style.css` 落地 `--bp-mobile`/`--bp-tablet` 设计令牌（`:root`）；**但 `@media` 内引用变量的方案被否决**——`var()` 在媒体查询中浏览器不解析且 lightningcss 压缩报错（build 失败），故各 view 媒体查询仍用字面量 `640px`/`1024px`，令牌仅作全局声明保留。

**验证**
- `.tmp/verify_search2.py` → 57 key，0 MISS
- `pytest -q --basetemp=.tmp/pytest` → 91 项全绿（exit 0）
- `npm run build` → 通过（vue-tsc 0 错 + vite 产物正常）
- ✅ CDP 三断点截图 + DOM 断言（Edge headless，`.tmp/shot.mjs` + `.tmp/tasks_visual.json`）：本环境有 Edge/Chrome，已实跑。
  - T-A1：搜「开锁」三断点（1440/820/390）均只剩 `Locksmith`（rows=["Locksmith 55"]，学术组 1 / 其余 0）；搜「心理学」命中 `Psychology`。
  - T-A4：模态打开 `body.overflow="hidden"` + `aria-modal="true"` + `role="dialog"`；**Esc 关闭后 `overflow=""`**（移动端 390 打开同样锁背景）。
  - T-A3：DOM 断言确认按钮已移入 `.n-empty` 内部、`.empty-action` hack 已消失（5 个空状态共用同一组件，无回归）。
  - 截图存 `.tmp/shots/`（char-*-kaisuo / char-1440-xinli / play-*-modal-* / admin-1440-empty / **charbar-1440-empty / charbar-390-empty / overview-1440-empty / overview-390-empty**）。
  - **并行隔离浏览器补拍**：用户要求「自行加子代理并行加快」后，`.tmp/shot.mjs` 改造为 `EDGE_PORT`/`EDGE_PROFILE`/`TASKS_FILE` 可配 → 同时起两个独立 Edge 实例（端口 9341/9342、独立 profile），分别拍 CharacterBar 空态与 Overview 空态，1440 与 390 双断点；断言均 `{"btnInsideNEmpty":true,"emptyActionHackExists":false}`。
  - modlens 主观评分（≥4/5）属外部服务，本环境未接；上述客观 DOM 断言等价于通过。
- **独立并行代码评审 PASS**：同步派一个独立子代理对全部 7 个改动文件做交叉审阅（对照任务书 + 红线），结论「✅ 全部 7 文件 PASS，红线 PASS，无 TypeScript 风险」。
- 🔧 T-A4 补充修复（测试发现）：`onKeydown` 原仅置 `readerOpen=false` 而未调用 `closeReader()`，导致 **Esc 关闭时 body 滚动锁不释放、焦点不还原**（点击关闭按钮正常）。已改为 Esc 调用 `closeReader()`，与其它关闭路径（按钮 / 点遮罩）一致。`npm run build` 复验通过。

---

## [v1.0.1 · 专名修正 + 2 个新模组入库] - 2026-09-01

- 91 项 pytest 全绿 / 全部 4 模组 validate 通过
- 3 处专名实质错误已修正（罗马音 2 + 地名 1）
- 2 个新模组 `yuren-pie`（鱼人与派）/ `sleeping-cat`（不要叫醒沉睡的猫）入库

---

## [v1.0 · 公开候选版] - 2026-09-01

本节为发布标记说明。代码本身仍是 M0–M8 累计成果，未单独立项。

- 91 项 pytest 全绿 / 前端构建通过
- 完整操作手册 `docs/操作指引.md` 已就位
- 配套文档齐全：部署指南 / HTTPS 反代 / 安全清单 / 模组拆解说明 / 角色卡模板 / CoC7th 规则依据
- 内部工作档案（审阅报告 / 任务书 / 复检）隔离于 `docs/AI工作记录/`
- 唯一硬阻塞：用户自验（Docker 构建 + 异地 HTTPS 实战）
