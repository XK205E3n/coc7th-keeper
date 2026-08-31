# CoC7th 守密人 · 飞书跑团

> **在飞书里跑《克苏鲁的呼唤》第七版，1-2 人友好**

DeepSeek Harness 常驻后台 + 飞书群消息（dsh-lark-bot 桥接）+ `coc7th-keeper` skill —— 让 AI 在飞书群里担任守密人（KP），玩家只需要在飞书里发指令，**不需要**安装任何桌面工具。

> 📌 本目录是 **skill 工作区内的权威副本**（v0.2.0 起为唯一部署来源）；项目总览见仓库根目录 `README.md`。

---

## 特点

- ✅ **飞书即一切**：玩家在飞书群发 `/coc ...`，机器人把消息注入 DeepSeek Harness 中的 Agent，Agent 加载 skill 后调用 Python 规则脚本，再以飞书卡片回传结果。**整个过程不需要打开桌面 GUI。**
- ✅ **完整的 CoC7th 规则**：build、技能检定、对抗、幸运、理智、战斗、重伤
- ✅ **加密安全随机数**：基于 Python `secrets.SystemRandom`，每次投骰写入审计日志（`dice.log`，仅追加）
- ✅ **AI 守密人**：守密人十条 + 场景自适应风格（神秘冷峻 / 紧张紧凑 / 慢热会话）
- ✅ **官方短模组《惊魂》**：1 守密人 + 1-2 玩家，约 2-3 小时
- ✅ **频道感知隐私铁律**（最高优先级）：跑团群聊零 KP 数据——守密人旁注 / 内部提示 / 未揭示线索与真相 / 隐藏数值 / 失败后果剧透 / `kp-notes` 摘录 / 机器绝对路径一律禁止进群聊；KP 数据只在守密人私聊且确认身份时展示，绝不回流群聊（详见 `SKILL.md` §2）
- ✅ **单一工作区布局**：Agent 只加载本工作区副本（`DSH_LARK_WORKSPACE` 锁定仓库根目录），模组目录由 `COC_MODULES_DIR` 锚定，不写死机器路径
- ✅ **复用 DSH 社区现成飞书集成**：`PlutoKeating/dsh-lark-bot` —— 自带安全网守护、自更新、群聊隔离、Markdown 卡片

---

## 目录结构

```
.dsh/skills/coc7th-keeper/
├── SKILL.md                  # skill 入口（守密人系统提示词；含 §2 隐私铁律）
├── README.md                 # 本文件（skill 总览）
├── DEPLOY.md                 # 完整部署手册
├── USER_GUIDE.md             # 给玩家的说明书
├── scripts/                  # Python 规则脚本（CSPRNG；统一经 .dsh/bin/coc.cmd|ps1 调用）
│   ├── _common.py            #   共享：随机数 / 审计 / JSON IO / COC_MODULES_DIR 锚点 / 路径净化
│   ├── roll.py               #   任意骰子表达式
│   ├── check.py              #   技能 / 对抗 / 联合 / 幸运
│   ├── build.py              #   角色 build
│   ├── sanity.py             #   理智检定 + 损失 + 实时疯狂
│   ├── combat.py             #   战斗：先攻 / 攻击 / 伤害 / 重伤
│   ├── room.py               #   房间生命周期
│   ├── modules.py            #   模组列表 / 简介
│   ├── help.py               #   /coc help 渲染（唯一权威源）
│   ├── build_help_cache.py   #   预渲染 help 缓存
│   ├── build_modules_cache.py#   预渲染 modules 缓存
│   ├── build_all_cache.py    #   一键重生所有缓存
│   └── use_pregen.py         #   预制角色复制
├── modules/                  # 模组目标目录（COC_MODULES_DIR 锚点）
│   ├── the-haunting/         #   《惊魂》官方短模组（随仓库分发）
│   │   ├── plot.md / kp-notes.md / clues.md / npcs.json / pregens/
│   └── toy-dancer-comes/     #   《玩具跳着舞蹈来》（第三方授权，不入公开仓库）
│       ├── plot.md / kp-notes.md / clues.md / npcs.json / monsters.json
│       ├── pregens/ / handouts/ / README.md
├── references/               # 规则速查 + 预渲染缓存
│   ├── rules-summary.md      #   规则摘要
│   ├── skills-table.md       #   技能表
│   ├── weapons.md            #   武器
│   ├── sanity-tables.md      #   理智
│   ├── spells.md             #   法术
│   ├── help-cache.md         #   /coc help 预渲染（只读，勿手改）
│   └── modules-cache.md/.json#   /coc modules 预渲染（只读，勿手改）
├── assets/quickstart.md      # 5 分钟快速上手
└── bridge/README.md          # 飞书接入说明（已选定 dsh-lark-bot）
```

