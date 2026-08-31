# -*- coding: utf-8 -*-
"""游戏房间 API（M1.5）：/api/games（挂载后 /api/games）。

覆盖：
- 生命周期：创建 / 公共视图 / 加入
- 角色卡：自动生成 / 直传 / 列表 / 单查
- 回合：行动提交 / 自由掷骰 / 审计 / 房主强制推进
- SSE：/events 实时事件流（含断线重连历史回放）

鉴权约定（M1 简化版）：
- 玩家：请求头 X-Player-Token（player_from_token）
- 房主：请求头 X-Host-Token（host_from_token）
SSE /events 无强制鉴权：带合法玩家令牌则绑定 uid 以接收定向感知事件。
"""
from __future__ import annotations

from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server import modules, roundman, store
from server.engine import build_character, roll_expr
from server.sse import EventBus, format_sse
from server.store import GameStore

router = APIRouter(prefix="/games", tags=["games"])


# ---------------- 鉴权辅助 ----------------

def _room_or_404(game_key: str) -> tuple[GameStore, dict]:
    """取游戏存档与房间记录；房间不存在抛 404。"""
    st = store.get_store(game_key)
    game = st.get_game(game_key)
    if game is None:
        raise HTTPException(status_code=404, detail=f"房间 {game_key} 不存在")
    return st, game


def player_from_token(request: Request, game_key: str) -> dict:
    """按请求头 X-Player-Token 解析玩家身份；房间不存在抛 404，无有效令牌抛 401。"""
    st = store.get_store(game_key)
    if st.get_game(game_key) is None:
        raise HTTPException(status_code=404, detail=f"房间 {game_key} 不存在")
    token = request.headers.get("X-Player-Token")
    if not token:
        raise HTTPException(status_code=401, detail="缺少玩家令牌 X-Player-Token")
    for p in st.list_players(game_key):
        if roundman.verify_token(game_key, p["uid"], token):
            return p
    raise HTTPException(status_code=401, detail="玩家令牌无效")


def host_from_token(request: Request, game_key: str) -> dict:
    """按请求头 X-Host-Token 解析房主身份；房间不存在抛 404，无有效令牌抛 401。"""
    st = store.get_store(game_key)
    if st.get_game(game_key) is None:
        raise HTTPException(status_code=404, detail=f"房间 {game_key} 不存在")
    token = request.headers.get("X-Host-Token")
    if not token:
        raise HTTPException(status_code=401, detail="缺少房主令牌 X-Host-Token")
    for p in st.list_players(game_key):
        if p.get("is_host") and roundman.verify_token(game_key, p["uid"], token):
            return p
    raise HTTPException(status_code=401, detail="房主令牌无效")


# ---------------- 请求体 ----------------

class CreateGameBody(BaseModel):
    """创建房间请求体。"""
    name: str
    rule: str = "coc7"
    module_id: str | None = None
    world_summary: str | None = None
    host_name: str = "房主"


class JoinBody(BaseModel):
    """加入房间请求体。"""
    name: str


class CharacterBody(BaseModel):
    """建卡请求体：action=auto 自动生成，或 character 直传角色卡 JSON。"""
    action: str | None = None
    name: str | None = None
    character: dict | None = None


class ActionBody(BaseModel):
    """行动提交请求体。"""
    text: str


class RollBody(BaseModel):
    """自由掷骰请求体。"""
    expr: str
    why: str = ""


# ---------------- 生命周期 ----------------

@router.post("")
def create_game(body: CreateGameBody) -> dict:
    """创建游戏房间；返回游戏号与房主凭证（M1 无访问密码，不重复建玩家）。"""
    if body.module_id is not None and modules.get_module(body.module_id) is None:
        raise HTTPException(status_code=400, detail=f"模组 {body.module_id} 不存在")
    return roundman.create_game(
        name=body.name,
        rule=body.rule,
        module_id=body.module_id,
        world_summary=body.world_summary,
        host_name=body.host_name,
    )


@router.get("/{game_key}")
def game_view(game_key: str) -> dict:
    """房间公共视图（无鉴权；SSE 重连 / 前端校准用全量兜底）。"""
    view = roundman.game_public_view(game_key)
    if view is None:
        raise HTTPException(status_code=404, detail=f"房间 {game_key} 不存在")
    return {"game": view}


@router.post("/{game_key}/join")
def join(game_key: str, body: JoinBody) -> dict:
    """加入房间；房主由 create_game 自动占位为玩家 1，不重复加入。"""
    try:
        return roundman.join_game(game_key, body.name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"房间 {game_key} 不存在") from None
    except ValueError:
        raise HTTPException(status_code=409, detail="名字已被占用") from None


# ---------------- 角色卡 ----------------

