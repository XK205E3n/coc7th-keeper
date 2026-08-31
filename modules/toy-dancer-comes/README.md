# 《玩具跳着舞蹈来》单人模组 · 使用说明

> 作者：Yukishiro | 整合者：DeepSeek Harness CoC7th KP
> 模块 ID：`toy-dancer-comes` | 房间示例：`toy-dance`
> 类型：1 KP + 1 PL 单人剧本 | 时长 3-4 小时
> 规则：克苏鲁的呼唤 第七版（CoC7th）

---

## 1. 快速启动（飞书群）

```
/coc init toy-dance --module toy-dancer-comes --kp <守密人名>
/coc use-pregen relay
/coc status
/coc scene 一楼大厅
```

> 🔒 **守密人**：在游戏开始前**务必**先 `read` 本模块下的 `kp-notes.md`（真相笔记），熟悉完整剧情。

---

## 2. 模组文件结构

```
.dsh/skills/coc7th-keeper/modules/toy-dancer-comes/
├── README.md             # 本文件（KP 使用说明）
├── meta.json             # 模组元数据（自动发现用）
├── plot.md               # 玩家视角剧本大纲
├── kp-notes.md           # 守密人真相笔记（**绝不展示**）
├── clues.md              # 线索与调查日志
├── npcs.json             # NPC 数据（含伪装屋主、木偶 NPC、玩具修理者）
├── monsters.json         # 神话生物 / 木偶 / 童年玩具 / 肉体改造表
├── pregens/
│   └── relay.json        # 预制角色（中转 / 记者）
└── handouts/
    ├── cover.jpeg                 # 封面（青绿背景舞蹈木偶）
    ├── fake-shen-portrait.jpeg    # 伪装沈珂成立绘
    ├── half-timber-reference.jpeg # 半露木构架式建筑参考
    ├── kp-tip-1.jpeg              # 守密人贴士 1（谢尔顿容器说明）
    ├── kp-tip-2.jpeg              # 守密人贴士 2（半露木建筑定义）
    ├── maps/
    │   ├── qiulin-park-map.jpeg   # 秋林苑园区地图
    │   ├── floor-1.jpeg           # 一楼平面图
    │   └── floor-2.jpeg           # 二楼平面图
    └── handouts/
        ├── house-of-tragedies.jpeg # 展板：惨剧不断的住宅
        ├── witch-curse.jpeg       # 展板：魔女的灭门诅咒
        └── shen-investigation.jpeg # 展板：沈珂成手写笔记
```

---

## 3. 玩家剧情大纲（PL 视角）

阅读 `plot.md` 即可获取完整的 10 个场景调度。

### 故事梗概

2012 年 7 月，调查员因工作或学业来到松寒市，受远房亲戚**沈珂成**邀请入住「**秋林苑 7 号楼**」（半露木构架式英式别墅）。**真相是：「沈珂成」是百年前的英国玩具设计师**谢尔顿·夏普**利用 1991 年失踪的松本家长子的身体伪装的恶灵；园区内所有 NPC 已被献祭，由谢尔顿操纵木偶伪造的幻象。调查员需要在 7 月 17 日午夜前与**玩具修理者**（犹格-索托斯的化身）建立联系，借助童年玩具击溃谢尔顿灵魂。

### 三大结局

| 结局 | 触发条件 | 后果 |
|---|---|---|
| **A 跳舞的玩具** | 接受肉体改造 + 击溃谢尔顿 | 成功脱困，SAN 恢复，Cthulhu Mythos +2% |
| **B 乖巧的玩具** | 拒绝改造（模型被毁）+ 战败 | 成为玩具修理者藏品 |
| **C 失控的玩具** | 未破坏模型 + 未与玩具修理者建立联系 | 被木偶化 + 记忆被抹消 |

---

## 4. 守密人工作流

### 4.1 开场准备

1. `read kp-notes.md`（真相笔记，已自动加载到上下文）
2. `read npcs.json` 与 `monsters.json` 备用
3. 准备好 11 张图片素材的分发时机：

| 时机 | 图片 |
|---|---|
| 开场 | `cover.jpeg`（封面）+ `maps/qiulin-park-map.jpeg`（园区图） |
| 进入一楼 | `maps/floor-1.jpeg`（一楼平面图） |
| 进入二楼 | `maps/floor-2.jpeg`（二楼平面图） |
| 阁楼展板 | `handouts/house-of-tragedies.jpeg` + `witch-curse.jpeg` |
| 沈珂成笔记 | `handouts/shen-investigation.jpeg` |
| 介绍沈珂成 | `fake-shen-portrait.jpeg`（外貌参考） |
| 玩家问别墅来历 | `half-timber-reference.jpeg`（半露木建筑参考） |

