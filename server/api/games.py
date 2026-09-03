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

import logging
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server import auth, modules, roundman, store
from server.engine import build_character, roll_expr
from server.gm.llm import LLMClient, MAX_TOKENS_MAX, MAX_TOKENS_MIN
from server.gm.pipeline import run_round
from server.sse import EventBus, format_sse
from server.store import GameStore

logger = logging.getLogger("kp.games")

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


class ChatBody(BaseModel):
    """局内聊天（M7 额外任务）：text 为消息文本；expr 可选——带上的话服务端一并掷骰，
    骰果进 dice_log 审计并随聊天消息广播（分享掷骰结果）。"""
    text: str = ""
    expr: str | None = None


class KickBody(BaseModel):
    """房主移除玩家请求体。"""
    uid: str


class LlmLimitBody(BaseModel):
    """房主调整本局 LLM 输出上限请求体（max_tokens）。"""
    max_tokens: int


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
    # M7 建议：线索台账副本初始化（获得线索时状态更新，管理员可查）
    st.init_clue_ledger(game_key, modules.list_clues(module_id))


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
    if game.get("phase") == "closed":
        raise HTTPException(status_code=410, detail="房间已关闭")
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

    M8R5 语义（E3n 定案）：提交只保存行动，**不再自动推进** —— 全员提交后
    由「推进回合」按钮（任何人可点）或房主强制推进触发结算。
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
    logger.info("room %s round %s 玩家 %s 提交行动（v%s）",
                game_key, game["round"], player["name"], version)
    return {"accepted": True, "round": game["round"], "action_version": version}


def _identify_requester(request: Request, game_key: str) -> tuple[dict, bool]:
    """玩家令牌或房主令牌识别请求者，返回 (player, is_host)。"""
    try:
        player = player_from_token(request, game_key)
        return player, bool(player.get("is_host"))
    except HTTPException:
        pass
    st, game = _room_or_404(game_key)
    host_from_token(request, game_key)
    host_uid = game.get("host_uid")
    player = st.get_player(game_key, host_uid)
    if player is None:
        raise HTTPException(status_code=401, detail="身份无效")
    return player, True

def _llm_limit_text(limit: int, suggested: int) -> str:
    """截断提示文案：system 消息与 SSE 事件共用同一文本（前端按签名去重）。"""
    return (f"⚠️ AI 叙事输出达到 token 上限（{limit}）被截断，本轮已用离线兜底叙事。"
            f"房主可在「房主面板」调高输出上限（建议 {suggested}）。")


def _notify_llm_limit(st: GameStore, game_key: str, result: dict) -> None:
    """LLM 输出被截断：落一条 system 消息（刷新可恢复；只含提示，绝不含思考内容）。"""
    limit = result.get("llm_max_tokens") or 4000
    suggested = min(limit * 2, MAX_TOKENS_MAX)
    st.add_message(game_key, result["round"], "system", {
        "text": _llm_limit_text(limit, suggested),
        "max_tokens": limit,
        "suggested": suggested,
    })


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
    # LLM 输出截断 → 通知房主调高上限（只带提示文本与建议值，不带任何思考内容）
    if result.get("truncated"):
        limit = result.get("llm_max_tokens") or 4000
        suggested = min(limit * 2, MAX_TOKENS_MAX)
        await bus.publish(game_key, "llm_limit_hit", {
            "round": round_no,
            "stage": result.get("truncated_stage", ""),
            "text": _llm_limit_text(limit, suggested),
            "max_tokens": limit,
            "suggested": suggested,
        })


