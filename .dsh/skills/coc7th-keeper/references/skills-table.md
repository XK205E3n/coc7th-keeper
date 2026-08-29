# CoC7th 技能表 · 中文版

> 完整职业与技能成长表请参考 Chaosium 官方规则书。
> 本表列出常用技能及其**典型初始值**（不区分职业）。**技能名优先使用中文**。

## 通用技能（默认初始值）

| 中文 | 英文 | 初始值 | 备注 |
|---|---|---|---|
| 会计 | Accounting | 5 | |
| 人类学 | Anthropology | 1 | |
| 估价 | Appraise | 5 | |
| 考古学 | Archaeology | 1 | |
| 艺术与手艺 | Art/Craft | 5 | 选 1 项（如绘画） |
| 魅惑 | Charm | 15 | |
| 攀爬 | Climb | 20 | |
| 信用评级 | Credit Rating | 0 | 视职业 |
| **克苏鲁神话** | **Cthulhu Mythos** | **0** | **不可超过 SAN / 5** |
| 伪装 | Disguise | 5 | |
| **闪避** | **Dodge** | **30** | 关键战斗技能 |
| 汽车驾驶 | Drive Auto | 20 | |
| 电子维修 | Elec Repair | 10 | |
| 套话 | Fast Talk | 5 | |
| **格斗（拳）** | **Fighting(Brawl)** | **25** | |
| 手枪 | Firearms(Handgun) | 20 | |
| 步枪 | Firearms(Rifle) | 25 | |
| 急救 | First Aid | 30 | |
| 历史 | History | 5 | |
| 威胁 | Intimidate | 15 | |
| 跳跃 | Jump | 20 | |
| 母语 | Language(Own) | 20 | = 教育 × 5 |
| 法律 | Law | 5 | |
| 图书馆使用 | Library Use | 20 | |
| **倾听** | **Listen** | **20** | |
| 开锁 | Locksmith | 1 | |
| 机械维修 | Mech Repair | 10 | |
| 医学 | Medicine | 1 | |
| 博物学 | Natural World | 10 | |
| 导航 | Navigate | 10 | |
| 神秘学 | Occult | 5 | |
| 说服 | Persuade | 10 | |
| 驾驶 | Pilot | 1 | |
| 心理学 | Psychology | 10 | |
| 精神分析 | Psychoanalysis | 1 | 用于治疗临时疯狂 |
| 骑乘 | Ride | 5 | |
| 科学 | Science | 1 | 选 1 项 |
| 巧手 | Sleight of Hand | 10 | |
| **侦查** | **Spot Hidden** | **25** | 关键调查技能 |
| 潜行 | Stealth | 20 | |
| 生存 | Survival | 10 | |
| 游泳 | Swim | 20 | |
| 投掷 | Throw | 20 | |
| 追踪 | Track | 10 | |

## 关键战斗 / 调查技能（Agent 速记）

- **闪避 Dodge 30**：默认；战斗中自动成功不成长。
- **格斗（拳）Fighting(Brawl) 25**：空手套；可用武器时切换至对应武器技能。
- **手枪 Firearms(Handgun) 20 / 步枪 Rifle 25**：默认；具体武器需检定。
- **侦查 Spot Hidden 25**：发现隐藏物、发现暗门、察觉伏击。
- **倾听 Listen 20**：听门外动静、察觉跟踪。
- **克苏鲁神话 Cthulhu Mythos 0**：知道越多越疯；最多意志 / 5。

## 职业常用差异化（PL 自选）

| 职业 | 高起始技能 |
|---|---|
| **教授 / 学者** | 图书馆使用 60+、侦查 50+、克苏鲁神话起步 5+ |
| **私家侦探** | 侦查 60+、手枪 50+、法律 40+ |
| **医生** | 医学 60+、急救 50+、心理学 40+ |
| **作家 / 记者** | 心理学 50+、图书馆使用 50+、套话 40+ |
| **退伍军人** | 步枪 60+、格斗（拳）60+、闪避 40+ |
| **警察** | 手枪 50+、法律 50+、说服 40+ |
| **神职人员** | 神秘学 50+、心理学 50+、克苏鲁神话 5+ |
| **艺术家** | 艺术与手艺 60+、魅惑 50+、心理学 40+ |

## 中文技能名 ↔ 英文技能名 速查

Agent 在调用 `/coc check` 时，应**同时支持中英文技能名**：

| 中文 | 英文（脚本参数） |
|---|---|
| 侦查 | Spot Hidden |
| 倾听 | Listen |
| 闪避 | Dodge |
| 格斗 | Fighting(Brawl) |
| 手枪 | Firearms(Handgun) |
| 步枪 | Firearms(Rifle) |
| 急救 | First Aid |
| 心理学 | Psychology |
| 魅惑 | Charm |
| 说服 | Persuade |
| 套话 | Fast Talk |
| 威胁 | Intimidate |
| 攀爬 | Climb |
| 跳跃 | Jump |
| 投掷 | Throw |
| 游泳 | Swim |
| 潜行 | Stealth |
| 追踪 | Track |
| 神秘学 | Occult |
| 图书馆使用 | Library Use |
| 开锁 | Locksmith |
| 巧手 | Sleight of Hand |
| 信用评级 | Credit Rating |
| 法律 | Law |
| 历史 | History |
| 会计 | Accounting |
| 估价 | Appraise |
| 伪装 | Disguise |
| 信用 | Credit Rating |
| 精神分析 | Psychoanalysis |
| 自然 | Natural World |
| 导航 | Navigate |
| 驾驶 | Pilot |
| 骑乘 | Ride |
| 生存 | Survival |
| 母语 | Language(English) |

> Agent 接收玩家发 `/coc check 侦查` 时，自动映射到 `check.py skill "Spot Hidden" ...`。