### 4.2 标准检定流程

当玩家说「我进入二楼卧室仔细观察天花板」时：

1. KP 确认场景位于二楼
2. **询问玩家**：「是否进行侦查（Spot Hidden）检定？阈值 35。」——**绝不替玩家决定**
3. 玩家发 `/coc check Spot Hidden 35 --why 二楼天花板异常`
4. KP 用 Python 脚本（`check.py skill`）执行检定
5. 把结果写入 `log.md` 与 `kp-notes.md`，分发到飞书

### 4.3 理智检定流程

每次场景触发的理智损失表（详见 `kp-notes.md` 中段）：

```
/coc san <损失量> [原因]
```

玩具修理屋中的理智检定**不会触发实时疯狂**——避免流程被中断。

### 4.4 战斗轮

最终战 HP 14 的谢尔顿 + 童年玩具 / 肉体改造能力：

```
/coc attack 砸炮枪 70 1d8 +0 --by relay   # 砸炮枪用 Firearms(Handgun)
/coc dodge 50                              # 谢尔顿的 50% 斗殴时，调查员闪避
```

**关键**：常规手段对谢尔顿无效，必须使用童年玩具或肉体改造能力。

### 4.5 突破围堵

四个选项：
- **小飞象面具**（最佳）：直接安全脱困，无须检定
- **强行突围**：4 次敏捷 / 战技对抗，每失败 1 次 1d3 伤害

### 4.6 1d6 肉体改造表

接受玩具修理者的实验后掷 1d6：

| d6 | 改造 | 效果 |
|---|---|---|
| 1 | 鹰眼 | 攻击轮奖励骰 |
| 2 | 猫爪 | 1d4+DB，可伤灵魂 |
| 3 | 犬牙 | 1d4+DB，可伤灵魂（撕咬） |
| 4 | 兔腿 | 闪避奖励骰 |
| 5 | 猿臂 | 双手战斗技能一回合 2 动 |
| 6 | 猪肚 | 撕肉回 1d3 HP，吃肉 0/1 SAN |

### 4.7 童年玩具四选一

| 道具 | 效果 |
|---|---|
| 砸炮枪 | 1d8 / 6 发 / 15 码 |
| 如意棒 | 1d8 / 近战 |
| 呲水枪 | 5 次击中击溃灵魂（左臂→右臂→左腿→右腿→头部） |
| 兵人军团 | 1d10 / 需 APP 检定 |

---

## 5. 重要守密人贴士

### 5.1 「沈珂成」的伪装

- 用松本幸嗣身体伪装；吸取真正沈珂成的记忆
- 玩家一家 20 年没见过沈家人 → 只会想起 10 岁小孩
- 表现热心温柔；尽可能获取信任
- 离开借口：「处理工作」「收拾行李」

### 5.2 NPC 的「敲太阳穴」细节

- 所有 NPC 时不时用食指关节敲击太阳穴
- 这是谢尔顿操纵的标志
- **最终战后的巡警也会做这个动作** —— 给玩家的最后「惊喜」

### 5.3 理智损失节奏

- 开场到「沈珂成」离开：**0**
- 一楼探索：**0**（翻《世界奇妙玩具物语》+0/1）
- 二楼探索：**0~1**
- 园区 NPC 接触：**0**
- 众人目送：**0/1d3**
- 鬼打墙：**1/1d3**
- 玩具修理屋：**1/1d8 + 1/1d6 = 2/2d14**（不疯狂）
- 阁楼微缩模型：**1/1d6**
- 改造后：**1d3/1d6**

**总上限**：约 8-12 SAN 损失。POW 65 的预制角色起始 SAN 325，**最终战仍有 30+ SAN 余裕**。

### 5.4 微缩模型的关键

- **微缩模型 = 古宅心脏**
- **破坏微缩模型**：谢尔顿灵魂变脆弱 + 木偶失去控制
- **只有玩具修理者的神秘液体能腐蚀模型**
- **人类手段完全无效**

### 5.5 「沈珂成」的失联时机

- KP 酌情安排
- 推荐：发现书架后铁门后，「沈珂成」含糊其辞 → 一段时间后消息不回、电话无人接听

---

## 6. 与 CoC7th KP 标准流程的整合

本模组完全兼容 `.dsh/skills/coc7th-keeper` 下的所有脚本与指令。

### 6.1 飞书指令（PL 视角）