---

## 5 分钟上手

```powershell
# 1. 装飞书集成（一键）
npx dsh-lark-bot@latest setup --profile dsh-lark

# 2. 配置你自己的 API Key / Provider / 模型（发布版不捆绑凭据）
#    飞书内：/key /provider /model /config；或本地脚本：.\tools\configure-provider.ps1

# 3. 启动守密人后台
dsh --profile dsh-lark
#    或 .\bot-start.ps1（后台常驻 + 健康检查）
# → 终端打印二维码 → 飞书 App 扫码授权

# 4. 在飞书 App 建跑团群 + 邀请 bot

# 5. 在群里（守密人）发
/coc init demo --module the-haunting --kp 你的飞书名

# 6. 玩家加入
/coc join
/coc use-pregen theron-quist
```

详细步骤见 [`DEPLOY.md`](DEPLOY.md)；玩家视角的说明书见 [`USER_GUIDE.md`](USER_GUIDE.md)。

---

## 工作原理（一图速览）

```
飞书群消息  ──►  dsh-lark-bot（WebSocket 长连接）
                       │
                       ▼ 注入消息（含可信频道上下文 chat_type）
              DeepSeek Harness 中的 Agent（本机进程）
                       │
                       ▼ 加载
              coc7th-keeper skill
                       │
                       ▼ 调用
              scripts/*.py（加密安全随机数 + JSON；经 .dsh/bin/coc.cmd|ps1）
                       │
                       ▼ 输出
              Markdown 中文叙述（跑团数据落 coc-session/）
                       │
                       ▼ dsh-lark-bot 自动转飞书卡片
               飞书群消息
```

**Agent 不处理飞书协议**——全部由 dsh-lark-bot 承担；Agent 按 `chat_type` 执行隐私分支（`SKILL.md` §2）。

---

## 测试（不需要飞书，直接验脚本）

> 所有脚本调用必须走工作区统一入口 `.dsh\bin\coc.cmd` / `.dsh\bin\coc.ps1`
> （wrapper 自动设置 `COC_SESSION_ROOT=<workspace>\coc-session`、`COC_MODULES_DIR=<skill-root>\modules`，
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
.\.dsh\bin\coc.ps1 build_all_cache        # 重生 help / modules 缓存
```

---

## 许可与致谢

- 本 skill 是 CoC7th 跑团辅助工具；项目本体（脚本、文档、工具）以 **MIT 协议**发布，© 2026 XK205E3n（见仓库根目录 `LICENSE`）。
- 剧本《The Haunting》（惊魂）：Chaosium 官方短模组（爱好者公平使用范围），随仓库分发。
- 剧本《玩具跳着舞蹈来》（toy-dancer-comes）：作者 **Yukishiro** 的第三方授权模组；作者**禁止修改后二次发布**，因此**不随公开仓库分发**，仅本地按需使用；模组原 PDF 不进入仓库。
- 飞书集成：`dsh-lark-bot`（AGPLv3）—— [PlutoKeating/dsh-lark-bot](https://github.com/PlutoKeating/dsh-lark-bot)。
