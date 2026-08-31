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
