# -*- coding: utf-8 -*-
"""开发者监视接口（M5.5）：只读查看房间内部数据。

- 鉴权：请求头 `X-Dev-Token` == data/config.json 的 `dev_token`（未配置 → 503）
- **只读**：全部端点只查询，绝不修改任何状态
- 可见内容：叙事流 / kp_notes / dice_log / state_changes / perceptions / llm_log / 房间全量
- 边界：房间不存在 404；players 输出去掉 token_hash（凭证不出现在监视接口）
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from server import config, store

router = APIRouter(prefix="/dev", tags=["dev"])


def require_dev(request: Request) -> None:
    """校验开发者令牌；未配置或错误一律拒绝。"""
    dev_token = config.load_config().get("dev_token")
    if not dev_token:
        raise HTTPException(status_code=503,
                            detail="未配置 dev_token，请在 data/config.json 设置")
    token = request.headers.get("X-Dev-Token")
    if not token or token != dev_token:
        raise HTTPException(status_code=401, detail="开发者令牌无效")


def _room_or_404(game_key: str) -> store.GameStore:
    st = store.get_store(game_key)
    if st.get_game(game_key) is None:
        raise HTTPException(status_code=404, detail=f"房间 {game_key} 不存在")
    return st


@router.get("/games")
def list_games(request: Request) -> dict:
    """扫描 data/games/*.db 列出全部房间（只读）。"""
    require_dev(request)
    games = []
    db_dir = Path(store.store_path("a1b2c3d4")).parent
    if db_dir.is_dir():
        for db in sorted(db_dir.glob("*.db")):
            key = db.stem
            try:
                st = store.get_store(key)
                g = st.get_game(key)
                if g:
                    games.append({"game_key": key, "name": g["name"],
                                  "round": g["round"], "phase": g["phase"]})
            except Exception:  # noqa: BLE001 - 单个坏库跳过
                continue
    return {"games": games, "count": len(games)}


@router.get("/games/{game_key}/messages")
def dev_messages(game_key: str, request: Request,
                 last: int = Query(100, ge=1, le=1000)) -> dict:
    require_dev(request)
    st = _room_or_404(game_key)
    return {"messages": st.list_messages(game_key, limit=last)}


@router.get("/games/{game_key}/kp_notes")
def dev_kp_notes(game_key: str, request: Request,
                 last: int = Query(50, ge=1, le=500)) -> dict:
    require_dev(request)
    st = _room_or_404(game_key)
    return {"kp_notes": st.list_kp_notes(game_key, limit=last)}


@router.get("/games/{game_key}/dice_log")
def dev_dice_log(game_key: str, request: Request,
                 last: int = Query(100, ge=1, le=1000)) -> dict:
    require_dev(request)
    st = _room_or_404(game_key)
    return {"dice_log": st.list_dice_log(game_key, last=last)}


@router.get("/games/{game_key}/state_changes")
def dev_state_changes(game_key: str, request: Request,
                      last: int = Query(100, ge=1, le=1000)) -> dict:
    require_dev(request)
    st = _room_or_404(game_key)
    return {"state_changes": st.list_state_changes(game_key, limit=last)}


@router.get("/games/{game_key}/perceptions")
def dev_perceptions(game_key: str, request: Request,
                    to_uid: str | None = None,
                    last: int = Query(100, ge=1, le=1000)) -> dict:
    require_dev(request)
    st = _room_or_404(game_key)
    return {"perceptions": st.list_perceptions(game_key, to_uid=to_uid, limit=last)}


@router.get("/games/{game_key}/llm_log")
def dev_llm_log(game_key: str, request: Request,
                last: int = Query(50, ge=1, le=500)) -> dict:
    require_dev(request)
    st = _room_or_404(game_key)
    return {"llm_log": st.list_llm_log(game_key, limit=last)}


@router.get("/games/{game_key}/room")
def dev_room(game_key: str, request: Request) -> dict:
    """房间全量（游戏 / 玩家 / 角色卡）；players 去掉 token_hash。"""
    require_dev(request)
    st = _room_or_404(game_key)
    game = st.get_game(game_key)
    players = []
    for p in st.list_players(game_key):
        p = dict(p)
        p.pop("token_hash", None)
        players.append(p)
    return {"game": game, "players": players,
            "characters": st.list_characters(game_key)}
