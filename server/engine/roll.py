# -*- coding: utf-8 -*-
"""通用投骰 CLI：直接显示骰子结果（不判定成败），并写审计日志。

用法：
    python roll.py 1d100
    python roll.py 2d6+3 --by alice --why "手榴弹伤害"
    python roll.py 3d6 --json
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

# 允许相对导入 _common
sys.path.insert(0, str(Path(__file__).parent))
from _common import append_dice_log, out, roll_expression, room_dir  # noqa: E402


def roll_expr(expr: str, by: str = "kp", why: str = "",
              room: str | None = None, no_log: bool = False) -> dict:
    result = roll_expression(expr)
    payload = {"kind": "roll", "by": by, "why": why, **result}
    if not no_log:
        rd = room_dir(room)
        rd.mkdir(parents=True, exist_ok=True)
        append_dice_log(rd, payload)
    return {"ok": True, **payload}


def main() -> int:
    ap = argparse.ArgumentParser(description="CoC7th 加密安全投骰")
    ap.add_argument("expr", help="骰子表达式，如 1d100 / 2d6+3 / d20")
    ap.add_argument("--by", default="kp", help="投骰人（玩家名 / kp）")
    ap.add_argument("--why", default="", help="本次投骰目的，记入审计")
    ap.add_argument("--room", default=None, help="房间 id；默认从环境变量或 'default'")
    ap.add_argument("--no-log", action="store_true", help="不写入 dice.log")
    args = ap.parse_args()

    try:
        payload = roll_expr(args.expr, args.by, args.why, args.room, args.no_log)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    out(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
