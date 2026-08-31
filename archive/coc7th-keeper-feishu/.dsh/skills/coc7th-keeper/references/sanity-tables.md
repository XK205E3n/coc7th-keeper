# CoC7th 理智机制速查 · 中文版

> 理智（Sanity，SAN）是 CoC 跑团的核心机制之一。
> 调查员面对恐怖、神话接触、不可名状之物时，会损失 SAN；SAN 过低会触发疯狂。

## 1. 理智损失判定流程

1. **守密人给出 SAN 损失量**（如 `1d4+1`，平均 3.5 点）。
2. **玩家在飞书发**：`/coc san <损失量> [原因]`
3. **Agent 调脚本** `sanity.py check`：按当前 SAN 投骰：
   - **成功**（掷骰 ≤ 当前 SAN）→ **损失 0**
   - **失败**（掷骰 > 当前 SAN）→ **按损失掷骰**：

| 损失量 | 骰面 |
|---|---|
| 0 | 1d10 |
| 1 | 1d3 |
| 2-4 | 1d4 |
| ≥ 5 | 1d6 |

4. **损失 ≥ 5 且失败** → 触发「**实时疯狂**」（1d10 表）
5. **角色卡自动更新**：SAN current 减去实际损失；写入 `sanity.history`

## 2. 实时疯狂表（1d10，Real-Time Insanity）

| 掷骰 | 中文症状 | 英文 |
|---|---|---|
| 1 | 失忆：醒来身处陌生地 | Amnesia |
| 2 | 暴力：破坏周围一切 | Violence |
| 3 | 偏执：感到被跟踪 | Paranoia |
| 4 | 恐慌：无法移动 | Panic |
| 5 | 惊厥：肌肉痉挛 | Seizure |
| 6 | 恍惚：对外界无反应 | Trance |
| 7 | 歇斯底里：大哭 / 尖叫 / 狂笑 | Hysteria |
| 8 | 恐惧症：突发对常见物的恐惧 | Phobia |
| 9 | 躁狂：极度乐观或自大 | Mania |
| 10 | 自残：伤害自己 | Self-Harm |

> 该表由 `sanity.py` 内置；触发后守密人应问询玩家选择如何应对（顺从 / 抵抗精神分析 / 寻求同伴帮助等）。

## 3. 临时疯狂表（持续 1d10 小时，Temporary Insanity）

- 选一张**恐惧症** + 一张**躁狂**列表
- 玩家在发作期间尽量回避恐惧物 / 表现出躁狂行为
- 发作结束后 SAN **不恢复**，但可接受 Psychoanalysis 治疗

## 4. 不定疯狂（长期，Indefinite Insanity）

当 SAN 长期低于 max：

- 守密人与玩家协商**重塑人物概念**
- 角色在每次恢复时必须掷 1d10：1-3 重塑性格
- 本 skill 暂未实现自动重塑（建议手动 `kp-note` 记录）

## 5. 恐惧症简表（Phobias，CoC7th 摘要）

> 完整 100+ 项；本表给出常用 20 项以便玩家速查。

| 中文 | 英文 |
|---|---|
| 害怕黑暗 | Achluophobia |
| 害怕密闭空间 | Claustrophobia |
| 害怕高处 | Acrophobia |
| 害怕开放空间 | Agoraphobia |
| 害怕水 | Hydrophobia |
| 害怕火 | Pyrophobia |
| 害怕血液 | Hemophobia |
| 害怕昆虫 | Entomophobia |
| 害怕陌生人 | Xenophobia |
| 害怕孤独 | Autophobia |
| 害怕人群 | Enochlophobia |
| 害怕野兽 | Zoophobia |
| 害怕噪音 | Phonophobia |
| 害怕镜子 | Spectrophobia |
| 害怕触摸 | Haphephobia |
| 害怕死亡 | Thanatophobia |
| 害怕疾病 | Pathophobia |
| 害怕魔法 / 超自然 | |
| 害怕自己 | |
| 害怕过去 | |

## 6. 躁狂简表（Manias）

| 中文 | 英文 |
|---|---|
| 沉迷书籍 | Bibliomania |
| 囤积物品 | Hoarding |
| 酗酒 | Dipsomania |
| 沉迷工作 | Ergomania |
| 不停洗手 | Ablutomania |
| 反复开关门 / 灯 | |
| 自我伤害 | |
| 强迫清洁 | |
| 不停自言自语 | |
| 熬夜 | |
| 反复回忆 | |
| 远离他人 | |
| 依赖他人 | |
| 恋物 | |
| 拒绝睡眠 | |
| 寻找意义 | |
| 观察他人 | |
| 记录一切 | |
| 画符号 | |
| 囤积食物 | |

## 7. 精神分析治疗（Psychoanalysis）

- 治疗师用精神分析技能（建议建议 60+）每周对玩家治疗 1d3 SAN
- 失败则**治疗师自己**损失 1d3 SAN
- 守密人可让玩家扮演自己的治疗师或由 NPC 担任

## 8. 日常稳定检定（Daily Stability Check）

- 部分规则书要求玩家在每次恢复前前验 1d100：若失败且 SAN 低于 max，**强制触发不定疯狂**
- 本 skill 默认开启此规则

## 9. 神话接触的额外损失（Cthulhu Mythos Exposure）

当玩家首次接触某位神话生物或符号时：
- 立即损失 0/1d10 SAN
- 失败后获得 1d3 点的 Cthulhu Mythos 知识（最高 POW/5）

---

**相关文档**：
- 完整规则摘要：`rules-summary.md` §4
- 神话魔法：`spells.md`
- 技能表：`skills-table.md`