async def _settle_and_advance(request: Request, game_key: str,
                              skip_missing: bool = False) -> dict:
    """结算当前回合并推进（M8R5 抽取，自动结算与房主强制推进共用）。

    流程：裁判 → 引擎掷骰 → 叙事 → 状态落库 → round+1 → 广播。
    - skip_missing=False（自动结算）：仅当活跃玩家全部已提交时结算。
    - skip_missing=True（房主强制推进）：未提交行动的活跃玩家按「本轮无行动」
      跳过（不阻塞结算），已提交行动一律进入裁判，绝不丢弃（v1.0.3 实测空跳丢行动）。
    - 结算期间广播 llm_started / llm_finished（前端显示「AI 结算中」与失败原因）。

    返回 {"settled": bool, "round": int, "skipped": [未提交者名字]}。
    """
    st = store.get_store(game_key)
    bus: EventBus = request.app.state.bus

    async with roundman.pipeline_lock(game_key):
        game = st.get_game(game_key)
        if game is None:
            return {"settled": False, "round": 0, "skipped": []}
        players = st.list_players(game_key)
        active = [p for p in players if not p["is_away"]]
        if not active:
            return {"settled": False, "round": game["round"], "skipped": []}
        pending = [p["name"] for p in active if not p["has_submitted"]]
        if not skip_missing and pending:
            return {"settled": False, "round": game["round"], "skipped": pending}

        round_no = game["round"]
        await bus.publish(game_key, "llm_started", {"round": round_no})
        logger.info("room %s round %s 结算开始（skip_missing=%s，等待跳过=%s）",
                    game_key, round_no, skip_missing, pending)
        llm = LLMClient.from_config(max_tokens=game.get("max_tokens"))
        try:
            result = await run_round(game_key, llm=llm)
        except Exception as exc:  # 结算失败必须可见：广播失败事件并保持 collecting，玩家可重试提交
            logger.error("room %s round %s 结算失败：%s", game_key, round_no, exc)
            await bus.publish(game_key, "llm_finished",
                              {"round": round_no, "ok": False,
                               "error": f"结算失败：{exc}"})
            return {"settled": False, "round": round_no, "skipped": pending}
        if result.get("truncated"):
            _notify_llm_limit(st, game_key, result)
        await _broadcast_round_result(request, game_key, result)
        await bus.publish(game_key, "llm_finished",
                          {"round": round_no, "ok": True, "error": ""})
        logger.info("room %s round %s 结算完成", game_key, round_no)
        new_round = roundman.advance_game(game_key)
        data = {"round": new_round, "phase": "collecting"}
        await bus.publish(game_key, "turn_advanced", data)
        await bus.publish(game_key, "round_started", data)
        return {"settled": True, "round": new_round, "skipped": pending}


# ---------------- 局内聊天（M7 额外任务） ----------------

