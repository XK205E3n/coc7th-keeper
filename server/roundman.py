# -*- coding: utf-8 -*-
"""回合调度器（M1.6）+ 房间级写锁。

M1 范围：
- 房间级 `threading.Lock`（写队列）：所有改动房间状态的入口必须 `with room_lock(key)`
- 生命周期与回合推进：create / join / advance（round+1 → 记录 rounds → 清空行动）
- SSE 广播由 API 层在锁外发出（见 server/api/games.py）

M2 起在此接入完整管线：收集 → AI 裁判（adjudicate.py 输出 dice_checks）→
服务端掷骰（固定骰果）→ 叙事（narrate.py）→ 状态应用（state_apply.py）→ 广播。
单人模式自动推进（活跃玩家=1 时提交即推进）在 M4 启用。
"""
from __future__ import annotations

import secrets
import threading
import time

from server import store

# ---------------- 房间级写锁 ----------------

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def room_lock(game_key: str) -> threading.Lock:
    """返回指定房间的写锁（首次调用时创建）。"""
    with _locks_guard:
        return _locks.setdefault(game_key, threading.Lock())


def new_game_key() -> str:
    """生成 8 位十六进制游戏标识（小写；符合 store.store_path 的 key 规则）。"""
    return secrets.token_hex(4)


# ---------------- 生命周期 ----------------

def create_game(name: str, rule: str = "coc7", module_id: str | None = None,
                world_summary: str | None = None, host_name: str = "房主",
                password_hash: str | None = None) -> dict:
    """创建游戏：建 games 行 + 房主玩家行。返回游戏状态与房主凭证。"""
    game_key = new_game_key()
    host_uid = "u_" + secrets.token_hex(4)
    host_token = secrets.token_hex(16)
    st = store.get_store(game_key)
    with room_lock(game_key):
        st.create_game(game_key, name, rule, module_id, world_summary,
                       host_uid, password_hash)
        st.add_player(game_key, host_uid, host_name,
                      token_hash=_hash_token(host_token), is_host=True)
    game = st.get_game(game_key)
    game["players"] = _public_players(st, game_key)
    return {"game": game, "host_uid": host_uid, "host_token": host_token,
            "game_key": game_key}


def join_game(game_key: str, name: str, token_hash: str | None = None) -> dict:
    """玩家加入：名字唯一性校验。返回玩家记录与凭证。

    M5 将扩展为邀请链接 + 角色认领 + 访问密码。
    """
    st = store.get_store(game_key)
    with room_lock(game_key):
        game = st.get_game(game_key)
        if game is None:
            raise KeyError(f"房间 {game_key} 不存在")
        if st.player_by_name(game_key, name) is not None:
            raise ValueError(f"名字 {name!r} 已被占用")
        uid = "u_" + secrets.token_hex(4)
        player_token = secrets.token_hex(16)
        st.add_player(game_key, uid, name, token_hash=_hash_token(player_token))
    return {"player": st.get_player(game_key, uid), "player_token": player_token}


def advance_game(game_key: str) -> int:
    """房主强制推进（M1 防卡死基础版）：round+1、清空行动、回 collecting。"""
    st = store.get_store(game_key)
    with room_lock(game_key):
        new_round = st.advance_round(game_key, phase="collecting")
    return new_round


def _hash_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(game_key: str, uid: str, token: str) -> bool:
    """校验玩家 token（M1 简化版；M5 auth.py 将统一凭证体系）。"""
    st = store.get_store(game_key)
    p = st.get_player(game_key, uid)
    if p is None or not p.get("token_hash"):
        return False
    return secrets.compare_digest(p["token_hash"], _hash_token(token))


def _public_players(st: "store.GameStore", game_key: str) -> list[dict]:
    """玩家列表的公共视图——不含 token_hash（M5 起再按角色裁剪 kp 字段）。"""
    out = []
    for p in st.list_players(game_key):
        out.append({
            "uid": p["uid"], "name": p["name"], "is_host": p["is_host"],
            "is_away": bool(p["is_away"]), "has_submitted": bool(p["has_submitted"]),
            "action_version": p["action_version"], "joined_at": p["joined_at"],
        })
    return out


def game_public_view(game_key: str) -> dict:
    """房间公共视图（SSE 重连 / 前端校准用全量兜底）。

    只含表侧内容：房间信息 + 玩家列表 + 回合/阶段 + 模组摘要。
    绝不包含 kp_notes / dice_log / 隐藏数值（隐私铁律 Web 化，§7）。
    """
    st = store.get_store(game_key)
    game = st.get_game(game_key)
    if game is None:
        return None
    view = {
        "game_key": game_key,
        "name": game["name"],
        "rule": game["rule"],
        "module_id": game["module_id"],
        "world_summary": game.get("world_summary"),
        "phase": game["phase"],
        "round": game["round"],
        "current_scene": game.get("current_scene"),
        "created_at": game["created_at"],
        "players": _public_players(st, game_key),
        "characters": st.list_characters(game_key),  # 角色卡公开字段
    }
    return view


def now_ms() -> int:
    return int(time.time() * 1000)
