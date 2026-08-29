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


def main() -> int:
    ap = argparse.ArgumentParser(description="CoC7th 加密安全投骰")
    ap.add_argument("expr", help="骰子表达式，如 1d100 / 2d6+3 / d20")
    ap.add_argument("--by", default="kp", help="投骰人（玩家名 / kp）")
    ap.add_argument("--why", default="", help="本次投骰目的，记入审计")
    ap.add_argument("--room", default=None, help="房间 id；默认从环境变量或 'default'")
    ap.add_argument("--no-log", action="store_true", help="不写入 dice.log")
    ap.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    args = ap.parse_args()

    try:
        result = roll_expression(args.expr)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    audit_entry = {
        "kind": "roll",
        "by": args.by,
        "why": args.why,
        **result,
    }

    if not args.no_log:
        rd = room_dir(args.room)
        rd.mkdir(parents=True, exist_ok=True)
        append_dice_log(rd, audit_entry)

    payload = {"ok": True, **audit_entry}
    if args.json or True:  # 始终 JSON 输出（机器友好）
        out(payload)
    else:
        print(f"{args.expr} -> rolls={result['rolls']} total={result['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