@router.post("/{game_key}/characters")
async def create_character(game_key: str, body: CharacterBody,
                           request: Request) -> dict:
    """建卡（需玩家令牌）：action=auto 自动生成；或直传 schema coc7-character/v1 JSON。"""
    st, game = _room_or_404(game_key)
    player = player_from_token(request, game_key)
    if body.character is not None:
        char = body.character
        char_name = body.name or player["name"]
    elif body.action == "auto":
        char_name = body.name or player["name"]
        char = build_character(char_name)
    else:
        raise HTTPException(status_code=400, detail="需提供 character（角色卡 JSON）或 action=auto")
    st.set_character(game_key, player["uid"], char_name, char)
    bus: EventBus = request.app.state.bus
    await bus.publish(game_key, "character_ready",
                      {"uid": player["uid"], "name": char_name})
    return {"character": char}


@router.get("/{game_key}/characters")
def list_characters(game_key: str, request: Request) -> dict:
    """角色卡列表（需玩家令牌）。"""
    st, _ = _room_or_404(game_key)
    player_from_token(request, game_key)
    return {"characters": st.list_characters(game_key)}


@router.get("/{game_key}/characters/{player_name}")
def get_character(game_key: str, player_name: str, request: Request) -> dict:
    """按角色名查单张角色卡（需玩家令牌）；找不到抛 404。"""
    st, _ = _room_or_404(game_key)
    player_from_token(request, game_key)
    for c in st.list_characters(game_key):
        if c["name"] == player_name:
            return {"character": c}
    raise HTTPException(status_code=404, detail=f"角色 {player_name} 不存在")


# ---------------- 回合 ----------------

@router.post("/{game_key}/actions")
async def submit_action(game_key: str, body: ActionBody, request: Request) -> dict:
    """提交/修改本轮行动（需玩家令牌）；action_version 每次 +1 并广播。"""
    st, game = _room_or_404(game_key)
    player = player_from_token(request, game_key)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="行动内容不能为空")
    version = st.set_action(game_key, player["uid"], game["round"], text)
    bus: EventBus = request.app.state.bus
    await bus.publish(game_key, "action_received", {
        "uid": player["uid"],
        "name": player["name"],
        "round": game["round"],
        "action_version": version,
    })
    return {"accepted": True, "round": game["round"], "action_version": version}


@router.post("/{game_key}/roll")
async def roll_dice(game_key: str, body: RollBody, request: Request) -> dict:
    """自由掷骰（需玩家令牌）：结果入审计并广播 dice_result。"""
    st, game = _room_or_404(game_key)
    player = player_from_token(request, game_key)
    try:
        result = roll_expr(body.expr, by=player["name"], why=body.why, no_log=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"非法的骰子表达式: {e}") from None
    st.add_dice_log(game_key, kind="roll", payload=result, round_no=game["round"])
    bus: EventBus = request.app.state.bus
    await bus.publish(game_key, "dice_result", {
        **result,
        "uid": player["uid"],
        "name": player["name"],
        "round": game["round"],
    })
    return {"result": result}


@router.get("/{game_key}/audit")
def audit(game_key: str, request: Request,
          last: int = Query(20, ge=1, le=200)) -> dict:
    """掷骰审计（需玩家令牌）：最近 N 条，默认 20，上限 200（超出 422）。"""
    st, _ = _room_or_404(game_key)
    player_from_token(request, game_key)
    return {"audit": st.list_dice_log(game_key, last=last)}


@router.post("/{game_key}/advance")
async def advance(game_key: str, request: Request) -> dict:
    """房主强制推进（需 X-Host-Token）：轮次 +1，广播 turn_advanced / round_started。"""
    st, game = _room_or_404(game_key)
    host_from_token(request, game_key)
    new_round = roundman.advance_game(game_key)
    data = {"round": new_round, "phase": "collecting"}
    bus: EventBus = request.app.state.bus
    await bus.publish(game_key, "turn_advanced", data)
    await bus.publish(game_key, "round_started", data)
    return {"triggered": True, "round": new_round}


# ---------------- SSE ----------------

@router.get("/{game_key}/events")
async def events(game_key: str, request: Request) -> StreamingResponse:
    """SSE 事件流：无强制鉴权；带合法玩家令牌则绑定 uid 接收定向感知事件。

    房间不存在时先回 404，不开流。
    """
    _room_or_404(game_key)  # 404 检查：房间必须已存在
    uid: str | None = None
    token = request.headers.get("X-Player-Token")
    if token:
        try:
            uid = player_from_token(request, game_key)["uid"]
        except HTTPException:
            pass  # 令牌无效则降级为匿名广播订阅（仍可收广播事件）
    bus: EventBus = request.app.state.bus

    async def gen() -> AsyncIterator[str]:
        """订阅事件总线，逐条编码为 SSE wire 文本（含历史回放）。"""
        async for ev in bus.subscribe(game_key, uid=uid):
            yield format_sse(ev)

    return StreamingResponse(gen(), media_type="text/event-stream")