| 指令 | 用途 |
|---|---|
| `/coc init toy-dance --module toy-dancer-comes --kp <name>` | KP 创建房间 |
| `/coc use-pregen relay` | PL 使用预制角色 |
| `/coc status` | 查看房间状态 |
| `/coc check <技能> [值]` | 技能检定 |
| `/coc luck` | 幸运检定 |
| `/coc san <损失量>` | 理智检定 |
| `/coc attack <技能> <对方闪避> <伤害> <加值>` | 攻击 |
| `/coc dodge <对方攻击>` | 闪避 |
| `/coc roll <表达式>` | 任意投骰 |
| `/coc say <台词>` | 角色发言 |
| `/coc scene <位置>` | KP 描述场景 |
| `/coc handout <文件>` | KP 展示图片/展板 |

### 6.2 脚本调用（KP 内部）

```powershell
# 全部走工作区统一入口（路径全在 workspace 内，零 plan-gate）
# 推荐用 PowerShell 版（agent 默认）；cmd 版给一键 .bat 用

# 技能检定
.\.dsh\bin\coc.ps1 check skill "Spot Hidden" 35 --by relay --room toy-dance --why "二楼天花板异常"

# 理智检定（--player-file 自动相对 <workspace>\coc-session 解析）
.\.dsh\bin\coc.ps1 sanity check --player-file "toy-dance/players/relay.json" 5 --by kp --room toy-dance --why "直视玩具修理者"

# 战斗
.\.dsh\bin\coc.ps1 combat attack 50 25 1d8 +0 --by relay --room toy-dance

# 任意投骰（1d6 肉体改造表）
.\.dsh\bin\coc.ps1 roll 1d6 --by kp --room toy-dance --why "肉体改造表"

# 审计
.\.dsh\bin\coc.ps1 room audit toy-dance --last 20

# 状态
.\.dsh\bin\coc.ps1 room status toy-dance
```

> 老式 `python "<绝对路径>\scripts\<name>.py ..."` 仍然能跑（路径在 workspace 内时），
> 但 DSH plan-gate 对绝对路径会要求人工批准。**强烈推荐统一走 wrapper**。

---

## 7. 视觉资源使用指南

### 7.1 何时分发图片

| 场景 | 图片 | 用途 |
|---|---|---|
| 开场 | `cover.jpeg` | 营造氛围 |
| 开场 | `maps/qiulin-park-map.jpeg` | 园区布局 |
| 与「沈珂成」交流 | `fake-shen-portrait.jpeg` | 外貌参考 |
| 问别墅来历 | `half-timber-reference.jpeg` | 建筑风格参考 |
| 进入一楼 | `maps/floor-1.jpeg` | 房间布局 |
| 进入二楼 | `maps/floor-2.jpeg` | 房间布局 |
| 阁楼 | `handouts/house-of-tragedies.jpeg` | 展板 |
| 阁楼 | `handouts/witch-curse.jpeg` | 展板（含玩具修理者线索） |
| 阁楼 | `handouts/shen-investigation.jpeg` | 展板（沈珂成笔记） |

### 7.2 飞书卡片自动渲染

dsh-lark-bot 会自动将图片路径渲染为飞书图片卡片。KP 调用：

```
/coc handout maps/floor-1
```

bot 会读取 `modules/toy-dancer-comes/handouts/maps/floor-1.jpeg` 并发送为图片消息。

---

## 8. 模组作者备注

> 本模组创作灵感来源于三津田信三先生所著恐怖小说《**忌馆**》，存在部分设定参考，包含对**小林泰三**先生创作的克苏鲁神话形象（玩具修理者）的个人解读与二次创作。
>
> 模组禁止商业用途，禁止修改后二次发布，欢迎非盈利性质的 Log、视频、小说等衍生创作，联系作者请备注「玩具跳着舞蹈来」。

---

## 9. 转换说明（由 DeepSeek Harness 整合）

- 原 PDF：`模组/玩具跳着舞蹈来/Yukishiro-玩具跳着舞蹈来.pdf`（24 页）
- AI 可读版：`模组/玩具跳着舞蹈来/玩具跳着舞蹈来_AI可读版.md`
- 视觉资源提取：用 pymupdf 提取 11 张图片至 `_extracted/`
- 整合目录：`.dsh/skills/coc7th-keeper/modules/toy-dancer-comes/`
- 房间目录：`coc-session/toy-dance/`

转换过程保留了：
- ✅ 24 页正文文本
- ✅ 11 张视觉资源（封面/园区图/楼面图/展板/笔记）
- ✅ 所有规则数值（SAN/HP/MP/DB、检定阈值、伤害骰、道具效果、结局）
- ✅ 守密人贴士（KP 内部使用）

补全的内容：
- ➕ 1d6 肉体改造表 JSON 数据化
- ➕ 童年玩具四选一 JSON 数据化
- ➕ 围堵四兽与鼠群木偶的战斗数据 JSON 化
- ➕ 1 张预制角色（中转 / 记者，POW 65）
- ➕ 完整 KP 工作流（检定流程、理智节奏、图片分发时机、时序表）

---

**祝跑团愉快！**

