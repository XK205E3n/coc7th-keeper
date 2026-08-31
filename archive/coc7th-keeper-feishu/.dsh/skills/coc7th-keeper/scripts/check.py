# -*- coding: utf-8 -*-
"""CoC7th 技能/属性/对抗检定 CLI。

判定档位（与 CoC7th 规则一致）：
  1                 → 大成功（Critical / Extreme）
  <= skill/5        → 极难成功
  <= skill/2        → 困难成功
  <= skill          → 成功
  < 100             → 失败
  100               → 大失败（Fumble）

支持：
  1) 单项技能 check <skill_name> <skill_value> [difficulty]
  2) 属性对抗 opposed <A_skill> <A_value> <B_value>  （B 固定技能值，A 投骰对照 B 技能值）
  3) 联合检定 combined <skill_value>
  4) 幸运检定 luck <current_luck>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 用 UTF-8 直接写 stdout，绕过 Windows GBK 控制台编码问题
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Py 3.7+
except Exception:  # pragma: no cover
    pass

sys.path.insert(0, str(Path(__file__).parent))
from _common import append_dice_log, out, secure_d100, room_dir  # noqa: E402


def judge(value: int, skill: int) -> str:
    if value <= 0:
        return "INVALID"
    if value == 1:
        return "critical"     # 大成功
    if value <= max(1, skill // 5):
        return "extreme"      # 极难
    if value <= max(1, skill // 2):
        return "hard"         # 困难
    if value <= skill:
        return "regular"      # 成功
    if value < 100:
        return "failure"      # 失败
    return "fumble"           # 大失败


def check_skill(skill_name: str, skill_value: int, by: str = "kp",
                why: str = "", difficulty: str = "regular",
                room: str | None = None) -> dict:
    if skill_value < 1 or skill_value > 100:
        raise ValueError(f"技能值 {skill_value} 非法，应在 1-100")

    roll = secure_d100()
    result = judge(roll, skill_value)
    payload = {
        "kind": "check",
        "by": by,
        "why": why,
        "skill": skill_name,
        "skill_value": skill_value,
        "difficulty": difficulty,
        "roll": roll,
        "result": result,
    }
    if room is not None:
        rd = room_dir(room); rd.mkdir(parents=True, exist_ok=True)
        append_dice_log(rd, payload)
    payload["result_cn"] = {
        "critical": "大成功", "extreme": "极难成功",
        "hard": "困难成功", "regular": "成功",
        "failure": "失败", "fumble": "大失败",
    }[result]
    return payload


def check_luck(current_luck: int, by: str = "kp", why: str = "",
               room: str | None = None) -> dict:
    """幸运检定：直接以当前 Luck 值为目标技能。"""
    roll = secure_d100()
    result = judge(roll, current_luck)
    payload = {
        "kind": "luck",
        "by": by,
        "why": why or "每日首次幸运",
        "skill": "Luck",
        "skill_value": current_luck,
        "difficulty": "regular",
        "roll": roll,
        "result": result,
    }
    if room is not None:
        rd = room_dir(room); rd.mkdir(parents=True, exist_ok=True)
        append_dice_log(rd, payload)
    payload["result_cn"] = {
        "critical": "大成功", "extreme": "极难成功",
        "hard": "困难成功", "regular": "成功",
        "failure": "失败", "fumble": "大失败",
    }[result]
    return payload


def check_opposed(skill_name: str, attacker_value: int,
                  defender_value: int, by: str = "kp", why: str = "",
                  room: str | None = None) -> dict:
    """对抗检定：双方各掷一次，谁成功档更高谁赢。"""
    a_roll = secure_d100()
    b_roll = secure_d100()
    a_judge = judge(a_roll, attacker_value)
    b_judge = judge(b_roll, defender_value)
    order = {"critical":5,"extreme":4,"hard":3,"regular":2,"failure":1,"fumble":0}
    if order[a_judge] > order[b_judge]:
        winner = "attacker"
    elif order[b_judge] > order[a_judge]:
        winner = "defender"
    else:
        winner = "tie"
    payload = {
        "kind": "opposed",
        "by": by,
        "why": why or f"对抗:{skill_name}",
        "skill": skill_name,
        "attacker": {"skill": attacker_value, "roll": a_roll, "result": a_judge},
        "defender": {"skill": defender_value, "roll": b_roll, "result": b_judge},
        "winner": winner,
    }
    if room is not None:
        rd = room_dir(room); rd.mkdir(parents=True, exist_ok=True)
        append_dice_log(rd, payload)
    return payload


def check_combined(skill_value: int, by: str = "kp", why: str = "",
                   room: str | None = None) -> dict:
    """联合检定：每有一名协助者，成功线提升 +20，封顶 +80（≥ skill 时等同 hard）。"""
    roll = secure_d100()
    payload = {
        "kind": "combined",
        "by": by,
        "why": why or "联合检定",
        "skill_value": skill_value,
        "roll": roll,
        "result": judge(roll, skill_value),
    }
    if room is not None:
        rd = room_dir(room); rd.mkdir(parents=True, exist_ok=True)
        append_dice_log(rd, payload)
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="CoC7th 检定")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("skill", help="单项技能检定")
    p1.add_argument("skill_name"); p1.add_argument("skill_value", type=int)
    p1.add_argument("--by", default="kp"); p1.add_argument("--why", default="")
    p1.add_argument("--room", default=None)

    p2 = sub.add_parser("luck", help="幸运检定")
    p2.add_argument("current_luck", type=int)
    p2.add_argument("--by", default="kp"); p2.add_argument("--why", default="")
    p2.add_argument("--room", default=None)

    p3 = sub.add_parser("opposed", help="对抗检定")
    p3.add_argument("skill_name")
    p3.add_argument("attacker_value", type=int)
    p3.add_argument("defender_value", type=int)
    p3.add_argument("--by", default="kp"); p3.add_argument("--why", default="")
    p3.add_argument("--room", default=None)

    p4 = sub.add_parser("combined", help="联合检定（占位实现）")
    p4.add_argument("skill_value", type=int)
    p4.add_argument("--by", default="kp"); p4.add_argument("--why", default="")
    p4.add_argument("--room", default=None)

    args = ap.parse_args()
    try:
        if args.cmd == "skill":
            # 修复派发错位（v0.1.x 遗留）：按关键字传参，room 真正路由到房间
            # （写入该房间 dice.log），difficulty 保持普通档默认值，
            # 避免把 args.room 误填入 difficulty 槽导致 room 恒为 None。
            payload = check_skill(
                args.skill_name, args.skill_value,
                by=args.by, why=args.why,
                difficulty="regular", room=args.room,
            )
        elif args.cmd == "luck":
            payload = check_luck(args.current_luck, args.by, args.why, args.room)
        elif args.cmd == "opposed":
            payload = check_opposed(args.skill_name, args.attacker_value,
                                    args.defender_value, args.by, args.why, args.room)
        else:
            payload = check_combined(args.skill_value, args.by, args.why, args.room)
    except ValueError as e:
        print("ERROR:", e, file=sys.stderr); return 1

    out({"ok": True, **payload})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
