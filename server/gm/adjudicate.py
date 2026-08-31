# -*- coding: utf-8 -*-
"""裁判阶段（M2.3）：本轮全部行动 + 场景 + kp-notes → dice_checks JSON。

- LLM 在线：要求 provider 输出 `{"dice_checks": [...], "private_notes": "..."}`，
  服务端解析并做 **kind 白名单 + 每玩家一条 + target 从角色卡补齐** 的规范化。
- LLM 不可用（断网/无 key/解析失败）：走 `fallback_adjudicate()` 关键词兜底，
  保证游戏不中断（验收：LLM 断网时状态应用仍完成）。
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

_KEYWORD_RULES: list[tuple[str, str, str]] = [
    # (正则, 技能中文名, 说明) —— 命中第一个即停
    (r"直视|目睹|看到|见到|注视|直面|盯着", "sanity", "直视不可名状之物"),
    (r"理智|san\b", "sanity", "理智冲击"),
    (r"侦查|检查|查看|搜索|搜查|翻找|打量|观察|搜寻|四处看", "侦查", "调查/检索"),
    (r"倾听|听|动静|脚步声|门后|隔壁", "倾听", "听觉调查"),
    (r"图书馆|查资料|查阅|翻书|资料|文献|档案", "图书馆使用", "文献调查"),
    (r"心理学|察言观色|试探|识破", "心理学", "观察意图"),
    (r"魅惑|搭讪|讨好", "魅惑", "社交"),
    (r"说服|劝|谈判|说服", "说服", "社交"),
    (r"套话|套问|诱导", "套话", "社交"),
    (r"威胁|恐吓|威吓", "威胁", "社交"),
    (r"攀爬|爬上|爬下|翻墙|爬", "攀爬", "体能"),
    (r"潜行|潜入|溜进|偷偷|悄悄", "潜行", "潜行"),
    (r"枪|射击|开枪|开枪|手枪|步枪", "手枪", "射击"),
    (r"闪避|躲避|躲开|闪开", "闪避", "闪避"),
    (r"格斗|拳|搏斗|殴打|攻击|打斗|战斗", "格斗（拳）", "近战"),
    (r"急救|包扎|止血|抢救|医疗|医治", "急救", "急救"),
]


def fallback_adjudicate(*, actions: list[dict],
                        characters: dict[str, dict]) -> dict:
    """关键词兜底裁判：每名玩家最多一条检定（技能/理智/无需）。

    命中顺序：直视/理智 > 调查类技能 > 社交 > 体能 > 战斗 > 急救；否则 none。
    """
    checks: list[dict] = []
    taken: set[str] = set()
    for action in actions:
        uid = action.get("uid", "")
        if not uid or uid in taken:
            continue
        text = str(action.get("text", ""))
        norm: dict[str, Any] = {"player_uid": uid, "kind": "none", "reason": "纯叙事推进"}
        for pattern, zh_name, note in _KEYWORD_RULES:
            if re.search(pattern, text):
                if zh_name == "sanity":
                    norm = {"player_uid": uid, "kind": "sanity", "loss": 1,
                            "reason": note}
                else:
                    char = characters.get(uid)
                    norm = {"player_uid": uid, "kind": "skill",
                            "skill": zh_name,
                            "target": resolve_skill_value(zh_name, char),
                            "reason": note}
                break
        checks.append(norm)
        taken.add(uid)
    return {"dice_checks": checks, "private_notes": "", "source": "fallback"}
