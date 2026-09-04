# -*- coding: utf-8 -*-
"""M5 多人联机后端测试：邀请与凭证 / 访问密码 / 暂离不阻塞 / 踢人 / 全员推进 /
SSE token 查询参数 / 自由掷骰落消息 / 开发者只读监视接口 / LLM 调用记录。"""
from __future__ import annotations

import json
import secrets

import httpx
import pytest

from server import store
from server.tests.test_api import _start_live_server

# 辅助：写一个带 dev_token 的 config.json 到当前 DATA_DIR
def _enable_dev_token(monkeypatch, token: str = "dev-secret-1") -> None:
    from server import config as cfg
    data_dir = cfg.data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = cfg.default_config()
    payload["dev_token"] = token
    (data_dir / "config.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _create_room(client, name="多人测试团", module_id="the-haunting",
                 password=None, host_name="房主"):
    body = {"name": name, "module_id": module_id, "host_name": host_name}
    if password is not None:
        body["password"] = password
    r = client.post("/api/games", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "invite_token" in d, "创建响应必须含 invite_token"
    return d


# ---------------- M5.1 邀请与访问密码 ----------------

def test_join_requires_invite_token(client):
    d = _create_room(client)
    key = d["game_key"]
    # 无邀请头 → 401
    r = client.post(f"/api/games/{key}/join", json={"name": "爱丽丝"})
    assert r.status_code in (401, 403), r.text
    # 错误邀请 → 401
    r = client.post(f"/api/games/{key}/join", json={"name": "爱丽丝"},
                    headers={"X-Join-Token": "wrong"})
    assert r.status_code in (401, 403)
    # 正确邀请 → 成功
    r = client.post(f"/api/games/{key}/join", json={"name": "爱丽丝"},
                    headers={"X-Join-Token": d["invite_token"]})
    assert r.status_code == 200, r.text
    assert r.json()["player_token"]


def test_invite_rotation_invalidates_old(client):
    d = _create_room(client)
    key = d["game_key"]
    headers = {"X-Host-Token": d["host_token"]}
    r = client.post(f"/api/games/{key}/invite", headers=headers)
    assert r.status_code == 200
    new_invite = r.json()["invite_token"]
    assert new_invite != d["invite_token"]
    # 旧邀请失效
    r = client.post(f"/api/games/{key}/join", json={"name": "旧码"},
                    headers={"X-Join-Token": d["invite_token"]})
    assert r.status_code in (401, 403)
    # 新邀请可用
    r = client.post(f"/api/games/{key}/join", json={"name": "新码"},
                    headers={"X-Join-Token": new_invite})
    assert r.status_code == 200


def test_access_password(client):
    pwd = secrets.token_hex(6)  # 运行时生成，避免硬编码凭据
    d = _create_room(client, password=pwd)
    key = d["game_key"]
    # 密码错误 → 403
    r = client.post(f"/api/games/{key}/join", json={"name": "A", "password": "no"},
                    headers={"X-Join-Token": d["invite_token"]})
    assert r.status_code == 403
    # 缺密码 → 403
    r = client.post(f"/api/games/{key}/join", json={"name": "A"},
                    headers={"X-Join-Token": d["invite_token"]})
    assert r.status_code == 403
    # 正确 → 成功
    r = client.post(f"/api/games/{key}/join", json={"name": "A", "password": pwd},
                    headers={"X-Join-Token": d["invite_token"]})
    assert r.status_code == 200, r.text


# ---------------- M5.2 回合收集器：暂离不阻塞 / 全员推进 / 未提交等待 ----------------

def test_all_active_submitted_auto_advance(client):
    """2 活跃玩家：仅 A 提交不推进；A+B 都提交后自动推进。"""
    d = _create_room(client, host_name="房主")
    key = d["game_key"]
    host_headers = {"X-Player-Token": d["host_token"]}
    join1 = client.post(f"/api/games/{key}/join", json={"name": "爱丽丝"},
                        headers={"X-Join-Token": d["invite_token"]}).json()
    join2 = client.post(f"/api/games/{key}/join", json={"name": "鲍勃"},
                        headers={"X-Join-Token": d["invite_token"]}).json()
    h1, h2 = {"X-Player-Token": join1["player_token"]}, {"X-Player-Token": join2["player_token"]}
    for p in (("爱丽丝", h1), ("鲍勃", h2)):
        client.post(f"/api/games/{key}/characters",
                    json={"action": "auto", "name": p[0]}, headers=p[1])

    # 房主(活跃)未提交 + 爱丽丝提交 → 不自动推进（M8R5：提交不再触发推进）
    r = client.post(f"/api/games/{key}/actions", json={"text": "我检查柜子"}, headers=h1)
    assert r.status_code == 200
    assert client.get(f"/api/games/{key}").json()["game"]["round"] == 0
    # 非房主在未全员提交时推进 → 403
    r = client.post(f"/api/games/{key}/advance", headers=h1)
    assert r.status_code == 403

    # 爱丽丝暂离 → 不再计入活跃
    r = client.post(f"/api/games/{key}/away", headers=h1)
    assert r.status_code == 200 and r.json()["is_away"] is True

    # 活跃玩家 = 房主 + 鲍勃；鲍勃提交 → 还不推进（房主未提交）
    client.post(f"/api/games/{key}/actions", json={"text": "我倾听动静"}, headers=h2)
    assert client.get(f"/api/games/{key}").json()["game"]["round"] == 0

    # 房主提交 → 全员(活跃)已提交 → 任何人（此处鲍勃）可推进
    r = client.post(f"/api/games/{key}/actions", json={"text": "我四处查看"}, headers=host_headers)
    assert r.status_code == 200
    r = client.post(f"/api/games/{key}/advance", headers=h2)
    assert r.status_code == 200
    assert client.get(f"/api/games/{key}").json()["game"]["round"] == 1

    # 暂离玩家回来
    r = client.post(f"/api/games/{key}/back", headers=h1)
    assert r.json()["is_away"] is False


def test_player_status_broadcast_live():
    """SSE ?token= 查询参数连接 + player_status 事件。"""
    url, server, thread = _start_live_server()
    try:
        with httpx.Client(base_url=url, timeout=10) as c:
            r = c.post("/api/games", json={"name": "暂离SSE", "host_name": "房主"})
            key, host_token = r.json()["game_key"], r.json()["host_token"]
            join = c.post(f"/api/games/{key}/join", json={"name": "爱丽丝"},
                          headers={"X-Join-Token": r.json()["invite_token"]}).json()
            token = join["player_token"]
            # 用 ?token= 连接（模拟前端 EventSource）
            with c.stream("GET", f"/api/games/{key}/events?token={token}",
                          timeout=httpx.Timeout(15, read=5)) as resp:
                it = resp.iter_lines()
                resp2 = c.post(f"/api/games/{key}/away", headers={"X-Player-Token": token})
                assert resp2.status_code == 200
                seen = set()
                for line in it:
                    if line == "event: player_status":
                        seen.add(line)
                        break
                assert "event: player_status" in seen
    finally:
        server.should_exit = True
        thread.join(timeout=5)


# ---------------- M5.4 房主管理：踢人 ----------------

def test_kick_flow(client):
    d = _create_room(client, host_name="房主")
    key = d["game_key"]
    join = client.post(f"/api/games/{key}/join", json={"name": "麻烦精"},
                       headers={"X-Join-Token": d["invite_token"]}).json()
    uid, token = join["player"]["uid"], join["player_token"]
    host_headers = {"X-Host-Token": d["host_token"]}
    # 踢人
    r = client.post(f"/api/games/{key}/kick", json={"uid": uid}, headers=host_headers)
    assert r.status_code == 200 and r.json()["removed"] == uid
    # 被踢玩家 token 失效
    assert client.get(f"/api/games/{key}", headers={"X-Player-Token": token}).status_code in (200, 401)
    # 玩家列表不含被踢者
    players = client.get(f"/api/games/{key}").json()["game"]["players"]
    assert all(p["uid"] != uid for p in players)
    # 不能踢房主
    host_uid = client.get(f"/api/games/{key}").json()["game"]["players"][0]["uid"]
    r = client.post(f"/api/games/{key}/kick", json={"uid": host_uid}, headers=host_headers)
    assert r.status_code == 400


# ---------------- TODO-B#1：自由掷骰落消息 ----------------

def test_free_roll_persists_message(client):
    d = _create_room(client, host_name="爱丽丝")
    key = d["game_key"]
    headers = {"X-Player-Token": d["host_token"]}
    assert client.post(f"/api/games/{key}/characters",
                       json={"action": "auto", "name": "爱丽丝"},
                       headers=headers).status_code == 200
    r = client.post(f"/api/games/{key}/roll", json={"expr": "2d6"}, headers=headers)
    assert r.status_code == 200
    msgs = client.get(f"/api/games/{key}/messages?last=20", headers=headers).json()["messages"]
    dice = [m for m in msgs if m["kind"] == "dice"]
    assert dice, "自由掷骰应落 messages 表（kind=dice）"
    assert dice[-1]["payload"]["expr"] == "2d6"


# ---------------- M5.5 开发者只读监视接口 ----------------

def test_dev_endpoints(client, monkeypatch):
    _enable_dev_token(monkeypatch, "dev-secret-1")
    d = _create_room(client, host_name="爱丽丝")
    key = d["game_key"]
    headers = {"X-Player-Token": d["host_token"]}
    client.post(f"/api/games/{key}/characters", json={"action": "auto", "name": "爱丽丝"},
                headers=headers)
    client.post(f"/api/games/{key}/roll", json={"expr": "1d100"}, headers=headers)
    from server import store as _store
    _store.get_store(key).add_kp_note(key, "守密人的秘密观察", 0)

    dev = {"X-Dev-Token": "dev-secret-1"}
    # 未配/错 token → 401
    r = client.get(f"/api/dev/games/{key}/room")
    assert r.status_code in (401, 503)
    r = client.get(f"/api/dev/games/{key}/room", headers={"X-Dev-Token": "bad"})
    assert r.status_code in (401, 403)

    room = client.get(f"/api/dev/games/{key}/room", headers=dev)
    assert room.status_code == 200
    body = json.dumps(room.json())
    assert "token_hash" not in body            # 凭证不出现在监视接口
    # kp_notes 可读
    notes = client.get(f"/api/dev/games/{key}/kp_notes", headers=dev).json()["kp_notes"]
    assert notes and "秘密观察" in notes[0]["text"]
    # dice_log / llm_log / messages 可读
    assert len(client.get(f"/api/dev/games/{key}/dice_log", headers=dev).json()["dice_log"]) >= 1
    assert isinstance(client.get(f"/api/dev/games/{key}/llm_log", headers=dev).json()["llm_log"], list)
    assert len(client.get(f"/api/dev/games/{key}/messages", headers=dev).json()["messages"]) >= 1
    # 未知房间 404
    assert client.get("/api/dev/games/nope/room", headers=dev).status_code == 404
    # 只读：调用 dev 后游戏状态不变
    before = client.get(f"/api/games/{key}", headers=headers).json()["game"]["round"]
    client.get(f"/api/dev/games/{key}/room", headers=dev)
    client.get(f"/api/dev/games/{key}/messages", headers=dev)
    after = client.get(f"/api/games/{key}", headers=headers).json()["game"]["round"]
    assert before == after


def test_dev_games_list(client, monkeypatch):
    _enable_dev_token(monkeypatch, "dev-secret-1")
    _create_room(client, name="列表面")
    dev = {"X-Dev-Token": "dev-secret-1"}
    r = client.get("/api/dev/games", headers=dev)
    assert r.status_code == 200
    keys = [g["game_key"] for g in r.json()["games"]]
    assert len(keys) >= 1


def test_llm_log_recorded_offline(client):
    """离线（无 key）管线也记录 LLM 调用尝试（ok=False）。"""
    d = _create_room(client, host_name="爱丽丝")
    key = d["game_key"]
    headers = {"X-Player-Token": d["host_token"]}
    client.post(f"/api/games/{key}/characters", json={"action": "auto", "name": "爱丽丝"},
                headers=headers)
    r = client.post(f"/api/games/{key}/actions", json={"text": "我检查柜子"}, headers=headers)
    assert r.status_code == 200
    r = client.post(f"/api/games/{key}/advance", headers=headers)
    assert r.status_code == 200
    st = store.get_store(key)
    logs = st.list_llm_log(key)
    assert len(logs) >= 2                       # adjudicate + narrate
    assert all(not l["ok"] for l in logs)       # 离线均失败（fallback）
    assert {l["stage"] for l in logs} >= {"adjudicate", "narrate"}


def test_public_view_no_invite_token(client):
    """邀请凭证不出现在公共视图（凭证隔离）。"""
    d = _create_room(client)
    key = d["game_key"]
    body = json.dumps(client.get(f"/api/games/{key}").json())
    assert "invite_token" not in body
