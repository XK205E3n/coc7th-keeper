# CoC7th 神话魔法速查 · 中文版

> 神话魔法（Cthulhu Mythos Magic）是 CoC 跑团的高级内容。
> CoC7th 神话魔法分两类：**接触 / 召唤神话生物** 与 **具体法术（书）**。

## 1. 主要神话法术书（按来源）

| 中文 | 英文 | 来源 | 备注 |
|---|---|---|---|
| 《死灵之书》 | Necronomicon | Abdul Alhazred | 经典；大部分守密人视为不可得 |
| 《玄君七章秘经》 | Seven Cryptical Books of Hsan | Hsan | 极少副本 |
| 《伊波恩之书》 | Liber Ivonis | Justin Geoffrey | 早期翻译本 |
| 《蠕虫之秘密》 | Dhol Chants | — | 简化仪式 |
| 《食尸教典仪》 | Cultes des Goules | Comte d'Erlette | 法语 |
| 《塞拉伊诺大预言》 | Cthaat Aquadingen | Friedrich von Juntz | |

## 2. 法术调用一般流程

1. **PL 拥有可识别法术书的语言与 POW**（≥ POW/5 起步）
2. **获得法术**（视守密人规则；多通过 Cthulhu Mythos 检定）
3. **咏唱时间**（视法术，少则 1 回合，多则整仪式）
4. **POW 消耗**：施法者掷 `MP / 5`；成功保留法术，失败失去法术（部分规则）
5. **失败后果**：
   - 法术反（招来所招之物）
   - SAN 损失 1d10
   - 神话接触（视为见到神话生物，触发 SAN 损失）

## 3. 经典神话法术（按书分类）

| 中文 | 英文 | 来源 | 效果 |
|---|---|---|---|
| 枯萎术 | Shrivelling | Necronomicon | 接触生命 1d6 / 法术 POW × 伤害 |
| 与食尸鬼接触 | Contact Ghoul | Necronomicon | 与食尸鬼建立长期契约 |
| 精神支配 | Dominate | 中世纪法术书 | 对人类 / 动物精神控制 |
| 拉之声音 | Voice of Ra | 埃及古籍 | 复活死者传话 |
| 返回沉睡 | Return to the Sleep | Necronomicon | 短暂压制某些神话实体 |
| 长者印记 | Elder Sign | 各书通用 | 抵御神话生物的符印 |

> **本 skill 不内置完整法术表**（CoC7th 玩家手册含大量；约 300+ 条）。守密人在玩家请求施法时按需查询官方书。

## 4. 法术失败（Mythos Magic Fumble）

施法失败时掷 1d10：

| 骰值 | 后果 | 英文 |
|---|---|---|
| 1 | 法术变成"召唤该生物" — 实体到来 | Summoned |
| 2 | 法术反施法者（通常体力 1d10） | Backlash |
| 3 | 神话接触：损失 1d10 SAN | Mythos Exposure |
| 4 | 法术变成另一个相关法术（守密人选） | Transformed |
| 5-7 | 法术失败，无显著效果 | Fizzle |
| 8-9 | 法术部分成功（打折） | Partial |
| 10 | 法术成功但附副作用 | Side Effect |

> 本表可由 `spells.py`（待实现）自动掷。

## 5. 神话生物（Mythos Entities）速查

| 中文 | 英文 | 危险等级 | 弱点 |
|---|---|---|---|
| 深潜者 | Deep Ones | 中 | 银、火、日光 |
| 食尸鬼 | Ghoul | 低 | 火焰 |
| 飞天水螅 | Flying Polyp | 中高 | — |
| 夏尔奈特 | | 高 | — |
| 诺弗·凯 | Hounds of Tindalos | 高 | — |
| 米·戈 | Mi-Go | 中 | 火、电 |
| 奈亚拉托提普 | Nyarlathotep | 神级 | — |
| 阿撒托斯 | Azathoth | 神级 | — |

> 完整神话生物列表见官方怪物图鉴。

## 6. 长者印记（Elder Sign）

**CoC7th 最强大的防护符文**。画在纸上、木头上或物体上，可：
- 阻挡某些神话生物接近
- 压制某些神话实体一段时间
- 给予与神话体对抗的加值

---

**相关文档**：
- 理智机制：`sanity-tables.md`
- 完整规则摘要：`rules-summary.md`
- 技能表：`skills-table.md`