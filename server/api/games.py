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

from server import auth, modules, roundman, store
from server.engine import build_character, roll_expr
from server.gm.llm import LLMClient
from server.gm.pipeline import run_round
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
    password: str | None = None      # 可选访问密码（M5.1）


class JoinBody(BaseModel):
    """加入房间请求体：邀请凭证走 X-Join-Token 头，密码可选（M5.1）。"""
    name: str
    password: str | None = None


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


class KickBody(BaseModel):
    """房主移除玩家请求体。"""
    uid: str


# ---------------- 生命周期 ----------------

@router.post("")
def create_game(body: CreateGameBody) -> dict:
    """创建游戏房间；返回游戏号、房主凭证与邀请凭证（M5.1 可选访问密码）。"""
    if body.module_id is not None and modules.get_module(body.module_id) is None:
        raise HTTPException(status_code=400, detail=f"模组 {body.module_id} 不存在")
    result = roundman.create_game(
        name=body.name,
        rule=body.rule,
        module_id=body.module_id,
        world_summary=body.world_summary,
        host_name=body.host_name,
    )
    game_key = result["game_key"]
    st = store.get_store(game_key)
    invite_token = auth.new_invite_token()
    updates = {"invite_token": invite_token}
    if body.password:
        updates["password_hash"] = auth.hash_password(body.password)
    st.update_game(game_key, **updates)
    if body.module_id:
        _inject_opening(body.module_id, game_key)
    result["invite_token"] = invite_token
    return result


def _inject_opening(module_id: str, game_key: str) -> None:
    """开局注入（M4）：current_scene=首场景 + 开场消息 + kp-notes 全文（只进守密人上下文）。"""
    st = store.get_store(game_key)
    flow = modules.get_scene_flow(module_id)
    if not flow:
        return
    scene = modules.get_scene(module_id, flow[0])
    if scene is None:
        return
    st.update_game(game_key, current_scene=scene["id"])
    st.add_message(game_key, 0, "scene", {
        "text": f"{scene.get('name', '')} · {scene.get('location', '')}\n{scene.get('summary', '')}",
        "scene_id": scene["id"],
    })
    kp = modules.module_dir(module_id) / "kp-notes.md"
    if kp.exists():
        st.add_kp_note(game_key, kp.read_text(encoding="utf-8"), 0)


@router.get("/{game_key}")
def game_view(game_key: str) -> dict:
    """房间公共视图（无鉴权；SSE 重连 / 前端校准用全量兜底）。"""
    view = roundman.game_public_view(game_key)
    if view is None:
        raise HTTPException(status_code=404, detail=f"房间 {game_key} 不存在")
    return {"game": view}


@router.post("/{game_key}/join")
def join(game_key: str, body: JoinBody, request: Request) -> dict:
    """加入房间（M5.1）：必须携带邀请凭证 X-Join-Token；设了访问密码则校验密码。

    房主由 create_game 自动占位为玩家 1，不重复加入。
    """
    st, game = _room_or_404(game_key)
    invite_token = request.headers.get("X-Join-Token")
    if not invite_token or invite_token != game.get("invite_token"):
        raise HTTPException(status_code=401, detail="邀请无效或已过期")
    if game.get("password_hash"):
        if not body.password or not auth.verify_password(body.password,
                                                         game["password_hash"]):
            raise HTTPException(status_code=403, detail="访问密码错误")
    try:
        return roundman.join_game(game_key, body.name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"房间 {game_key} 不存在") from None
    except ValueError:
        raise HTTPException(status_code=409, detail="名字已被占用") from None


# ---------------- M5.4 房主管理 / M5.1 邀请轮换 / M5.2 暂离 ----------------

@router.post("/{game_key}/invite")
async def refresh_invite(game_key: str, request: Request) -> dict:
    """房主轮换邀请凭证（旧码立即失效）。"""
    st, _ = _room_or_404(game_key)
    host_from_token(request, game_key)
    invite_token = auth.new_invite_token()
    st.update_game(game_key, invite_token=invite_token)
    return {"invite_token": invite_token}


@router.post("/{game_key}/away")
async def away(game_key: str, request: Request) -> dict:
    """玩家暂离（M5.2 暂离不阻塞回合）。"""
    st, _ = _room_or_404(game_key)
    player = player_from_token(request, game_key)
    st.update_player(game_key, player["uid"], is_away=1)
    bus: EventBus = request.app.state.bus
    await bus.publish(game_key, "player_status",
                      {"uid": player["uid"], "is_away": True})
    return {"uid": player["uid"], "is_away": True}


