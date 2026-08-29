# CoC7th 规则速查 · 中文版

> 本文件供 Agent 在不确定规则时查阅。完整规则请参考 Chaosium 官方第七版守密人手册（Keeper Rulebook）。
> 规则术语英文与中文并排，**优先使用中文**，英文仅用于匹配脚本参数。

## 1. 判定档位（掷出 1d100，与技能值对比）

| 掷骰值 | 中文结果 | 英文 | 备注 |
|---|---|---|---|
| 1 | **大成功** | Critical / Extreme | 一击必杀级表现 |
| ≤ 技能 / 5 | **极难成功** | Extreme | 极小概率 |
| ≤ 技能 / 2 | **困难成功** | Hard | 较难 |
| ≤ 技能 | **成功** | Regular | 基本达成 |
| > 技能（且 < 100） | **失败** | Failure | 没做到 |
| 100 | **大失败** | Fumble | 出大问题 |

## 2. 检定种类（中英文对照）

| 中文 | 英文 | 说明 |
|---|---|---|
| 单项检定 | Regular Check | 单次掷骰与目标技能值比对 |
| 对抗检定 | Opposed Check | 双方各掷一次，成功档高者胜 |
| 联合检定 | Combined Check | 每名协助者提升 +20，封顶 +80 |
| 幸运检定 | Luck Check | 以当前幸运（LUK）为目标技能 |
| 成长检定 | Improvement Check | 成功后技能可成长 1d10 |
| 追加检定 | Pushed Check | 失败后可掷 1d6：1=放弃；2-5=继续失败；6=重投 |

## 3. 伤害与战斗

### 伤害加值（DB，Damage Bonus）

由力量（STR）+ 体型（SIZ）查表：

| 总和 | DB（中文） | 英文 | 说明 |
|---|---|---|---|
| ≤ 64 | -2 | -2 | 减 1d4（最低 0） |
| 65-84 | -1 | -1 | |
| 85-124 | 0 | 0 | |
| 125-164 | +1d4 | +1d4 | |
| 165-204 | +1d6 | +1d6 | |
| ≥ 205 | +2d6 | +2d6 | |

### 战斗轮（Combat Round）

1. **先攻**（Initiative）：敏捷（DEX）+ 1d10，高者先行动
2. **攻击**（Attack）：投攻击技能 vs 对方闪避（Dodge）
3. **命中**：成功则掷武器伤害 + DB
4. **闪避**（Dodge）：默认 30%，成功减伤一半

### 重伤表（Major Wound）

体力 ≤ 0 时掷 1d10：

| 掷骰值 | 后果 | 英文 |
|---|---|---|
| 1-3 | 失血过多：每轮 1d3 伤害直至 Medicine 止血 | Bleeding |
| 4-5 | 昏迷 | Unconscious |
| 6-7 | 重伤：体力上限永久 -1d10 | Major Wound |
| 8 | 体力上限减半 | Crippled |
| 9-10 | 濒死：下一轮未救治即死亡 | Death's Door |

## 4. 理智机制（详见 sanity-tables.md）

- **理智上限（SAN max）= 意志 × 5**（POW × 5）
- **理智损失骰（SAN Loss Die）**（失败时按损失掷）：

| 损失量 | 骰面 | 英文 |
|---|---|---|
| 0 | 1d10 | |
| 1 | 1d3 | |
| 2-4 | 1d4 | |
| ≥ 5 | 1d6 |（可能触发实时疯狂） |

- **疯狂发作**（**Insanity**）：损失 ≥ 5 且失败 → 实时疯狂表（1d10）
- **不定疯狂**（**Indefinite Insanity**）：长期 SAN < max

## 5. 关键派生值

| 项目 | 计算 | 英文 |
|---|---|---|
| 体力（HP） | ⌈(体质 + 体型) / 10⌉ | Hit Points |
| 魔法（MP） | ⌈意志 / 5⌉ | Magic Points |
| 理智（SAN，起始） | 意志 × 5 | Sanity |
| 移动（MOV） | 8（力量 < 敏捷 且 力量 < 80 → -1；体型 > 79 → -1；最低 1） | Movement |
| 伤害加值（DB） | 查表 | Damage Bonus |
| 体格（BUILD） | (力量 + 体型) / 10 取整 | Build |

## 6. 通用行动消耗回合

| 动作 | 回合数 | 英文 |
|---|---|---|
| 移动 ≤ MOV | 1 | Move |
| 攻击近战 | 1 | Melee Attack |
| 攻击远程（短距离） | 1 | Ranged Attack |
| 装填重型武器 | 1 整回合 | Reload |
| 短对话 | 1 | Short Conversation |
| 持续施法 | 全回合（无法同时攻击） | Continuous Casting |

## 7. 调查员年龄调整

| 年龄 | 调整 | 英文 |
|---|---|---|
| 15-19 | 教育 / 2；EDU ≤ 95 时 -5 | Young Investigator |
| 20-39 | 教育调整无 | Adult |
| 40-49 | 成功 EDU 减半；魅力 -5 | Middle Age |
| 50-59 | 成功 EDU 减半；魅力 -10 | Senior |
| 60-69 | 成功 EDU 减半；魅力 -15 | Old |
| 70-79 | 成功 EDU 减半；魅力 -20 | Very Old |
| 80+ | 魅力 -25；MOV -2 | Ancient |

## 8. 常用术语对照表

| 中文 | 英文 | 缩写 |
|---|---|---|
| 守密人 | Keeper | KP |
| 玩家 | Player | PL |
| 调查员 | Investigator | PC |
| 非玩家角色 | Non-Player Character | NPC |
| 属性 | Attribute / Characteristic | — |
| 技能 | Skill | — |
| 经验值 | Experience Points | XP / Cthulhu Mythos |
| 神话知识 | Cthulhu Mythos | CM |
| 理智检定 | Sanity Check | SAN Check |
| 战斗轮 | Combat Round | CR |
| 推进一次行动 | Push the Roll | — |
| 重伤 | Major Wound | — |
| 临时疯狂 | Temporary Insanity | — |
| 不定疯狂 | Indefinite Insanity | — |
| 实时疯狂 | Real-time Insanity | — |

---

**相关文档**：
- 技能表：`skills-table.md`
- 武器与护甲：`weapons.md`
- 理智机制（含疯狂表）：`sanity-tables.md`
- 神话魔法：`spells.md`