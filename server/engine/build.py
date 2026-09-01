# -*- coding: utf-8 -*-
"""CoC7th 角色 build（生成）。

属性生成（标准 CoC7th 规则）：
  STR / CON / DEX / APP / POW / INT / SIZ  =  5d6 × 6  →  × 取，舍弃 5 个最低
  EDU  =  (2d6+6) × 5
  Luck =  5d6 × 5 取（舍弃 5 个最低和 EDU 算法一致） — 此处与 EDU 同法
  HP   =  (CON + SIZ) / 10 （向上取整）
  MP   =  POW / 5 （向上取整）
  SAN  =  POW（百分制，初始理智 = 意志值本身）
  DB   =  STR+SIZ 查表
  MOV  =  默认 8（STR<DEX<80 时 -1；SIZ>79 时 -1）

技能初始值（默认职业相关仅给出最小初始；通用职业点分配留待 PL 自填）。
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

# 用 UTF-8 直接写 stdout，绕过 Windows GBK 控制台编码问题
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Py 3.7+
except Exception:  # pragma: no cover
    pass

sys.path.insert(0, str(Path(__file__).parent))
from _common import out, relabel, write_json  # noqa: E402


# ------- 骰子辅助（仅本文件使用，单独命名避免冲突） -------

def _roll_one(n: int, m: int) -> int:
    return sum(secrets.randbelow(m) + 1 for _ in range(n))


def _roll_keep(n: int, m: int, keep: int) -> int:
    """roll n 个 dm，保留最高的 keep 个相加。"""
    rolls = sorted([secrets.randbelow(m) + 1 for _ in range(n)], reverse=True)
    return sum(rolls[:keep])


def gen_attributes() -> dict:
    """生成 8 项主属性 + Luck（标准 CoC7th 5d6×6 keep 3 + EDU (2d6+6) × 5）。"""
    a = {}
    for stat in ("STR", "CON", "DEX", "APP", "POW", "INT", "SIZ"):
        # 5d6 keep 3，乘 5
        a[stat] = _roll_keep(5, 6, 3) * 5
    # EDU = (2d6 + 6) * 5
    a["EDU"] = (_roll_keep(2, 6, 2) + 6) * 5
    # Luck = 5d6 keep 3，乘 5
    a["LUK"] = _roll_keep(5, 6, 3) * 5
    return a


def derived(a: dict) -> dict:
    """由属性派生 HP/MP/SAN/DB/MOV。"""
    siz, con, str_, dex, pow_ = a["SIZ"], a["CON"], a["STR"], a["DEX"], a["POW"]
    hp = -(-(con + siz) // 10)          # ceil
    mp = -(-pow_ // 5)
    san = pow_
    db_sum = str_ + siz
    if db_sum <= 64:    db = "-2"
    elif db_sum <= 84:  db = "-1"
    elif db_sum <= 124: db = "0"
    elif db_sum <= 164: db = "+1d4"
    elif db_sum <= 204: db = "+1d6"
    else:               db = "+2d6"
    mov = 8
    if str_ < dex and str_ < 80: mov -= 1
    if siz > 79:                mov -= 1
    if mov < 1:                  mov = 1
    return {"HP": hp, "MP": mp, "SAN": san, "DB": db, "MOV": mov}


# 默认技能初始值（CoC7th 通用；非职业专长。完整技能表见 references/skills-table.md）
DEFAULT_SKILLS = {
    "Accounting":5,"Anthropology":1,"Appraise":5,"Archaeology":1,"Art/Craft":5,
    "Charm":15,"Climb":20,"Credit Rating":0,"Cthulhu Mythos":0,"Disguise":5,
    "Dodge":30,"Drive Auto":20,"Elec Repair":10,"Fast Talk":5,"Fighting(Brawl)":25,
    "Firearms(Handgun)":20,"Firearms(Rifle)":25,"First Aid":30,"History":5,"Intimidate":15,
    "Jump":20,"Language(English)":20,"Language(Other)":1,"Law":5,"Library Use":20,
    "Listen":20,"Locksmith":1,"Mech Repair":10,"Medicine":1,"Natural World":10,
    "Navigate":10,"Occult":5,"Op Hvy Machine":1,"Persuade":10,"Pilot":1,
    "Psychoanalysis":1,"Psychology":10,"Ride":5,"Science":1,"Sleight of Hand":10,
    "Spot Hidden":25,"Stealth":20,"Survival":10,"Swim":20,"Throw":20,
    "Track":10,
}


def build_character(name: str, age: int = 25) -> dict:
    a = gen_attributes()
    d = derived(a)
    return {
        "schema": "coc7-character/v1",
        "name": name,
        "meta": {"age": age, "occupation": "(未填)"},
        "attributes": {
            "STR": a["STR"], "CON": a["CON"], "SIZ": a["SIZ"],
            "DEX": a["DEX"], "APP": a["APP"], "INT": a["INT"],
            "POW": a["POW"], "EDU": a["EDU"], "LUK": a["LUK"],
        },
        "derived": d,
        "skills": dict(DEFAULT_SKILLS),
        "inventory": [],
        "notes": [],
        "sanity": {"current": d["SAN"], "max": d["SAN"], "history": []},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="CoC7th 角色 build")
    ap.add_argument("name", help="角色名")
    ap.add_argument("--age", type=int, default=25, help="角色年龄（EDU 调整时使用）")
    ap.add_argument("--out", default=None, help="输出 JSON 路径；省略则打到 stdout")
    args = ap.parse_args()

    char = build_character(args.name, args.age)

    if args.out:
        write_json(Path(args.out), char)
        # 隐私净化：saved 用相对标签回显，避免把机器绝对路径带回飞书群
        out({"ok": True, "saved": relabel(Path(args.out)), "summary": {
            "name": char["name"], "STR": char["attributes"]["STR"],
            "CON": char["attributes"]["CON"], "HP": char["derived"]["HP"],
            "SAN": char["sanity"]["current"], "DB": char["derived"]["DB"],
        }})
    else:
        out({"ok": True, "character": char})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
