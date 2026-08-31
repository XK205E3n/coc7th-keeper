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
