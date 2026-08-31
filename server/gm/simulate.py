# -*- coding: utf-8 -*-
"""守密人管线命令行模拟（M2 验收：CLI 模拟 3 类行动——技能检定/理智检定/无需检定）。

用法（在仓库根目录）：
    .venv/Scripts/python -m server.gm.simulate --mode skill   [--action "我仔细检查柜子（侦查）" --player 爱丽丝]
    .venv/Scripts/python -m server.gm.simulate --mode sanity  [--action "我直视那团蠕动的东西"]
    .venv/Scripts/python -m server.gm.simulate --mode none    [--action "我走到窗边看夜色"]

默认 LLM 关闭（离线兜底，确定性强）；--mode 控制兜底裁判的判定方向。
"""
from __future__ import annotations

import argparse
import asyncio
import json

from server import roundman, store
from server.engine import build_character
from server.gm.pipeline import run_round

DEFAULT_ACTIONS = {
    "skill": "我仔细检查柜子，寻找线索（侦查）",
    "sanity": "我直视那团缓缓蠕动的东西",
    "none": "我沿着走廊慢慢走着，没有说话",
}


async def main() -> int:
    ap = argparse.ArgumentParser(description="守密人管线 CLI 模拟（M2 验收）")
    ap.add_argument("--mode", choices=("skill", "sanity", "none"), default="skill",
                    help="兜底裁判方向：技能检定 / 理智检定 / 无需检定")
    ap.add_argument("--action", default=None, help="行动文本（默认按 mode）")
    ap.add_argument("--player", default="爱丽丝", help="模拟玩家名")
    args = ap.parse_args()

    created = roundman.create_game(name=f"模拟-{args.mode}", rule="coc7",
                                   module_id="the-haunting", host_name=args.player)
    key = created["game_key"]
    uid = created["host_uid"]
    char = build_character(args.player)
    st = store.get_store(key)
    st.set_character(key, uid, args.player, char)
    action_text = args.action or DEFAULT_ACTIONS[args.mode]
    st.set_action(key, uid, 0, action_text)

    result = await run_round(key, llm=None)          # LLM 关闭 → 关键词兜底

    print(json.dumps({
        "mode": args.mode,
        "action": action_text,
        "dice_checks": result["dice_checks"],
        "dice_results": [{k: v for k, v in r.items() if k not in ("check",)}
                         for r in result["dice_results"]],
        "narrative": result["narrative"],
        "state_changes_applied": result["applied"],
        "rejected": result["rejected"],
        "sources": result["sources"],
        "sim_key": key,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
