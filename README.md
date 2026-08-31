# 跑团 Web 平台（开发中）

> 自托管的 AI 跑团（TRPG）Web 平台：单人 / 多人联机，本期 CoC7th。纯 Web 应用，不依赖飞书等群聊软件。

## 当前状态

**M0–M4 已完成**：后端（规则引擎库化 + SQLite 存档 + REST + SSE + AI 守密人两阶段管线 + **单人自动推进闭环**）+ 前端（五大工作区 + **总览/角色/游玩三页可玩**），**58 项 pytest 全绿**。下一步：M5 多人联机（邀请 / 回合 / 私密 / 房主管理 / 开发者监视）。

| 文档 | 地址 | 说明 |
|---|---|---|
| **开发里程碑清单** | [`MILESTONES.md`](MILESTONES.md) | ⭐ 逐个 milestone 的任务 / 产出 / 验收，M0 / M1 已勾选完成 |
| 变更日志 | [`CHANGELOG.md`](CHANGELOG.md) | ✅ 每次里程碑完成推送后更新的条目记录 |
| 计划书 | [`docs/跑团Web平台计划书.md`](docs/跑团Web平台计划书.md) | 参考对象（DiceFrame）审核、方案对比、总体架构 |
| 实施方案 | [`docs/跑团Web平台-实施方案.md`](docs/跑团Web平台-实施方案.md) | 技术选型、目录结构、API 契约、回合状态机 |
| 模组拆解说明 | [`docs/模组拆解说明.md`](docs/模组拆解说明.md) | v2 模组包格式（`trpg-module/v1` + `scenes.json`） |
| 归档说明 | [`archive/coc7th-keeper-feishu/归档说明.md`](archive/coc7th-keeper-feishu/归档说明.md) | 飞书版旧项目归档说明与素材复用指引（素材源） |

## 目录结构

```
跑团/
├── MILESTONES.md          # ★ 开发里程碑清单（M0–M4 已完成）
├── CHANGELOG.md           # ★ 变更日志（每里程碑推送后更新）
├── server/                # ★ FastAPI 后端（核心交付物）
│   ├── main.py            #   入口：/api/health，端口 18000
│   ├── config.py          #   data/config.json + secrets.json 读写
│   ├── engine/            # ★ 规则引擎库（自归档 skill 复制并库化，CLI 兼容）
│   ├── store.py           #   SQLite 存档（WAL，每游戏一个 db，十张表）
│   ├── roundman.py        #   回合调度器 + 房间级写锁 + 管线锁 + 场景调度
│   ├── sse.py             #   房间级 SSE 事件总线（心跳 + 重连回放）
│   ├── modules.py         #   模组 v2 数据层（扫描 modules/）
│   ├── state_apply.py     #   ★ 五类状态变动校验落库 + 禁用词过滤
│   ├── gm/                # ★ AI 守密人（llm / prompts / adjudicate / narrate / pipeline / simulate）
│   ├── api/               #   games.py（REST+SSE+自动推进）/ modules.py（含附件图片）
│   └── tests/             #   pytest 冒烟（58 项）
├── frontend/              # ★ Vue 3 前端（总览/角色/游玩三页可玩 + 组件库）
├── modules/               # ★ v2 模组（惊魂 / 玩具跳着舞蹈来，含 scenes.json + handouts）
├── prompts/               # ★ 守密人系统提示词（gm_system.md，编译产物）
├── docs/                  # 计划书 + 实施方案 + 模组拆解说明 + CoC7th 规则依据
├── archive/               # 飞书版旧项目归档（素材源；旧会话数据已清理）
├── data/                  # ★ 运行时配置与存档（不入库）
└── coc-session/           # 占位（新存档在 SQLite data/games/，不再用文件格式）
```

## 技术栈

后端 FastAPI + uvicorn + **AsyncOpenAI（AI 守密人：裁判/叙事两阶段，DeepSeek / Ollama / 硅基流动兼容，断网降级）** ｜ 规则引擎自 CoC7th 归档 skill 库化 ｜ 存档 **SQLite（WAL）**，每游戏一库 ｜ 实时 **SSE** ｜ 前端 Vue 3 + TS + Vite + Naive UI + Pinia。

## 快速启动（M0 已完成）

```bash
# 后端（首次先建虚拟环境）
python -m venv .venv
.venv\Scripts\python -m pip install fastapi "uvicorn[standard]" openai httpx pytest
.venv\Scripts\python server/main.py          # http://localhost:18000  (/api/health)
# 前端
cd frontend && npm i && npm run dev          # http://localhost:5173（/api 已代理到 18000）
```

## 运行测试

```bash
.venv\Scripts\python -m pytest               # 58 项冒烟（引擎回归 / 存档并发 / 模组 v2 / REST 全链路 / SSE / AI 守密人 / 单人自动推进）
```

## AI 守密人 CLI 模拟（M2 验收）

```bash
.venv\Scripts\python -m server.gm.simulate --mode skill    # 技能检定
.venv\Scripts\python -m server.gm.simulate --mode sanity   # 理智检定
.venv\Scripts\python -m server.gm.simulate --mode none     # 无需检定
```
