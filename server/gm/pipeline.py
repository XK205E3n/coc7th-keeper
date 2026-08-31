# -*- coding: utf-8 -*-
"""守密人回合管线（M2 闭环）：行动 → 裁判 → 引擎掷骰(固定) → 叙事 → 状态落库。

`run_round(game_key, llm=None)`：
  1. 收集本轮全部行动（store.latest_actions，AI 只读最后一次版本）
  2. adjudicate → dice_checks（LLM 或关键词兜底）
  3. 引擎掷骰（skill_check / sanity_check_roll / luck_check），**结果固定**
  4. narrate → narrative + state_changes（LLM 或兜底；禁用词过滤）
  5. state_apply 校验落库（五类白名单）
  6. 持久化：dice_log / 叙事流 messages / kp_notes(private_notes) / state_changes
  7. 返回本轮事件数据（由 API/roundman 广播；private_notes 与 kp 数据绝不上报玩家）

M4 单人自动推进将调用本函数（一个活跃玩家提交即推进）。
"""
from __future__ import annotations

import logging
from typing import Any

from server import modules, roundman, state_apply, store
from server.engine import luck_check, sanity_check_roll, skill_check
from server.gm.adjudicate import adjudicate
from server.gm.narrate import narrate

logger = logging.getLogger("gm.pipeline")


async def roll_check(check: dict, characters: dict[str, dict]) -> dict | None:
    """按 dice_check 调引擎掷骰（固定骰果）。kind=none 返回 None。"""
    uid = check.get("player_uid")
    kind = check.get("kind")
    char = characters.get(uid) or {}
    if kind == "skill":
        return skill_check(check.get("skill", "侦查"),
                           int(check.get("target", 25)), by=uid,
                           why=check.get("reason", ""))
    if kind == "sanity":
        state = char.get("state") or {}
        san = state.get("san")
        if san is None:
            d = char.get("data") or char
            derived = d.get("derived", {}) or {}
            san = derived.get("SAN", 50)
        return sanity_check_roll(int(san), int(check.get("loss", 1)),
                                 by=uid, why=check.get("reason", ""))
    if kind == "luck":
        d = char.get("data") or char
        luk = (d.get("attributes") or {}).get("LUK", 50)
        return luck_check(int(luk), by=uid, why=check.get("reason", ""))
    return None


def _log_tail(st: "store.GameStore", game_key: str) -> list[str]:
    msgs = st.list_messages(game_key, limit=40)
    return [str(m.get("payload", {}).get("text", "")) for m in msgs
            if m.get("payload", {}).get("text")]


async def run_round(game_key: str, *, llm: Any = None,
                    round_no: int | None = None) -> dict:
    """执行一轮守密人管线。返回 {round, dice_checks, dice_results, narrative,
    applied, rejected, perceptions, scene, handouts, sources}。"""
    st = store.get_store(game_key)
    game = st.get_game(game_key)
    if game is None:
        raise KeyError(f"房间 {game_key} 不存在")
    if round_no is None:
        round_no = game["round"]

    # 1) 本轮行动（最后一次版本）
    actions_raw = st.latest_actions(game_key, round_no)
    players = {p["uid"]: p for p in st.list_players(game_key)}
    actions = [{"uid": uid, "name": players[uid]["name"],
                "text": info["text"], "action_version": info["action_version"]}
               for uid, info in sorted(actions_raw.items())]

    # 角色卡
    characters: dict[str, dict] = {}
    for c in st.list_characters(game_key):
        characters[c["uid"]] = {"data": c["data"], "name": c["name"]}

    # 场景与上下文
    module_id = game.get("module_id")
    scene = modules.get_scene(module_id, game.get("current_scene")) \
        if module_id and game.get("current_scene") else None
    kp_tail = [n["text"] for n in st.list_kp_notes(game_key, limit=10)]
    log_tail = _log_tail(st, game_key)

    # 2) 裁判
    adj = await adjudicate(actions=actions, characters=characters, scene=scene,
                           kp_notes_tail=kp_tail, log_tail=log_tail,
                           round_no=round_no, llm=llm)

    # 3) 引擎掷骰（固定）
    dice_results: list[dict] = []
    for check in adj["dice_checks"]:
        res = await roll_check(check, characters)
        if res is not None:
            st.add_dice_log(game_key, kind=res.get("kind", "roll"),
                            payload={**res, "round": round_no,
                                     "check": {k: v for k, v in check.items()
                                               if k != "player_uid"}},
                            round_no=round_no)
            dice_results.append({**res, "player_uid": check["player_uid"],
                                 "check": check})

    # 4) 叙事
    nar = await narrate(actions=actions, characters=characters,
                        dice_results=dice_results, scene=scene,
                        round_no=round_no, llm=llm)

    # 5) 状态落库
    outcome = state_apply.apply_state_changes(
        st, game_key, round_no, nar["state_changes"], module_id=module_id)

    # 6) 持久化叙事流（dice 卡片 + 叙事）
    for res in dice_results:
        st.add_message(game_key, round_no, "dice", {
            "player_uid": res.get("player_uid"),
            "expr": res.get("expr"), "skill": res.get("skill"),
            "skill_value": res.get("skill_value"), "roll": res.get("roll"),
            "result": res.get("result"), "result_cn": res.get("result_cn"),
        })
    st.add_message(game_key, round_no, "narration", {"text": nar["narrative"]})

    # 守密人笔记（只进 KP 上下文，绝不上报）
    if adj.get("private_notes"):
        st.add_kp_note(game_key, adj["private_notes"], round_no)

    scene_out = outcome.get("scene")
    return {
        "round": round_no,
        "dice_checks": adj["dice_checks"],
        "dice_results": dice_results,
        "narrative": nar["narrative"],
        "applied": outcome["applied"],
        "rejected": outcome["rejected"],
        "perceptions": outcome["perceptions"],
        "scene": scene_out,
        "handouts": outcome["handouts"],
        "kp_notes": adj.get("private_notes", ""),     # 仅供调用方内部；禁止广播
        "sources": {"adjudicate": adj["source"], "narrate": nar["source"]},
    }