@router.post("/{game_key}/chat")
async def chat(game_key: str, body: ChatBody, request: Request) -> dict:
    """局内聊天：纯文本或携带 expr 联掷（骰果入审计并随消息展示）。

    消息落 messages 表（kind=chat，刷新可恢复），并广播 `chat` 事件。
    """
    st, game = _room_or_404(game_key)
    player = player_from_token(request, game_key)
    text = body.text.strip()
    expr = (body.expr or "").strip()
    if not text and not expr:
        raise HTTPException(status_code=400, detail="聊天消息或骰子表达式至少填一项")
    payload: dict = {"uid": player["uid"], "name": player["name"],
                     "text": text, "ts": roundman.now_ms()}
    if expr:
        try:
            result = roll_expr(expr, by=player["name"], why="聊天掷骰", no_log=True)
        except ValueError as e:
            raise HTTPException(status_code=400,
                                detail=f"非法的骰子表达式: {e}") from None
        st.add_dice_log(game_key, kind="roll", payload={
            **result, "by": player["name"], "why": "聊天掷骰", "from_chat": True,
        }, round_no=game["round"])
        payload.update({"expr": expr, "total": result["total"],
                        "rolls": result["rolls"]})
    st.add_message(game_key, game["round"], "chat", payload)
    bus: EventBus = request.app.state.bus
    await bus.publish(game_key, "chat", payload)
    return {"accepted": True, "message": payload}


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
    """推进回合（M8R5 语义 2.0，E3n 定案：提交不再自动推进）。

    - 活跃玩家全部已提交 → 任何玩家或房主均可触发，正常结算进入下一回合。
    - 未全员提交 → 仅房主可强制推进：以已提交行动立即结算，未提交者按
      「本轮无行动」跳过（settle_skipped 广播），已提交行动绝不丢弃。
    """
    st, game = _room_or_404(game_key)
    _player, is_host = _identify_requester(request, game_key)
    players = st.list_players(game_key)
    active = [p for p in players if not p["is_away"]]
    all_submitted = bool(active) and all(p["has_submitted"] for p in active)

    if not all_submitted and not is_host:
        pending = [p["name"] for p in active if not p["has_submitted"]]
        raise HTTPException(
            status_code=403,
            detail=f"还有玩家未提交行动（{', '.join(pending)}），仅房主可强制推进")

    res = await _settle_and_advance(request, game_key,
                                    skip_missing=not all_submitted)
    bus: EventBus = request.app.state.bus
    if not res["settled"]:
        # 兜底：无活跃玩家等异常情形 → 退回纯跳号
        logger.warning("room %s 推进未结算（settled=False），退回纯跳号", game_key)
        new_round = roundman.advance_game(game_key)
        data = {"round": new_round, "phase": "collecting"}
        await bus.publish(game_key, "turn_advanced", data)
        await bus.publish(game_key, "round_started", data)
        return {"triggered": True, "round": new_round, "skipped": []}
    if res["skipped"]:
        await bus.publish(game_key, "settle_skipped",
                          {"round": res["round"], "names": res["skipped"]})
    return {"triggered": True, "round": res["round"], "skipped": res["skipped"]}


@router.delete("/{game_key}")
async def close_game(game_key: str, request: Request) -> dict:
    """房主关闭房间（M8R5，需 X-Host-Token）：软关闭。

    phase 置 closed 并广播 room_closed；数据保留（db 不物理删除，清理留待
    管理端）。关闭后 join 被拒绝，在线玩家经 room_closed 事件跳回首页。
    """
    host_from_token(request, game_key)
    st, game = _room_or_404(game_key)
    if game.get("phase") == "closed":
        return {"closed": True, "game_key": game_key}
    st.update_game(game_key, phase="closed")
    logger.info("room %s 已被房主关闭", game_key)
    bus: EventBus = request.app.state.bus
    await bus.publish(game_key, "room_closed", {"game_key": game_key})
    return {"closed": True, "game_key": game_key}


@router.get("/{game_key}/my-action")
def my_action(game_key: str, request: Request) -> dict:
    """查自己本轮已提交的行动（M8R5 行动回显：提交后与刷新后都能确认写了什么）。"""
    st, game = _room_or_404(game_key)
    player = player_from_token(request, game_key)
    latest = st.latest_actions(game_key, game["round"])
    info = latest.get(player["uid"])
    return {"round": game["round"],
            "text": info["text"] if info else None,
            "action_version": info["action_version"] if info else None}


@router.post("/{game_key}/llm-limit")
async def set_llm_limit(game_key: str, body: LlmLimitBody, request: Request) -> dict:
    """房主调整本局 LLM 输出上限（需 X-Host-Token；1000–32000）。

    达到上限被截断时（llm_limit_hit 事件 + system 消息）房主可调高；
    广播 llm_limit_changed 同步所有在线玩家。
    """
    st, _ = _room_or_404(game_key)
    host_from_token(request, game_key)
    if not (MAX_TOKENS_MIN <= body.max_tokens <= MAX_TOKENS_MAX):
        raise HTTPException(
            status_code=400,
            detail=f"max_tokens 需在 {MAX_TOKENS_MIN}–{MAX_TOKENS_MAX} 之间")
    st.update_game(game_key, max_tokens=body.max_tokens)
    bus: EventBus = request.app.state.bus
    await bus.publish(game_key, "llm_limit_changed", {"max_tokens": body.max_tokens})
    return {"max_tokens": body.max_tokens}


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
