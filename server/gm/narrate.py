# -*- coding: utf-8 -*-
"""叙事阶段（M2.4）：固定骰果 + 行动 + 场景 → narrative + state_changes JSON。

- LLM 在线：provider 输出 `{"narrative": "...", "state_changes": [...]}`；
  服务端做 **状态类型白名单** 与 **禁用词过滤**（失败措辞铁律）。
- LLM 不可用：`fallback_narrate()` 按骰果档位生成保守叙事与 SAN/HP 状态变动。
- 骰果已由引擎固定，叙事不得改写成与骰果相反的结果（§1.9 / §8.1）。
"""
from __future__ import annotations

import logging
from typing import Any

from server import state_apply
from server.gm.adjudicate import _extract_json

logger = logging.getLogger("gm.narrate")

STATE_KINDS = ("hp", "san", "item", "clue", "scene")

_RESULT_CN = {
    "critical": "大成功", "extreme": "极难成功", "hard": "困难成功",
    "regular": "成功", "failure": "失败", "fumble": "大失败",
}


def _norm_state_changes(changes: list[dict], characters: dict[str, dict]) -> list[dict]:
    """规范化 + 白名单过滤 state_changes。"""
    out: list[dict] = []
    for c in changes or []:
        if not isinstance(c, dict):
            continue
        ctype = str(c.get("type", "")).strip().lower()
        uid = str(c.get("player_uid", "") or "").strip()
        if ctype not in STATE_KINDS:
            logger.warning("丢弃非法 state_change 类型: %r", c.get("type"))
            continue
        item: dict[str, Any] = {"type": ctype}
        if uid:
            item["player_uid"] = uid
        if ctype in ("hp", "san"):
            delta = c.get("delta")
            if isinstance(delta, (int, float)) and delta != 0:
                item["delta"] = int(delta)
            else:
                continue                              # 空变动直接忽略
        elif ctype == "item":
            action = str(c.get("action", "gain")).strip().lower()
            name = str(c.get("item", "")).strip()
            if not name:
                continue
            item["action"] = action if action in ("gain", "lose", "consume") else "gain"
            item["item"] = name
        elif ctype == "clue":
            cid = str(c.get("clue_id", "")).strip()
            text = str(c.get("text", "")).strip()
            if cid:
                item["clue_id"] = cid
            if text:
                item["text"] = text
        elif ctype == "scene":
            text = str(c.get("text", "")).strip()
            if text:
                item["text"] = text
        out.append(item)
    return out


async def narrate(*, actions: list[dict], characters: dict[str, dict],
                  dice_results: list[dict], scene: dict | None = None,
                  round_no: int = 0, llm: Any = None) -> dict:
    """叙事：骰果 → narrative + state_changes。返回 {"narrative","state_changes","source"}。"""
    if llm is None or not getattr(llm, "available", False):
        return fallback_narrate(actions=actions, dice_results=dice_results,
                                scene=scene)

    from server.gm import prompts as P
    messages = P.messages_for(
        "narrate", round_no=round_no, actions=actions, characters=characters,
        scene=scene, dice_results=dice_results)
    raw = await llm.chat(messages, json_mode=True)
    data = _extract_json(raw) if raw else None
    if data is None:
        logger.warning("叙事 JSON 解析失败，降级兜底")
        return fallback_narrate(actions=actions, dice_results=dice_results,
                                scene=scene)

    narrative = str(data.get("narrative", "") or "").strip()
    if not narrative:
        return fallback_narrate(actions=actions, dice_results=dice_results,
                                scene=scene)
    narrative = state_apply.filter_forbidden(narrative)     # 失败措辞铁律
    changes = _norm_state_changes(data.get("state_changes", []), characters)
    return {"narrative": narrative, "state_changes": changes, "source": "llm"}


# ---------------- 兜底叙事（LLM 不可用/解析失败） ----------------

def fallback_narrate(*, actions: list[dict], dice_results: list[dict],
                     scene: dict | None = None) -> dict:
    """按固定骰果生成保守叙事；SAN/HP 变动由骰果直接推出并落 state_changes。"""
    lines: list[str] = []
    changes: list[dict] = []
    by_uid: dict[str, str] = {a.get("uid", ""): a.get("text", "") for a in actions}

    if scene:
        lines.append(f"（场景 {scene.get('name', '')}）")

    for res in dice_results:
        uid = res.get("player_uid", "")
        action_text = by_uid.get(uid, "你采取了行动")
        kind = res.get("kind")
        if kind == "san_check":
            success = res.get("success")
            if success:
                lines.append(f"{action_text}——你稳住了心神，没有失去理智。")
            else:
                loss = res.get("actual_loss", 0)
                lines.append(f"{action_text}——一阵寒意攫住你，你失去了 {loss} 点理智。")
                if loss:
                    changes.append({"type": "san", "player_uid": uid, "delta": -loss})
        else:
            result = res.get("result")
            result_cn = _RESULT_CN.get(str(result), str(result))
            if result in ("failure", "fumble"):
                lines.append(f"{action_text}——你没能看出更多端倪。")      # 措辞铁律
            else:
                lines.append(f"{action_text}——检定{result_cn}。")
        # hp 变动（combat 结果由引擎 attack 产生时）
        if res.get("hit"):
            dmg = res.get("damage") or 0
            changes.append({"type": "hp", "player_uid": uid, "delta": -dmg})

    if not lines:
        fallback_text = "周围一片寂静，你继续观察着周围的一切。"
        for action in actions:
            if action.get("text"):
                fallback_text = f"{action['text']}——你环顾四周，一切平静如常。"
                break
        lines.append(fallback_text)
    narrative = "\n".join(lines)
    return {"narrative": state_apply.filter_forbidden(narrative),
            "state_changes": _norm_state_changes(changes, {}),
            "source": "fallback"}
