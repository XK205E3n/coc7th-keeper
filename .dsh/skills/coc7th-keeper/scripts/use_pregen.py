# -*- coding: utf-8 -*-
"""把预制角色从 <skill-root>/modules/<id>/pregens/<name>.json 复制到 <session>/<room>/players/<player>.json。

用法：
  use_pregen.py <name> --room <room_id> --player <player_name>
  use_pregen.py <name> --room <room_id> --player <player_name> --module <module_id>

支持：
  - 自动从 modules/<id>/pregens/ 扫描（按模块 ID）；默认扫所有模块
  - 角色卡写入后自动创建 room.json（如不存在），让该玩家可立即被 room.py join
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
from _common import ensure_room, modules_dir, read_json, relabel, write_json  # noqa: E402

DEFAULT_PREGEN_DIR = modules_dir() / "the-haunting" / "pregens"


def _find_pregen(name: str) -> Path | None:
    """在所有模块的 pregens/ 里找名为 <name>.json 的预制角色（不区分大小写）。"""
    if not name:
        return None
    # 先按 the-haunting 优先（向后兼容），再扫其他模块
    candidates: list[Path] = []
    if DEFAULT_PREGEN_DIR.exists():
        candidates += sorted(DEFAULT_PREGEN_DIR.glob("*.json"))
    for mod_dir in modules_dir().iterdir():
        if not mod_dir.is_dir():
            continue
        pregens = mod_dir / "pregens"
        if not pregens.exists():
            continue
        for p in pregens.glob("*.json"):
            if p not in candidates:
                candidates.append(p)
    low = name.lower()
    for p in candidates:
        if p.stem.lower() == low:
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="选用预制角色到当前房间")
    ap.add_argument("name", help="预制角色名（去掉 .json 后缀），如 theron-quist")
    ap.add_argument("--room", required=True, help="目标房间 ID")
    ap.add_argument("--player", required=True, help="落地后的玩家名（飞书名）")
    ap.add_argument("--module", default=None,
                    help="可选：限定查找的模块 ID（如 toy-dancer-comes）")
    args = ap.parse_args()

    # 查找预制角色
    src = None
    if args.module:
        # 统一走 modules_dir()（COC_MODULES_DIR 优先），与 _common 锚定保持一致
        mod_pregens = modules_dir() / args.module / "pregens"
        if mod_pregens.exists():
            candidate = mod_pregens / f"{args.name}.json"
            if candidate.exists():
                src = candidate
    if src is None:
        src = _find_pregen(args.name)
    if src is None:
        # 列出可用预制
        available: list[str] = []
        for d in modules_dir().iterdir():
            pregens = d / "pregens"
            if pregens.exists():
                available += sorted(p.stem for p in pregens.glob("*.json"))
        print(f"ERROR: 找不到预制角色 '{args.name}'。"
              f" 可用: {available}", file=sys.stderr)
        return 1

    # 落到房间
    base = ensure_room(args.room)
    players_dir = base / "players"
    players_dir.mkdir(parents=True, exist_ok=True)
    dst = players_dir / f"{args.player}.json"

    # 读源，强制覆盖 name 为 player（飞书名）
    char = read_json(src, default={})
    if not char:
        # 隐私净化：错误信息用相对标签，不暴露机器绝对路径
        print(f"ERROR: 预制角色文件无法读取：{relabel(src)}", file=sys.stderr)
        return 1
    char["name"] = args.player
    write_json(dst, char)

    # 确保 room.json 里 players 列表包含本玩家
    rj_path = base / "room.json"
    room = read_json(rj_path, default={})
    if not room:
        room = {
            "schema": "coc7-room/v1",
            "id": args.room,
            "created_at": int(__import__("time").time() * 1000),
            "kp": "KP",
            "players": [],
            "module": args.module,
            "turn": 0,
            "log_offset": 0,
        }
    players_list = room.setdefault("players", [])
    if args.player not in players_list:
        players_list.append(args.player)
    write_json(rj_path, room)

    out = {
        "ok": True,
        "pregen": src.stem,
        "from": relabel(src),
        "to": relabel(dst),
        "room": args.room,
        "player": args.player,
        "summary": {
            "name": char.get("name"),
            "STR": char.get("attributes", {}).get("STR"),
            "CON": char.get("attributes", {}).get("CON"),
            "HP": char.get("derived", {}).get("HP"),
            "SAN": char.get("sanity", {}).get("current"),
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())