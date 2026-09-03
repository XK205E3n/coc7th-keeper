# -*- coding: utf-8 -*-
"""REST 全链路冒烟 + SSE 测试（M1 验收：
curl 可完成 建房间→加入→建卡→掷骰→查审计；双 SSE 连接广播与断线重连回放）。"""
from __future__ import annotations

import json
import threading
import time

import httpx
import pytest


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_full_flow_create_join_build_roll_audit(client):
    # 1) 创建房间
    r = client.post("/api/games", json={
        "name": "惊魂之夜", "rule": "coc7", "module_id": "the-haunting",
        "host_name": "房主",
    })
    assert r.status_code == 200, r.text
    d = r.json()
    key, host_token = d["game_key"], d["host_token"]

    # 创建者 = 房主玩家
    view = client.get(f"/api/games/{key}").json()["game"]
    assert any(p["is_host"] for p in view["players"])
    assert view["module_id"] == "the-haunting"

    # 2) 加入（M5：需邀请凭证 X-Join-Token）
    join_h = {"X-Join-Token": d["invite_token"]}
    r = client.post(f"/api/games/{key}/join", json={"name": "爱丽丝"}, headers=join_h)
    assert r.status_code == 200, r.text
    joined = r.json()
    player_token, uid = joined["player_token"], joined["player"]["uid"]
    headers = {"X-Player-Token": player_token}

    # 同名冲突
    assert client.post(f"/api/games/{key}/join", json={"name": "爱丽丝"},
                       headers=join_h).status_code == 409
    # 房间不存在
    assert client.post("/api/games/nope/join", json={"name": "x"}).status_code == 404

    # 3) 建卡（auto）：爱丽丝
    r = client.post(f"/api/games/{key}/characters",
                    json={"action": "auto", "name": "爱丽丝·卡特"}, headers=headers)
    assert r.status_code == 200, r.text
    char = r.json()["character"]
    assert char["schema"] == "coc7-character/v1"
    assert char["name"] == "爱丽丝·卡特"

    # 鲍勃加入并手动建卡（characters 表按 uid 主键：每人一张卡）
    r = client.post(f"/api/games/{key}/join", json={"name": "鲍勃"}, headers=join_h)
    bob_token = r.json()["player_token"]
    bob_headers = {"X-Player-Token": bob_token}
    r = client.post(f"/api/games/{key}/characters",
                    json={"character": {"schema": "coc7-character/v1", "name": "手动卡",
                          "attributes": {"STR": 50}, "derived": {"HP": 10},
                          "skills": {}, "inventory": []}, "name": "手动卡"},
                    headers=bob_headers)
    assert r.status_code == 200

    # 角色查询：两张卡
    r = client.get(f"/api/games/{key}/characters", headers=headers)
    assert len(r.json()["characters"]) == 2
    r = client.get(f"/api/games/{key}/characters/爱丽丝·卡特", headers=headers)
    assert r.json()["character"]["name"] == "爱丽丝·卡特"
    assert client.get(f"/api/games/{key}/characters/不存在", headers=headers).status_code == 404

    # 4) 提交行动（修改递增版本）
    r = client.post(f"/api/games/{key}/actions", json={"text": "我检查柜子"}, headers=headers)
    assert r.json()["accepted"] is True and r.json()["action_version"] == 1
    r = client.post(f"/api/games/{key}/actions", json={"text": "我改检查书桌"}, headers=headers)
    assert r.json()["action_version"] == 2

    # 5) 掷骰 + 审计
    r = client.post(f"/api/games/{key}/roll",
                    json={"expr": "1d100", "why": "自由掷骰"}, headers=headers)
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert 1 <= result["total"] <= 100 and result["kind"] == "roll"
    assert r.json()["result"].get("by") == "爱丽丝"

    r = client.get(f"/api/games/{key}/audit?last=10", headers=headers)
    audit = r.json()["audit"]
    assert len(audit) >= 1 and audit[-1]["kind"] == "roll"
    assert audit[-1]["payload"]["expr"] == "1d100"

    # 6) 房主强制推进
    r = client.post(f"/api/games/{key}/advance", headers={"X-Host-Token": host_token})
    assert r.status_code == 200 and r.json()["triggered"] and r.json()["round"] == 1
    # M8R5：新回合无人提交，玩家 token 触发推进 → 403（已认证但仅房主可强制推进）
    assert client.post(f"/api/games/{key}/advance", headers=headers).status_code == 403

    # 7) 鉴权与参数校验
    assert client.post(f"/api/games/{key}/roll", json={"expr": "1d100"}).status_code == 401
    assert client.post(f"/api/games/{key}/roll",
                       json={"expr": "非法!"}, headers=headers).status_code == 400
    assert client.post(f"/api/games/{key}/actions", json={"text": ""},
                       headers=headers).status_code == 422 or 400

    # 8) 玩家公共视图不含 KP 字段（隐私铁律）
    body = json.dumps(client.get(f"/api/games/{key}", headers=headers).json())
    for forbidden in ("kp_notes", "dice_log", "password_hash"):
        assert forbidden not in body


