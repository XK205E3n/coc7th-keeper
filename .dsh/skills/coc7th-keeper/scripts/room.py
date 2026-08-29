# -*- coding: utf-8 -*-
"""CoC7th 房间与角色生命周期 CLI。

用法：
  room.py init <room_id> [--module <mod-id>] [--kp <name>]
  room.py join <room_id> <player_name>
  room.py leave <room_id> <player_name>
  room.py build <room_id> <player_name> [--age <n>]
  room.py save <room_id>
  room.py load <room_id>
  room.py status <room_id>
  room.py audit <room_id> [--last N]
  room.py kick <room_id> <actor> <target>   (KP 强制踢人 / 调整)
  room.py pwd   显示当前房间根目录
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# 用 UTF-8 直接写 stdout，绕过 Windows GBK 控制台编码问题
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Py 3.7+
except Exception:  # pragma: no cover
    pass

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    ensure_room, modules_dir, out, read_json, relabel, room_dir, session_root,
    write_json,
)
from build import build_character  # noqa: E402


def now_ts() -> int:
    return int(time.time() * 1000)


def _valid_module_ids() -> set[str]:
    """从 modules/<id>/meta.json 自动发现可用模组 ID 集合（锚定工作区，见 _common.modules_dir）。"""
    modules_dir_path = modules_dir()
    ids: set[str] = set()
    if not modules_dir_path.exists():
        return ids
    for child in modules_dir_path.iterdir():
        if not child.is_dir():
            continue
        meta = read_json(child / "meta.json", default={})
        if meta and meta.get("schema") == "coc7-module/v1" and meta.get("id"):
            ids.add(meta["id"])
    return ids


def cmd_init(room_id: str, module: str | None, kp: str) -> dict:
    base = ensure_room(room_id)
    rj = base / "room.json"
    room = read_json(rj, default={})
    # 校验 --module（若用户提供了 ID）
    if module:
        valid = _valid_module_ids()
        if module not in valid:
            return {"ok": False, "error": f"未知模组：{module!r}",
                    "available": sorted(valid),
                    "hint": "用 /coc modules 查看可玩模组列表，或直接用列表中的 id 重新 init"}
    if not room:
        room = {
            "schema": "coc7-room/v1",
            "id": room_id,
            "created_at": now_ts(),
            "kp": kp or "KP",
            "players": [],
            "module": module,
            "turn": 0,
            "log_offset": 0,
        }
        write_json(rj, room)
        (base / "log.md").write_text(
            f"# CoC7th 跑团日志 — 房间 `{room_id}`\n\n"
            f"- KP: `{room['kp']}`\n"
            f"- 模块: `{module or '(尚未选择)'}`\n"
            f"- 创建时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n",
            encoding="utf-8",
        )
    else:
        # 已存在，更新 KP/module 字段
        if kp: room["kp"] = kp
        if module: room["module"] = module
        write_json(rj, room)
    return {"ok": True, "room": room_id, "path": relabel(base)}


def cmd_join(room_id: str, player_name: str) -> dict:
    base = ensure_room(room_id)
    rj = base / "room.json"
    room = read_json(rj, default={})
    if not room:
        return {"ok": False, "error": f"房间 {room_id} 不存在；先 init"}
    if player_name not in room["players"]:
        room["players"].append(player_name)
        write_json(rj, room)
    # 角色卡（如不存在先建一个空壳）
    pf = base / "players" / f"{player_name}.json"
    if not pf.exists():
        write_json(pf, {
            "schema": "coc7-character/v1",
            "name": player_name,
            "attributes": {}, "derived": {}, "skills": {},
            "inventory": [], "notes": [],
            "sanity": {"current": 50, "max": 50, "history": []},
        })
    return {"ok": True, "room_id": room_id, "player": player_name,
            "players": room["players"], "kp": room["kp"]}


def cmd_build(room_id: str, player_name: str, age: int) -> dict:
    base = ensure_room(room_id)
    pf = base / "players" / f"{player_name}.json"
    if not pf.exists():
        # 隐私净化：错误信息用相对标签，不暴露机器绝对路径
        return {"ok": False, "error": f"角色卡不存在：{relabel(pf)}；请先 join"}
    char = build_character(player_name, age)
    char["name"] = player_name  # 强制一致
    write_json(pf, char)
    return {"ok": True, "saved": relabel(pf),
            "summary": {"name": char["name"], "STR": char["attributes"]["STR"],
                        "CON": char["attributes"]["CON"], "DEX": char["attributes"]["DEX"],
                        "POW": char["attributes"]["POW"], "HP": char["derived"]["HP"],
                        "SAN": char["sanity"]["current"], "DB": char["derived"]["DB"]}}


def cmd_status(room_id: str) -> dict:
    base = ensure_room(room_id)
    rj = read_json(base / "room.json", default={})
    if not rj:
        return {"ok": False, "error": f"房间 {room_id} 不存在"}
    players = []
    for pn in rj.get("players", []):
        pf = base / "players" / f"{pn}.json"
        c = read_json(pf, default={})
        players.append({
            "name": pn,
            "STR": c.get("attributes", {}).get("STR"),
            "CON": c.get("attributes", {}).get("CON"),
            "HP": c.get("derived", {}).get("HP"),
            "SAN_current": c.get("sanity", {}).get("current"),
            "skills_count": len(c.get("skills", {})),
        })
    log_exists = (base / "log.md").exists()
    dice_count = sum(1 for _ in (base / "dice.log").open("r", encoding="utf-8", errors="ignore")) if (base / "dice.log").exists() else 0
    return {"ok": True, "room": rj, "players": players,
            "log_exists": log_exists, "dice_entries": dice_count}


def cmd_audit(room_id: str, last: int) -> dict:
    base = ensure_room(room_id)
    log = base / "dice.log"
    if not log.exists():
        return {"ok": True, "entries": []}
    lines = log.read_text(encoding="utf-8", errors="ignore").splitlines()
    entries = []
    for ln in lines[-last:]:
        try: entries.append(json.loads(ln))
        except: pass
    return {"ok": True, "count": len(entries), "entries": entries}


def cmd_save(room_id: str) -> dict:
    """打包房间快照为单个 JSON（含所有角色卡 / 房间 / 最近日志）。"""
    import zipfile, hashlib
    base = ensure_room(room_id)
    snapshot = {
        "schema": "coc7-snapshot/v1",
        "saved_at": now_ts(),
        "room": read_json(base / "room.json", default={}),
        "players": {},
        "kp_notes": (base / "kp-notes.md").read_text(encoding="utf-8") if (base / "kp-notes.md").exists() else "",
        "log": (base / "log.md").read_text(encoding="utf-8") if (base / "log.md").exists() else "",
    }
    for pn in snapshot["room"].get("players", []):
        pf = base / "players" / f"{pn}.json"
        snapshot["players"][pn] = read_json(pf, default={})
    out_path = base / f"snapshot-{room_id}-{now_ts()}.json"
    write_json(out_path, snapshot)
    sha = hashlib.sha256(out_path.read_bytes()).hexdigest()
    return {"ok": True, "path": relabel(out_path), "sha256": sha}


def cmd_load(room_id: str, snapshot_path: str) -> dict:
    """从 snapshot JSON 恢复房间。"""
    base = ensure_room(room_id)
    src = Path(snapshot_path)
    if not src.exists():
        # 隐私净化：错误信息用相对标签，不暴露机器绝对路径
        return {"ok": False, "error": f"快照不存在：{relabel(src)}"}
    snap = read_json(src, default={})
    if snap.get("schema") != "coc7-snapshot/v1":
        return {"ok": False, "error": "快照 schema 不匹配"}
    write_json(base / "room.json", snap["room"])
    for pn, char in snap["players"].items():
        write_json(base / "players" / f"{pn}.json", char)
    if snap.get("kp_notes"):
        (base / "kp-notes.md").write_text(snap["kp_notes"], encoding="utf-8")
    if snap.get("log"):
        (base / "log.md").write_text(snap["log"], encoding="utf-8")
    return {"ok": True, "loaded_from": relabel(src)}


def cmd_kick(room_id: str, target: str) -> dict:
    base = ensure_room(room_id)
    rj = read_json(base / "room.json", default={})
    if target in rj.get("players", []):
        rj["players"].remove(target)
        write_json(base / "room.json", rj)
    pf = base / "players" / f"{target}.json"
    if pf.exists():
        pf.unlink()
    return {"ok": True, "kicked": target, "players": rj.get("players", [])}


def main() -> int:
    ap = argparse.ArgumentParser(description="CoC7th 房间与角色")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init"); p.add_argument("room_id")
    p.add_argument("--module", default=None); p.add_argument("--kp", default="KP")
    p = sub.add_parser("join"); p.add_argument("room_id"); p.add_argument("player_name")
    p = sub.add_parser("leave"); p.add_argument("room_id"); p.add_argument("player_name")
    p = sub.add_parser("build"); p.add_argument("room_id"); p.add_argument("player_name")
    p.add_argument("--age", type=int, default=25)
    p = sub.add_parser("save"); p.add_argument("room_id")
    p = sub.add_parser("load"); p.add_argument("room_id"); p.add_argument("snapshot_path")
    p = sub.add_parser("status"); p.add_argument("room_id")
    p = sub.add_parser("audit"); p.add_argument("room_id"); p.add_argument("--last", type=int, default=20)
    p = sub.add_parser("kick"); p.add_argument("room_id"); p.add_argument("target")
    p = sub.add_parser("pwd")

    args = ap.parse_args()
    try:
        if args.cmd == "init":   result = cmd_init(args.room_id, args.module, args.kp)
        elif args.cmd == "join": result = cmd_join(args.room_id, args.player_name)
        elif args.cmd == "build":result = cmd_build(args.room_id, args.player_name, args.age)
        elif args.cmd == "save": result = cmd_save(args.room_id)
        elif args.cmd == "load": result = cmd_load(args.room_id, args.snapshot_path)
        elif args.cmd == "status":result = cmd_status(args.room_id)
        elif args.cmd == "audit": result = cmd_audit(args.room_id, args.last)
        elif args.cmd == "kick":  result = cmd_kick(args.room_id, args.target)
        elif args.cmd == "pwd":   result = {"ok": True, "session_root": relabel(session_root())}
        else:
            # leave 由 kick 复用
            result = cmd_kick(args.room_id, args.player_name)
    except Exception as e:
        return out({"ok": False, "error": str(e)})

    out(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