@router.post("/{game_key}/back")
async def back(game_key: str, request: Request) -> dict:
    """玩家回归。"""
    st, _ = _room_or_404(game_key)
    player = player_from_token(request, game_key)
    st.update_player(game_key, player["uid"], is_away=0)
    bus: EventBus = request.app.state.bus
    await bus.publish(game_key, "player_status",
                      {"uid": player["uid"], "is_away": False})
    return {"uid": player["uid"], "is_away": False}


@router.post("/{game_key}/kick")
async def kick(game_key: str, body: KickBody, request: Request) -> dict:
    """房主移除玩家（不能踢房主；被踢玩家 token 立即失效）。"""
    st, _ = _room_or_404(game_key)
    host = host_from_token(request, game_key)
    if body.uid == host["uid"]:
        raise HTTPException(status_code=400, detail="不能移除房主")
    st.delete_player(game_key, body.uid)
    bus: EventBus = request.app.state.bus
    await bus.publish(game_key, "player_removed", {"uid": body.uid})
    return {"removed": body.uid}


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
    """提交/修改本轮行动（需玩家令牌）；action_version 每次 +1 并广播。

    单人/全员就绪 → 自动推进（M4）：裁判 → 引擎掷骰 → 叙事 → 状态落库 → 广播。
    """
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
    advanced = await _maybe_auto_advance(request, game_key)
    return {"accepted": True, "round": game["round"],
            "action_version": version, "auto_advanced": advanced}


# ---------------- 单人自动推进（M4.4） ----------------

async def _broadcast_round_result(request: Request, game_key: str, result: dict) -> None:
    """把一轮管线结果广播为 SSE 事件（kp_notes 绝不广播）。"""
    bus: EventBus = request.app.state.bus
    round_no = result["round"]
    for res in result["dice_results"]:
        await bus.publish(game_key, "dice_result", {**res, "round": round_no})
    await bus.publish(game_key, "narration",
                      {"round": round_no, "text": result["narrative"]})
    for item in result["applied"]:
        await bus.publish(game_key, "state_changed", {**item, "round": round_no})
    for perc in result["perceptions"]:
        await bus.publish(game_key, "perception",
                          {"to": perc["to_uid"], "text": perc["text"],
                           "clue_id": perc.get("clue_id")},
                          to_uid=perc["to_uid"])
    if result.get("scene"):
        await bus.publish(game_key, "scene_changed", {
            "scene": result["scene"], "handouts": result["handouts"]})
        for h in result["handouts"]:
            await bus.publish(game_key, "handout", {"file": h})


async def _maybe_auto_advance(request: Request, game_key: str) -> bool:
    """活跃玩家全部已提交 → 自动推进一轮（单人模式即提交即推进）。"""
    st = store.get_store(game_key)
    game = st.get_game(game_key)
    if game is None:
        return False
    players = st.list_players(game_key)
    active = [p for p in players if not p["is_away"]]
    if not active or not all(p["has_submitted"] for p in active):
        return False
    async with roundman.pipeline_lock(game_key):
        # 锁内复查（防并发重复推进）
        game = st.get_game(game_key)
        players = st.list_players(game_key)
        active = [p for p in players if not p["is_away"]]
        if not active or not all(p["has_submitted"] for p in active):
            return False
        result = await run_round(game_key, llm=LLMClient.from_config())
        await _broadcast_round_result(request, game_key, result)
        new_round = roundman.advance_game(game_key)
        data = {"round": new_round, "phase": "collecting"}
        bus: EventBus = request.app.state.bus
        await bus.publish(game_key, "turn_advanced", data)
        await bus.publish(game_key, "round_started", data)
    return True


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
    # TODO-B#1（M5 一并落地）：自由掷骰落叙事流（kind=dice，复用判定卡片渲染）
    st.add_message(game_key, game["round"], "dice", {
        **result, "uid": player["uid"], "name": player["name"],
    })
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


@router.get("/{game_key}/messages")
def messages(game_key: str, request: Request,
             last: int = Query(100, ge=1, le=500)) -> dict:
    """叙事流消息（需玩家令牌）：SSE 重连/刷新后的全量校准（M4）。"""
    st, _ = _room_or_404(game_key)
    player_from_token(request, game_key)
    msgs = st.list_messages(game_key, limit=last)
    return {"messages": msgs, "count": len(msgs)}


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

    令牌来源（M5.3，前端 EventSource 带不了请求头）：
      优先 `?token=` 查询参数，其次请求头 `X-Player-Token`。
    房间不存在时先回 404，不开流。
    """
    _room_or_404(game_key)  # 404 检查：房间必须已存在
    uid: str | None = None
    token = request.query_params.get("token") or request.headers.get("X-Player-Token")
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