def test_create_module_validation(client):
    r = client.post("/api/games", json={"name": "坏模组", "module_id": "不存在的模组"})
    assert r.status_code == 400


def test_modules_api(client):
    r = client.get("/api/modules")
    assert r.status_code == 200
    ids = {m["id"] for m in r.json()["modules"]}
    assert "the-haunting" in ids and "toy-dancer-comes" in ids

    r = client.get("/api/modules/the-haunting/scenes")
    assert r.status_code == 200
    assert len(r.json()["scenes"]) == 7
    assert r.json()["scene_flow"][0] == "s01"

    r = client.get("/api/modules/the-haunting/scenes/s06")
    assert "joseph_ghost" in r.json()["scene"]["npcs"]
    assert client.get("/api/modules/the-haunting/scenes/nope").status_code == 404
    assert client.get("/api/modules/nope").status_code == 404


def test_pregens_api(client):
    r = client.get("/api/modules/the-haunting/pregens")
    assert r.status_code == 200
    assert len(r.json()["pregens"]) == 2


def test_handout_file_api(client):
    r = client.get("/api/modules/toy-dancer-comes/handouts/maps/qiulin-court-map.jpeg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")
    assert len(r.content) > 0
    # 越界/缺失 → 404
    assert client.get("/api/modules/toy-dancer-comes/handouts/../meta.json").status_code == 404
    assert client.get("/api/modules/toy-dancer-comes/handouts/nope.png").status_code == 404


# ---------------- SSE 事件总线（M1.7） ----------------
# 两层验证：
#  ① 总线级（anyio 纯异步）：双连接同时收广播、perception 定向过滤、断线重连回放
#  ② HTTP 端到端（真实 uvicorn 服务器）：回放 + 实时推送 + 事件 wire 格式


@pytest.mark.anyio
async def test_event_bus_broadcast_target_and_replay():
    """两个订阅者同时收广播；私密事件只推给目标；断开重连后回放（私密只回放给本人）。"""
    import asyncio

    from server.sse import EventBus
    bus = EventBus(history_size=50)

    # ---- 断线重连回放：历史先于订阅产生 → 回放即时且有限 ----
    await bus.publish("g1", "dice_result", {"total": 42})
    await bus.publish("g1", "perception", {"text": "给1号的秘密"}, to_uid="u1")
    await bus.publish("g1", "turn_advanced", {"round": 1})
    await bus.publish("g1", "perception", {"text": "给2号的秘密"}, to_uid="u2")

    async def replay(uid: str, n: int) -> list[tuple[str, str | None]]:
        gen = bus.subscribe("g1", uid=uid)
        out = []
        for _ in range(n):
            ev = await anext(gen)
            out.append((ev["event"], ev.get("to_uid")))
        await gen.aclose()
        return out

    a = await replay("u1", 3)
    assert [e for e, _ in a] == ["dice_result", "perception", "turn_advanced"]
    assert a[1][1] == "u1"                       # 1 号能回放自己的私密感知

    b = await replay("u2", 3)
    assert [e for e, _ in b] == ["dice_result", "turn_advanced", "perception"]
    assert b[2][1] == "u2"                       # 2 号能回放自己的私密感知

    c = await replay("u3", 2)
    assert [e for e, _ in c] == ["dice_result", "turn_advanced"]
    # 3 号看不到任何私密事件（隐私铁律：回放同样按 to_uid 过滤）

    # ---- 两个订阅者同时在线：广播都收到，私密只推给目标 ----
    async def live_collect(uid: str, expect: int) -> list[dict]:
        gen = bus.subscribe("g2", uid=uid)
        events = []
        try:
            while len(events) < expect:
                events.append(await asyncio.wait_for(anext(gen), timeout=5))
        finally:
            await gen.aclose()
        return events

    t1 = asyncio.create_task(live_collect("u1", 2))
    t2 = asyncio.create_task(live_collect("u2", 1))
    await asyncio.sleep(0.1)                     # 让两个生成器先进入监听态
    await bus.publish("g2", "dice_result", {"total": 7})
    await bus.publish("g2", "perception", {"text": "只给1号"}, to_uid="u1")

    ev1 = await asyncio.wait_for(t1, 10)
    ev2 = await asyncio.wait_for(t2, 10)
    assert [e["event"] for e in ev1] == ["dice_result", "perception"]
    assert [e["event"] for e in ev2] == ["dice_result"]          # u2 收不到私密


