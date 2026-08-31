# -*- coding: utf-8 -*-
"""状态应用器（M2.5）：五类状态变动白名单校验落库 + 禁用词过滤。

类型白名单：hp / san / item / clue / scene。
原则（与 DiceFrame 一致）：叙事可以自由，状态必须可信——
- 越界/非法值（HP 越界、物品余额不足、重复线索、场景不存在）一律拒绝；
- 落库以校验后的值为准，叙事与状态冲突以 state_changes 为准。

禁用词过滤（失败措辞铁律）："没有异常 / 其实你漏掉" 等 → 改写为 "没能看出更多端倪"。

角色卡状态段（coc7-character/v1 的附加可变字段，state_apply 维护）：
  "state": {"hp", "max_hp", "san", "max_san", "clues": [], "conditions": [], "gold": 0}
"""
from __future__ import annotations

import logging
import re
from typing import Any

from server import modules, store
from server.engine import major_wound_roll

logger = logging.getLogger("state_apply")

STATE_KINDS = ("hp", "san", "item", "clue", "scene")

# 失败措辞铁律禁用词（§2.3）：命中即改写句子
FORBIDDEN_PATTERNS = (
    "没有异常", "没有发现异常", "并没有异常", "并无异常", "没有线索",
    "并不存在异常", "不存在异常", "其实你漏掉", "其实你没发现",
    "你漏掉了", "你其实错过了", "你错过了关键", "什么都没有", "一无所获",
)
_FORBIDDEN_RE = re.compile(
    r"[^。！？\n]*?(?:" + "|".join(map(re.escape, FORBIDDEN_PATTERNS)) + r")[^。！？\n]*[。！？]?")


def filter_forbidden(text: str) -> str:
    """把命中禁用词的句子改写为「没能看出更多端倪」。"""
    if not text:
        return text
    return _FORBIDDEN_RE.sub("没能看出更多端倪。", text)


def ensure_char_state(data: dict) -> dict:
    """为角色卡补齐可变状态段（幂等）。"""
    state = data.setdefault("state", {})
    derived = data.get("derived", {}) or {}
    sanity = data.get("sanity", {}) or {}
    max_hp = derived.get("HP") or 10
    max_san = sanity.get("max") or sanity.get("current") or derived.get("SAN") or 50
    state.setdefault("max_hp", max_hp)
    state.setdefault("hp", min(state.get("hp", max_hp), max_hp))
    state.setdefault("max_san", max_san)
    state.setdefault("san", min(state.get("san", max_san), max_san))
    state.setdefault("clues", [])
    state.setdefault("conditions", [])
    state.setdefault("gold", 0)
    return data


def _load_char(st: "store.GameStore", game_key: str, uid: str) -> dict | None:
    row = st.get_character(game_key, uid)
    return row["data"] if row else None


def _save_char(st: "store.GameStore", game_key: str, uid: str, data: dict) -> None:
    st.set_character(game_key, uid, data.get("name", uid), data)


def apply_state_changes(st: "store.GameStore", game_key: str, round_no: int,
                        changes: list[dict], module_id: str | None = None) -> dict:
    """校验并落库五类状态变动。

    返回：{"applied": [...], "rejected": [...], "perceptions": [...],
           "scene": scene_dict | None, "handouts": [...]}
    """
    applied: list[dict] = []
    rejected: list[dict] = []
    perceptions: list[dict] = []
    scene_obj: dict | None = None
    handouts: list[str] = []

    # 按 uid 批量加载角色卡（每玩家一次读写）
    char_cache: dict[str, dict | None] = {}
    for c in changes:
        uid = c.get("player_uid")
        if uid and uid not in char_cache:
            char_cache[uid] = _load_char(st, game_key, uid)

    for c in changes:
        ctype = c.get("type")
        uid = c.get("player_uid")
        payload = {"type": ctype, "player_uid": uid, **c}
        try:
            if ctype == "hp":
                _apply_hp(char_cache, uid, c, payload, applied, rejected)
            elif ctype == "san":
                _apply_san(char_cache, uid, c, payload, applied, rejected)
            elif ctype == "item":
                _apply_item(char_cache, uid, c, payload, applied, rejected)
            elif ctype == "clue":
                _apply_clue(st, game_key, char_cache, uid, c, payload,
                            applied, rejected, perceptions)
            elif ctype == "scene":
                scene_obj = _apply_scene(st, game_key, module_id, c,
                                         applied, rejected)
                if scene_obj:
                    handouts = list(scene_obj.get("handouts") or [])
            else:
                rejected.append({**payload, "reason": "未知的状态变动类型"})
        except Exception as e:  # noqa: BLE001
            logger.exception("state_change 应用异常")
            rejected.append({**payload, "reason": f"应用失败: {e}"})

    # 写回角色卡
    for uid, data in char_cache.items():
        if data is not None:
            ensure_char_state(data)
            _save_char(st, game_key, uid, data)

    # 落库审计
    for item in applied:
        try:
            st.add_state_change(game_key, round_no, item["type"],
                                item.get("player_uid"),
                                {k: v for k, v in item.items() if k != "type"})
        except Exception:  # noqa: BLE001
            logger.exception("state_change 审计落库失败")
    # 私密感知落库（只对目标玩家可见）
    for perc in perceptions:
        try:
            st.add_perception(game_key, round_no, perc["to_uid"],
                              perc["text"], perc.get("clue_id"))
        except Exception:  # noqa: BLE001
            logger.exception("perception 落库失败")
    return {"applied": applied, "rejected": rejected,
            "perceptions": perceptions, "scene": scene_obj, "handouts": handouts}


