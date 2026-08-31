# -*- coding: utf-8 -*-
"""裁判阶段（M2.3）：本轮全部行动 + 场景 + kp-notes → dice_checks JSON。

- LLM 在线：要求 provider 输出 `{"dice_checks": [...], "private_notes": "..."}`，
  服务端解析并做 **kind 白名单 + 每玩家一条 + target 从角色卡补齐** 的规范化。
- LLM 不可用（断网/无 key/解析失败）：走 `fallback_adjudicate()` 三层规则兜底
  （显式技能名 → 理智特判 → 意图短语），保证游戏不中断
  （验收：LLM 断网时状态应用仍完成；TODO-A：纯自然语言行动可推断技能）。
- 骰果一律由 pipeline 调引擎掷出，裁判只决定"检不检、检什么"。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger("gm.adjudicate")

KINDS = ("skill", "sanity", "luck", "none")

# 中文技能名 → 引擎角色卡技能键（英文）。角色卡 skills 以英文为键。
SKILL_ZH_EN = {
    "侦查": "Spot Hidden", "倾听": "Listen", "闪避": "Dodge",
    "格斗": "Fighting(Brawl)", "格斗（拳）": "Fighting(Brawl)", "拳击": "Fighting(Brawl)",
    "手枪": "Firearms(Handgun)", "步枪": "Firearms(Rifle)",
    "急救": "First Aid", "心理学": "Psychology", "魅惑": "Charm",
    "说服": "Persuade", "套话": "Fast Talk", "威胁": "Intimidate",
    "攀爬": "Climb", "潜行": "Stealth", "追踪": "Track", "神秘学": "Occult",
    "图书馆使用": "Library Use", "图书馆": "Library Use", "开锁": "Locksmith",
    "巧手": "Sleight of Hand", "信用评级": "Credit Rating", "信用": "Credit Rating",
    "法律": "Law", "历史": "History", "会计": "Accounting", "估价": "Appraise",
    "伪装": "Disguise", "精神分析": "Psychoanalysis", "博物学": "Natural World",
    "医学": "Medicine", "科学": "Science", "驾驶": "Pilot", "汽车驾驶": "Drive Auto",
    "电子维修": "Elec Repair", "机械维修": "Mech Repair", "生存": "Survival",
    "游泳": "Swim", "投掷": "Throw", "跳跃": "Jump", "骑乘": "Ride",
    "导航": "Navigate", "母语": "Language(English)", "知识": "Know",
    "克苏鲁神话": "Cthulhu Mythos", "搜索": "Spot Hidden",
}

# 中文技能缺省值（角色卡无此技能时兜底；§4.4 默认值）
DEFAULT_SKILLS_ZH = {
    "侦查": 25, "Spot Hidden": 25, "倾听": 20, "Listen": 20, "闪避": 30,
    "Dodge": 30, "格斗": 25, "格斗（拳）": 25, "Fighting(Brawl)": 25,
    "手枪": 20, "Firearms(Handgun)": 20, "步枪": 25, "Firearms(Rifle)": 25,
    "急救": 30, "First Aid": 30, "心理学": 10, "Psychology": 10,
    "魅惑": 15, "Charm": 15, "说服": 10, "Persuade": 10, "套话": 5,
    "Fast Talk": 5, "威胁": 15, "Intimidate": 15, "攀爬": 20, "Climb": 20,
    "潜行": 20, "Stealth": 20, "追踪": 10, "Track": 10, "神秘学": 5,
    "Occult": 5, "图书馆使用": 20, "Library Use": 20, "开锁": 1,
    "Locksmith": 1, "巧手": 10, "Sleight of Hand": 10, "法律": 5, "Law": 5,
    "历史": 5, "History": 5, "估价": 5, "Appraise": 5, "医学": 1, "Medicine": 1,
    "科学": 1, "Science": 1, "克苏鲁神话": 0, "Cthulhu Mythos": 0, "知识": 25,
    "Know": 25, "搜索": 25,
}


def resolve_skill_value(skill_name: str, character: dict | None) -> int:
    """从角色卡取技能值；查不到用默认值。技能名支持中/英文。"""
    skills = (character or {}).get("data", character or {}).get("skills", {}) or {}
    en = SKILL_ZH_EN.get(str(skill_name).strip(), str(skill_name).strip())
    # 先英文键，再中文键，再默认表
    for key in (en, str(skill_name).strip()):
        v = skills.get(key)
        if isinstance(v, (int, float)) and v > 0:
            return int(v)
    return int(DEFAULT_SKILLS_ZH.get(en, DEFAULT_SKILLS_ZH.get(str(skill_name), 25)))


def _norm_check(item: dict, characters: dict[str, dict],
                seen_uids: set[str]) -> dict | None:
    """单条 dice_check 规范化；不合法（kind 非白名单/重复玩家）返回 None。"""
    kind = str(item.get("kind", "")).strip().lower()
    if kind not in KINDS:
        logger.warning("丢弃非法 kind: %r", item.get("kind"))
        return None
    uid = str(item.get("player_uid", "")).strip()
    if not uid or uid in seen_uids:        # 每玩家每轮至多一条（§7.5）
        return None
    seen_uids.add(uid)
    out: dict[str, Any] = {
        "player_uid": uid, "kind": kind,
        "reason": str(item.get("reason", "") or ""),
    }
    if kind == "skill":
        name = str(item.get("skill") or "侦查").strip()
        target = item.get("target")
        if isinstance(target, (int, float)) and 0 < float(target) <= 100:
            out["target"] = int(target)
        else:
            out["target"] = resolve_skill_value(name, characters.get(uid))
        out["skill"] = name
    elif kind == "sanity":
        loss = item.get("loss")
        out["loss"] = int(loss) if isinstance(loss, (int, float)) and loss > 0 else 1
    return out


def _extract_json(raw: str) -> dict | None:
    """宽容解析：先整段 json.loads，失败则提取第一个 {...} 平衡块。"""
    if not raw:
        return None
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


async def adjudicate(*, actions: list[dict], characters: dict[str, dict],
                     scene: dict | None = None, kp_notes_tail: list[str] | None = None,
                     log_tail: list[str] | None = None, round_no: int = 0,
                     llm: Any = None) -> dict:
    """裁判：行动 → dice_checks。返回 {"dice_checks", "private_notes", "source"}。"""
    if llm is None or not getattr(llm, "available", False):
        return fallback_adjudicate(actions=actions, characters=characters)

    from server.gm import prompts as P
    messages = P.messages_for(
        "adjudicate", round_no=round_no, actions=actions, characters=characters,
        scene=scene, kp_notes_tail=kp_notes_tail, log_tail=log_tail)
    raw = await llm.chat(messages, json_mode=True)   # 可能返回 None
    data = _extract_json(raw) if raw else None
    if not data:
        logger.warning("裁判 JSON 解析失败，降级兜底")
        return fallback_adjudicate(actions=actions, characters=characters)
    seen: set[str] = set()
    checks = []
    for item in data.get("dice_checks", []) or []:
        if not isinstance(item, dict):
            continue
        norm = _norm_check(item, characters, seen)
        if norm:
            checks.append(norm)
    # 空结果不输出任何 dice_check，等价全部 none
    return {
        "dice_checks": checks,
        "private_notes": str(data.get("private_notes", "") or ""),
        "source": "llm",
    }


# ---------------- 兜底判定（LLM 不可用/解析失败） ----------------
#
# 三层判定（TODO-A：玩家纯自然语言行动 → AI 自行推断技能，无需括号标注）：
#   1. 显式技能名检索：文本含中/英文技能名 → 直接采用（兼容（侦查）/（Spot Hidden））；
#   2. 理智特判：看见词 + 恐怖词组合，或明确理智词 → sanity（loss 1）；
#   3. 意图短语规则：口语化短语 → 推断技能（命中第一条即停）；
#   4. 其余 → none（纯叙事推进，不强行加检定）。
# 每名玩家每轮至多一条（§7.5），taken 去重不变。

# ---- 第 1 层：显式技能名检索 ----
# 中文名取 SKILL_ZH_EN 的键，英文取角色卡技能键（SKILL_ZH_EN 的值）。
# 按名称长度降序，优先命中更长的技能名（如"格斗（拳）"先于"格斗"）。
_EXPLICIT_SKILL_PATTERNS: list[tuple[re.Pattern, str]] = []
for _name in sorted(set(SKILL_ZH_EN) | set(SKILL_ZH_EN.values()), key=len, reverse=True):
    _flags = re.IGNORECASE if _name.isascii() else 0
    _EXPLICIT_SKILL_PATTERNS.append((re.compile(re.escape(_name), _flags), _name))


def _match_explicit_skill(text: str) -> str | None:
    """第 1 层：文本包含完整技能名（中/英文）→ 返回该技能名；否则 None。"""
    for pattern, name in _EXPLICIT_SKILL_PATTERNS:
        if pattern.search(text):
            return name
    return None


# ---- 第 2 层：理智特判 ----
_SANITY_SIGHT_WORDS = ("直视", "盯着看", "盯着", "目睹", "看到", "见到",
                       "注视", "直面", "凝视")
_SANITY_HORROR_WORDS = ("蠕动", "血肉", "怪物", "尸体", "触手", "不可名状",
                        "腐烂", "嘶吼", "尖叫", "血")
_SANITY_EXPLICIT_WORDS = ("理智", "害怕", "恐惧", "发疯")
_SANITY_EN_RE = re.compile(r"\bsan(ity)?\b", re.IGNORECASE)


def _match_sanity(text: str) -> bool:
    """第 2 层：明确理智词，或"看见词 + 恐怖词"组合 → 理智检定。"""
    if _SANITY_EN_RE.search(text) or any(w in text for w in _SANITY_EXPLICIT_WORDS):
        return True
    return (any(w in text for w in _SANITY_SIGHT_WORDS)
            and any(w in text for w in _SANITY_HORROR_WORDS))


# ---- 第 3 层：意图短语规则 ----
# 撬/开锁与潜行共用一组（先锁后潜行）：
#   "撬开抽屉的锁" → 开锁 Locksmith；"撬开锁"（字面撬坏）也是开锁；
#   "翻窗户/爬" → 攀爬（由下方攀爬规则接管）。
_LOCK_RE = re.compile(r"开锁|撬锁|撬[^，。；！？!?]{0,8}的锁")


def _match_intent(text: str) -> tuple[str, str] | None:
    """第 3 层：意图短语 → (技能中文名, 理由)。按优先级命中第一条即停。"""
    # 侦查（翻找/寻找/搜索/找暗门/找线索/检查/查看/搜查/翻遍）
    if any(w in text for w in ("翻找", "寻找", "搜索", "找暗门", "找线索",
                               "检查", "查看", "搜查", "翻遍")):
        return "侦查", "调查/检索"
    # 开锁 / 潜行（先锁后潜行）
    if _LOCK_RE.search(text):
        return "开锁", "撬开锁具"
    if any(w in text for w in ("偷", "溜进", "偷偷", "潜行", "潜入")):
        return "潜行", "潜行潜入"
    # 倾听（侧耳/听/动静/脚步声/门后/隔壁）
    if any(w in text for w in ("侧耳", "听", "动静", "脚步声", "门后", "隔壁")):
        return "倾听", "听觉调查"
    # 图书馆使用（查资料/翻书/图书馆/查阅/文献/档案）
    if any(w in text for w in ("查资料", "翻书", "图书馆", "查阅", "文献", "档案")):
        return "图书馆使用", "文献调查"
    # 社交：魅惑 / 套话 / 威胁 / 说服
    if any(w in text for w in ("搭讪", "讨好")):
        return "魅惑", "社交魅力"
    if any(w in text for w in ("套话", "打听", "试探")):
        return "套话", "社交套话"
    if any(w in text for w in ("威胁", "恐吓", "威吓")):
        return "威胁", "社交威胁"
    if any(w in text for w in ("说服", "劝", "谈判")):
        return "说服", "社交说服"
    # 心理学（观察人的表情/察言观色/识破）
    if any(w in text for w in ("观察人的表情", "察言观色", "识破")):
        return "心理学", "观察意图"
    # 射击（举起/开枪/射击/瞄准/打枪）
    if any(w in text for w in ("举起", "开枪", "射击", "瞄准", "打枪")):
        return "手枪", "射击"
    # 格斗（格斗/拳/搏斗/殴打/攻击/打斗/战斗）
    if any(w in text for w in ("格斗", "拳", "搏斗", "殴打", "攻击", "打斗", "战斗")):
        return "格斗（拳）", "近战格斗"
    # 攀爬（攀爬/爬上/爬下/翻窗户/翻墙/爬）
    if any(w in text for w in ("攀爬", "爬上", "爬下", "翻窗户", "翻墙", "爬")):
        return "攀爬", "攀爬"
    # 急救（包扎/止血/急救/抢救/医治）
    if any(w in text for w in ("包扎", "止血", "急救", "抢救", "医治")):
        return "急救", "急救"
    return None


def fallback_adjudicate(*, actions: list[dict],
                        characters: dict[str, dict]) -> dict:
    """三层兜底裁判：显式技能名 → 理智特判 → 意图短语；否则 none。

    每名玩家最多一条检定（技能/理智/无需）；命中即停。
    """
    checks: list[dict] = []
    taken: set[str] = set()
    for action in actions:
        uid = action.get("uid", "")
        if not uid or uid in taken:
            continue
        text = str(action.get("text", ""))
        char = characters.get(uid)
        # 第 1 层：显式技能名（含括号标注写法，如（侦查）/ (Spot Hidden)）
        if (skill_zh := _match_explicit_skill(text)):
            norm: dict[str, Any] = {"player_uid": uid, "kind": "skill",
                                    "skill": skill_zh,
                                    "target": resolve_skill_value(skill_zh, char),
                                    "reason": "显式技能名"}
        # 第 2 层：理智特判
        elif _match_sanity(text):
            norm = {"player_uid": uid, "kind": "sanity", "loss": 1,
                    "reason": "直视不可名状之物"}
        # 第 3 层：意图短语 → 技能
        elif (intent := _match_intent(text)):
            zh_name, reason = intent
            norm = {"player_uid": uid, "kind": "skill", "skill": zh_name,
                    "target": resolve_skill_value(zh_name, char),
                    "reason": reason}
        # 其余：纯叙事推进
        else:
            norm = {"player_uid": uid, "kind": "none", "reason": "纯叙事推进"}
        checks.append(norm)
        taken.add(uid)
    return {"dice_checks": checks, "private_notes": "", "source": "fallback"}
