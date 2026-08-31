# -*- coding: utf-8 -*-
"""守密人提示词加载与上下文拼装（M2.1）。

- `system_prompt()`：加载编译产物 `prompts/gm_system.md`（UTF-8，进程内缓存）
- `stage_user_prompt(...)`：把 行动 / 场景 / 角色卡 / kp-notes 尾 / 叙事流尾
  拼装为裁判或叙事阶段的标准 user 指令（JSON 结构，便于 LLM 照做）
"""
from __future__ import annotations

import json
from typing import Any

from server import config

_PROMPT_PATH = config.PROJECT_ROOT / "prompts" / "gm_system.md"
_cached: str | None = None


def system_prompt() -> str:
    """返回守密人系统提示词（编译产物）。"""
    global _cached
    if _cached is None:
        _cached = _PROMPT_PATH.read_text(encoding="utf-8")
    return _cached


def _compact_actions(actions: list[dict]) -> list[dict]:
    return [{"player": a.get("name") or a.get("uid"),
             "uid": a["uid"], "text": a["text"]} for a in actions]


def _compact_chars(chars: dict[str, dict]) -> dict[str, dict]:
    out = {}
    for uid, char in chars.items():
        d = char.get("data") or char
        out[uid] = {
            "name": d.get("name"),
            "occupation": d.get("meta", {}).get("occupation"),
            "attributes": d.get("attributes", {}),
            "derived": d.get("derived", {}),
            "skills": d.get("skills", {}),
            "state": d.get("state", {}),
            "inventory": d.get("inventory", []),
        }
    return out


def stage_user_prompt(stage: str, *, round_no: int,
                      actions: list[dict],
                      characters: dict[str, dict],
                      scene: dict | None = None,
                      kp_notes_tail: list[str] | None = None,
                      log_tail: list[str] | None = None,
                      dice_results: list[dict] | None = None) -> str:
    """拼装裁判(adjudicate)/叙事(narrate)阶段的 user 消息。

    `characters`: {uid: 角色卡 dict}（内含 data 或直接为卡）
    `scene`: scenes.json 中的场景 dict 或 None
    """
    sections: list[str] = [f"## 当前状况（第 {round_no} 轮）"]
    if scene:
        sections.append("### 当前场景\n" + json.dumps(scene, ensure_ascii=False, indent=2))
    sections.append("### 本轮行动\n" + json.dumps(
        _compact_actions(actions), ensure_ascii=False, indent=2))
    sections.append("### 相关角色卡\n" + json.dumps(
        _compact_chars(characters), ensure_ascii=False, indent=2))
    if kp_notes_tail:
        sections.append("### 守密人笔记（只进你上下文，绝不进玩家视图）\n"
                        + "\n".join(kp_notes_tail[-8:]))
    if log_tail:
        sections.append("### 叙事流（玩家可见内容尾部）\n"
                        + "\n".join(log_tail[-6:]))
    if stage == "narrate":
        sections.append("### 服务端固定骰果（不可更改）\n"
                        + json.dumps(dice_results or [], ensure_ascii=False, indent=2))
        sections.append("请输出叙事阶段 JSON：`{\"narrative\": \"...\", \"state_changes\": [...]}`"
                        "（state_changes 类型仅限 hp/san/item/clue/scene；失败检定遵守措辞铁律）。")
    else:
        sections.append("请输出裁判阶段 JSON：`{\"dice_checks\": [{\"player_uid\", \"kind\":"
                        " \"skill|sanity|luck|none\", ...}], \"private_notes\": \"...\"}`"
                        "（kind 白名单：skill/sanity/luck/none；技能 target 取自角色卡 §4.4 默认值）。")
    return "\n\n".join(sections)


def messages_for(stage: str, *, round_no: int, actions: list[dict],
                 characters: dict[str, dict], scene: dict | None = None,
                 kp_notes_tail: list[str] | None = None,
                 log_tail: list[str] | None = None,
                 dice_results: list[dict] | None = None) -> list[dict]:
    """返回 [system, user] 两条消息。"""
    return [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": stage_user_prompt(
            stage, round_no=round_no, actions=actions, characters=characters,
            scene=scene, kp_notes_tail=kp_notes_tail, log_tail=log_tail,
            dice_results=dice_results)},
    ]


# 测试/开发检查用：提示词是否含飞书/群聊残留
LARK_RESIDUE = ("飞书", "群聊", "lark", "Lark", "plan-gate", "频道", "机器人",
                "/coc", "p2p", "group", "topic", "bridge")
