# -*- coding: utf-8 -*-
"""CoC7th 战斗回合机（简化核心）。

实现：
  - 先攻：每边 DEX 掷 1d100 + (1d10 ? - 等价改用：双方各掷 1d10 取 DEX/10 商)
    简化版：直接 DEX 数值 + 1d10，先攻高者先行动
  - 攻击：Brawl/Firearms 攻击检定，成功后掷伤害（1d6/1d8/1d10 + DB）
  - 闪避：Dodge 检定，成功减伤一半
  - 重伤：HP <= 0 时掷 1d10 查重伤表
  - 部位（可选）：HP roll 时掷 1d10 查表（命中部位对伤害 / 效果有修正）

调用：python combat.py <subcommand> ...
  - combat.py attack <attacker_skill> <defender_skill> <weapon_dmg_expr> <db>
  - combat.py ini <attacker_dex> <defender_dex>
  - combat.py wound <current_hp> <max_hp>   （重伤表查询）
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

# 用 UTF-8 直接写 stdout，绕过 Windows GBK 控制台编码问题
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Py 3.7+
except Exception:  # pragma: no cover
    pass

sys.path.insert(0, str(Path(__file__).parent))
from _common import append_dice_log, out, secure_d100, room_dir  # noqa: E402
from check import judge  # noqa: E402


def initiative(a_dex: int, b_dex: int) -> dict:
    a_roll = roll_die(10)
    b_roll = roll_die(10)
    a_total = a_dex + a_roll
    b_total = b_dex + b_roll
    if a_total > b_total:
        order = "attacker"
    elif b_total > a_total:
        order = "defender"
    else:
        order = "tie"
    return {"a_dex": a_dex, "b_dex": b_dex,
            "a_roll": a_roll, "b_roll": b_roll,
            "a_total": a_total, "b_total": b_total,
            "order": order}


def roll_die(faces: int) -> int:
    return secrets.randbelow(faces) + 1


def parse_dmg(expr: str) -> int:
    """伤害表达式：1d3 / 1d4 / 1d6 / 1d8 / 1d10 / 1d12 ± K
    返回投骰 + 修饰符；DB 由调用方外加。"""
    e = expr.strip().lower().replace(" ", "")
    sign = 1
    if e.startswith("-"):
        sign = -1; e = e[1:]
    elif e.startswith("+"):
        e = e[1:]
    k = 0
    if "+" in e:
        head, k_str = e.split("+", 1); k = int(k_str)
    elif "-" in e:
        head, k_str = e.split("-", 1); k = -int(k_str)
    else:
        head = e
    if "d" not in head:
        return sign * int(head) + k
    n_str, m_str = head.split("d", 1)
    n = int(n_str) if n_str else 1
    m = int(m_str)
    return sum(roll_die(m) for _ in range(n)) + k


def attack_round(attacker_skill: int, defender_skill: int,
                 weapon_dmg: str, db_str: str = "+0",
                 by: str = "kp", why: str = "",
                 room: str | None = None) -> dict:
    """一次攻击（含攻击检定、伤害、DB）。"""
    a_roll = secure_d100()
    d_roll = secure_d100()
    a_res = judge(a_roll, attacker_skill)
    d_res = judge(d_roll, defender_skill)

    # 简化规则：成功档比较
    order = {"critical":5,"extreme":4,"hard":3,"regular":2,"failure":1,"fumble":0}
    hit = order[a_res] > order[d_res]

    damage = 0
    if hit:
        damage = parse_dmg(weapon_dmg) + parse_db(db_str)

    payload = {
        "kind": "attack",
        "by": by, "why": why,
        "attacker_roll": a_roll, "attacker_skill": attacker_skill, "attacker_result": a_res,
        "defender_roll": d_roll, "defender_skill": defender_skill, "defender_result": d_res,
        "hit": hit, "weapon_dmg": weapon_dmg, "db": db_str, "damage": damage,
    }
    if room is not None:
        rd = room_dir(room); rd.mkdir(parents=True, exist_ok=True)
        append_dice_log(rd, payload)
    return payload


def parse_db(db_str: str) -> int:
    s = db_str.strip().replace(" ", "")
    if s.startswith("+"):
        s = s[1:]
    if "d" in s:
        # +1d4 / +1d6 / +2d6
        sign = 1
        if s.startswith("-"):
            sign = -1; s = s[1:]
        elif s.startswith("+"):
            s = s[1:]
        n, m = s.split("d", 1)
        return sign * sum(roll_die(int(m)) for _ in range(int(n)))
    try:
        return int(s)
    except ValueError:
        return 0


# 重伤表（CoC7th）
MAJOR_WOUND_TABLE = [
    ("1-3", "失血过多：每轮 1d3 伤害直至 0 HP 或接受 Medicine 检定止血"),
    ("4-5", "昏迷：失去意识，需同伴救援"),
    ("6-7", "重伤：失去某个肢体功能；HP 上限永久 -1d10"),
    ("8", "重伤：HP 上限永久减半（向上取整）"),
    ("9-10", "濒死：HP 归 0；下一轮若未救治则死亡"),
]


def major_wound_roll(current_hp: int) -> dict:
    """HP 跌至 <=0 时，掷 1d10 查重伤表。"""
    r = roll_die(10)
    for range_str, text in MAJOR_WOUND_TABLE:
        if "-" in range_str:
            lo, hi = map(int, range_str.split("-", 1))
            if lo <= r <= hi:
                return {"roll": r, "effect": text, "current_hp": current_hp}
        elif int(range_str) == r:
            return {"roll": r, "effect": text, "current_hp": current_hp}
    return {"roll": r, "effect": "(未命中)", "current_hp": current_hp}


def main() -> int:
    ap = argparse.ArgumentParser(description="CoC7th 战斗")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("ini", help="先攻判定")
    p1.add_argument("attacker_dex", type=int)
    p1.add_argument("defender_dex", type=int)

    p2 = sub.add_parser("attack", help="单次攻击")
    p2.add_argument("attacker_skill", type=int)
    p2.add_argument("defender_skill", type=int)
    p2.add_argument("weapon_dmg", help="如 1d6")
    p2.add_argument("db", help="如 +0 / +1d4")
    p2.add_argument("--by", default="kp"); p2.add_argument("--why", default="")
    p2.add_argument("--room", default=None)

    p3 = sub.add_parser("wound", help="HP<=0 时的重伤表查询")
    p3.add_argument("current_hp", type=int)

    args = ap.parse_args()
    if args.cmd == "ini":
        out({"ok": True, "initiative": initiative(args.attacker_dex, args.defender_dex)})
    elif args.cmd == "attack":
        out({"ok": True,
             "attack": attack_round(args.attacker_skill, args.defender_skill,
                                    args.weapon_dmg, args.db,
                                    args.by, args.why, args.room)})
    else:
        out({"ok": True, "wound": major_wound_roll(args.current_hp)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