@pytest.mark.anyio
async def test_event_bus_heartbeat_format():
    from server.sse import format_sse
    assert format_sse({"event": "heartbeat", "data": {}}) == ": ping\n\n"
    wire = format_sse({"event": "dice_result", "data": {"total": 7}})
    assert wire.startswith("event: dice_result\ndata: ")
    assert '"total": 7' in wire


def _start_live_server():
    """在随机端口启动真实 uvicorn 服务器（线程内）。返回 base_url。"""
    import threading
    import time

    import uvicorn
    from server.main import app

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0,
                                           log_level="warning"))

    def run():
        server.run()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    for _ in range(200):                      # 最多等 10s
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "uvicorn 未能在超时内启动"
    port = server.servers[0].sockets[0].getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    return url, server, thread


def test_http_sse_replay_and_live():
    """真实服务器端到端：先掷骰入历史 → 连接 SSE 回放；连接存活期间再掷骰 → 实时收到。"""
    import httpx
    url, server, thread = _start_live_server()
    try:
        with httpx.Client(base_url=url, timeout=10) as c:
            r = c.post("/api/games", json={"name": "SSE实", "host_name": "房主"})
            assert r.status_code == 200
            key = r.json()["game_key"]
            r = c.post(f"/api/games/{key}/join", json={"name": "阿"},
                       headers={"X-Join-Token": r.json()["invite_token"]})
            token = r.json()["player_token"]
            headers = {"X-Player-Token": token}

            # 先掷骰 → dice_result 进回放缓冲
            assert c.post(f"/api/games/{key}/roll",
                          json={"expr": "1d100", "why": "第一条"}, headers=headers).status_code == 200

            with c.stream("GET", f"/api/games/{key}/events",
                          headers=headers, timeout=httpx.Timeout(15, read=5)) as resp:
                assert resp.status_code == 200
                assert resp.headers["content-type"].startswith("text/event-stream")
                it = resp.iter_lines()

                # 回放：应出现第一条 dice_result
                buf = []
                for line in it:
                    buf.append(line)
                    if any(l == "event: dice_result" for l in buf):
                        break
                assert any(l == "event: dice_result" for l in buf), buf

                # 连接存活期间再掷骰 → 实时收到第二条
                posted = {"done": False}

                def _post():
                    time.sleep(0.2)
                    c.post(f"/api/games/{key}/roll",
                           json={"expr": "2d6", "why": "第二条"}, headers=headers)
                    posted["done"] = True

                threading.Thread(target=_post, daemon=True).start()
                saw_live = False
                for line in it:
                    if line == "event: dice_result":
                        saw_live = True
                        break
                assert saw_live, "连接存活期间未实时收到第二条骰果"
                # SSE 事件可能先于 POST 响应到达 → 等 _post 线程确认请求已完成
                deadline = time.time() + 5
                while not posted["done"]:
                    assert time.time() < deadline, "第二次掷骰请求未完成"
                    time.sleep(0.05)
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_http_sse_action_and_advance_replay():
    """action_received / turn_advanced / round_started 事件经 HTTP 落库并回放。"""
    import httpx
    url, server, thread = _start_live_server()
    try:
        with httpx.Client(base_url=url, timeout=10) as c:
            r = c.post("/api/games", json={"name": "SSE实2", "host_name": "房主"})
            key, host_token = r.json()["game_key"], r.json()["host_token"]
            r = c.post(f"/api/games/{key}/join", json={"name": "阿"},
                       headers={"X-Join-Token": r.json()["invite_token"]})
            token = r.json()["player_token"]
            headers = {"X-Player-Token": token}

            # 先制造事件：提交行动 + 房主推进
            assert c.post(f"/api/games/{key}/actions",
                          json={"text": "我推开门"}, headers=headers).status_code == 200
            assert c.post(f"/api/games/{key}/advance",
                          headers={"X-Host-Token": host_token}).status_code == 200

            with c.stream("GET", f"/api/games/{key}/events",
                          headers=headers, timeout=httpx.Timeout(15, read=5)) as resp:
                wanted = {"event: action_received", "event: turn_advanced",
                          "event: round_started"}
                seen = set()
                for line in resp.iter_lines():
                    if line in wanted:
                        seen.add(line)
                        if seen == wanted:
                            break
                assert seen == wanted, f"缺少事件: {wanted - seen}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