# ---------------- 五类校验 ----------------

def _apply_hp(char_cache, uid, c, payload, applied, rejected) -> None:
    data = char_cache.get(uid)
    if data is None:
        rejected.append({**payload, "reason": "玩家没有角色卡"})
        return
    ensure_char_state(data)
    st = data["state"]
    delta = int(c.get("delta", 0))
    new_hp = st["hp"] + delta
    if new_hp < 0 or new_hp > st["max_hp"]:
        rejected.append({**payload, "reason": f"HP 越界（{st['hp']} {delta:+d} → {new_hp}，"
                                              f"上限 {st['max_hp']}）"})
        return
    st["hp"] = new_hp
    out = {**payload, "hp": new_hp, "max_hp": st["max_hp"]}
    if new_hp <= 0:
        mw = major_wound_roll(new_hp)          # HP 归 0 → 重伤表
        st["conditions"].append(f"重伤:{mw['effect']}")
        out["major_wound"] = mw
    applied.append(out)


def _apply_san(char_cache, uid, c, payload, applied, rejected) -> None:
    data = char_cache.get(uid)
    if data is None:
        rejected.append({**payload, "reason": "玩家没有角色卡"})
        return
    ensure_char_state(data)
    st = data["state"]
    delta = int(c.get("delta", 0))
    new_san = st["san"] + delta
    if new_san < 0 or new_san > st["max_san"]:
        rejected.append({**payload, "reason": f"SAN 越界（{st['san']} {delta:+d} → {new_san}，"
                                              f"上限 {st['max_san']}）"})
        return
    st["san"] = new_san
    if delta < 0:
        history = data.setdefault("sanity", {}).setdefault("history", [])
        history.append({"ts": None, "loss": -delta, "reason": c.get("reason", ""),
                        "insane_kind": None})
        if new_san <= 0:                        # SAN 归 0 → 永久疯狂
            st["conditions"].append("永久疯狂")
            out = {**payload, "san": new_san, "permanent_insanity": True}
            applied.append(out)
            return
    applied.append({**payload, "san": new_san, "max_san": st["max_san"]})


def _apply_item(char_cache, uid, c, payload, applied, rejected) -> None:
    data = char_cache.get(uid)
    if data is None:
        rejected.append({**payload, "reason": "玩家没有角色卡"})
        return
    ensure_char_state(data)
    inv = data.setdefault("inventory", [])
    action = c.get("action", "gain")
    item = c.get("item", "")
    if action == "gain":
        if item in inv:
            rejected.append({**payload, "reason": "背包中已有该物品"})
            return
        inv.append(item)
    else:                                        # lose / consume
        if item not in inv:
            rejected.append({**payload, "reason": f"物品不存在或余额不足: {item}"})
            return
        inv.remove(item)
    applied.append({**payload, "inventory": list(inv)})


def _apply_clue(st, game_key, char_cache, uid, c, payload, applied, rejected,
                perceptions) -> None:
    """线索：加到目标玩家的 state.clues（去重）、生成私密感知，并更新线索台账状态。"""
    data = char_cache.get(uid)
    if data is None:
        rejected.append({**payload, "reason": "玩家没有角色卡"})
        return
    ensure_char_state(data)
    clues = data["state"]["clues"]
    clue_id = c.get("clue_id")
    text = c.get("text", "")
    if clue_id and clue_id in clues:
        rejected.append({**payload, "reason": f"已持有该线索 {clue_id}"})
        return
    if clue_id:
        clues.append(clue_id)
        # M7 建议：线索台账副本状态更新（管理员可查：谁/何时获得）
        try:
            st.unlock_clue(game_key, clue_id, uid)
        except Exception:  # noqa: BLE001
            logger.exception("线索台账解锁失败")
    applied.append({**payload, "clues": list(clues)})
    # 私密感知由管线负责落库（需要 game_key/round_no），这里只登记返回。
    if text:
        perceptions.append({"to_uid": uid, "text": text, "clue_id": clue_id})


def _apply_scene(st, game_key, module_id, c, applied, rejected) -> dict | None:
    ref = c.get("text", "")
    if not module_id or not ref:
        rejected.append({**c, "reason": "场景切换缺少模组或场景引用"})
        return None
    scene = modules.find_scene(module_id, ref)
    if scene is None:
        rejected.append({**c, "reason": f"场景不存在: {ref!r}"})
        return None
    st.update_game(game_key, current_scene=scene["id"])
    applied.append({"type": "scene", "scene_id": scene["id"], "name": scene.get("name")})
    return scene
