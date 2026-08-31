# -*- coding: utf-8 -*-
"""M7 额外任务测试：局内聊天（文本 / 联掷分享 / 审计 / SSE 广播）+ 线索台账。"""
from __future__ import annotations

import httpx
import pytest

from server import state_apply, store
from server.tests.test_api import _start_live_server


def test_chat_text(client):
    d = client.post("/api/games", json={"name": "聊天团", "host_name": "爱丽丝"}).json()
    key = d["game_key"]
    headers = {"X-Player-Token": d["host_token"]}
    r = client.post(f"/api/games/{key}/chat", json={"text": "大家好"}, headers=headers)
    assert r.status_code == 200 and r.json()["accepted"] is True
    assert r.json()["message"]["text"] == "大家好"
    # 无 token → 401
    assert client.post(f"/api/games/{key}/chat", json={"text": "hi"}).status_code == 401
    # 文本与 expr 都空 → 400
    assert client.post(f"/api/games/{key}/chat", json={"text": "  "},
                       headers=headers).status_code == 400


def test_chat_roll_share(client):
    """携带 expr：骰果入 dice_log 审计，聊天消息带结果，落 messages(kind=chat)。"""
    d = client.post("/api/games", json={"name": "聊天骰", "host_name": "爱丽丝"}).json()
    key = d["game_key"]
    headers = {"X-Player-Token": d["host_token"]}
    r = client.post(f"/api/games/{key}/chat",
                    json={"text": "我掷个骰看看", "expr": "1d100"}, headers=headers)
    assert r.status_code == 200
    msg = r.json()["message"]
    assert msg["expr"] == "1d100" and 1 <= msg["total"] <= 100
    assert "rolls" in msg
    # 审计可查
    audit = client.get(f"/api/games/{key}/audit?last=5", headers=headers).json()["audit"]
    assert audit and audit[-1]["kind"] == "roll"
    assert audit[-1]["payload"].get("from_chat") is True
    # 消息落库（刷新恢复）
    msgs = client.get(f"/api/games/{key}/messages?last=20", headers=headers).json()["messages"]
    chats = [m for m in msgs if m["kind"] == "chat"]
    assert chats and chats[-1]["payload"]["expr"] == "1d100"
    # 非法表达式 → 400
    assert client.post(f"/api/games/{key}/chat",
                       json={"text": "x", "expr": "abc"}, headers=headers).status_code == 400


def test_chat_event_broadcast_live():
    url, server, thread = _start_live_server()
    try:
        with httpx.Client(base_url=url, timeout=10) as c:
            r = c.post("/api/games", json={"name": "聊天SSE", "host_name": "房主"})
            key = r.json()["game_key"]
            join = c.post(f"/api/games/{key}/join", json={"name": "阿"},
                          headers={"X-Join-Token": r.json()["invite_token"]}).json()
            token = join["player_token"]
            with c.stream(f"GET", f"/api/games/{key}/events?token={token}",
                          timeout=httpx.Timeout(15, read=5)) as resp:
                it = resp.iter_lines()
                r2 = c.post(f"/api/games/{key}/chat",
                            json={"text": "来啦", "expr": "2d6"},
                            headers={"X-Player-Token": token})
                assert r2.status_code == 200
                seen = set()
                for line in it:
                    if line == "event: chat":
                        seen.add(line)
                        break
                assert "event: chat" in seen
    finally:
        server.should_exit = True
        thread.join(timeout=5)


# ---------------- M7 建议：线索台账 ----------------

def test_clue_ledger_init_on_create(client):
    """建团（带模组）初始化线索台账副本；公共视图不泄露。"""
    import json as _json
    d = client.post("/api/games", json={
        "name": "台账团", "module_id": "the-haunting", "host_name": "房主"}).json()
    key = d["game_key"]
    from server import store
    ledger = store.get_store(key).list_clue_ledger(key)
    assert len(ledger) >= 10                      # the-haunting clues.md 有 C-01..C-16
    assert all(x["state"] == "locked" for x in ledger)
    assert any(x["clue_id"] == "C-01" for x in ledger)
    body = _json.dumps(client.get(f"/api/games/{key}").json())
    assert "clue_ledger" not in body              # 台账只供管理员查询


def test_clue_ledger_unlock_on_gain(client, monkeypatch):
    """获得线索时台账状态刷新（locked→unlocked + 获得者）。"""
    _enable_dev(monkeypatch)
    d = client.post("/api/games", json={
        "name": "解锁团", "module_id": "toy-dancer-comes", "host_name": "爱丽丝"}).json()
    key = d["game_key"]
    headers = {"X-Player-Token": d["host_token"]}
    assert client.post(f"/api/games/{key}/characters",
                       json={"action": "auto", "name": "爱丽丝"},
                       headers=headers).status_code == 200
    # 通过管线让 LLM 兜底给线索不现实——直接调 state_apply 应用一条线索变动
    from server import state_apply as sa
    out = sa.apply_state_changes(
        store.get_store(key), key, 0,
        [{"type": "clue", "player_uid": d["host_uid"],
          "clue_id": "C-01", "text": "半露木构架式建筑知识"}],
        module_id="toy-dancer-comes")
    assert len(out["applied"]) == 1
    ledger = store.get_store(key).list_clue_ledger(key, state="unlocked")
    assert any(x["clue_id"] == "C-01" for x in ledger)
    row = [x for x in ledger if x["clue_id"] == "C-01"][0]
    assert row["acquired_by"] == d["host_uid"] and row["acquired_at"]
    # 重复获得幂等（第二次不再变化）
    sa.apply_state_changes(
        store.get_store(key), key, 0,
        [{"type": "clue", "player_uid": d["host_uid"],
          "clue_id": "C-01", "text": "x"}], module_id="toy-dancer-comes")
    assert len(store.get_store(key).list_clue_ledger(key, state="unlocked")) == 1


def test_dev_clue_ledger_query(client, monkeypatch):
    """管理员（dev_token）可查线索台账与状态统计。"""
    _enable_dev(monkeypatch)
    d = client.post("/api/games", json={
        "name": "查询团", "module_id": "the-haunting", "host_name": "房主"}).json()
    key = d["game_key"]
    dev = {"X-Dev-Token": "dev-secret-1"}
    r = client.get(f"/api/dev/games/{key}/clues", headers=dev)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 10 and body["unlocked"] == 0
    assert body["clues"][0]["clue_id"]
    # 玩家身份查不到台账
    assert client.get(f"/api/dev/games/{key}/clues",
                      headers={"X-Player-Token": d["host_token"]}).status_code == 401


def _enable_dev(monkeypatch, token: str = "dev-secret-1") -> None:
    """写一个带 dev_token 的 config.json 到当前 DATA_DIR。"""
    import json
    from server import config as cfg
    data_dir = cfg.data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = cfg.default_config()
    payload["dev_token"] = token
    (data_dir / "config.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------- M7 建议（更新）：线索台账注入 KP 上下文 ----------------

@pytest.mark.anyio
async def test_clue_ledger_injected_to_kp_context(client):
    """守密人（LLM）上下文中可见线索台账；获得线索后状态更新为已获得。"""
    import json as _json

    from server.gm.pipeline import run_round

    d = client.post("/api/games", json={
        "name": "KP台账", "module_id": "the-haunting", "host_name": "爱丽丝"}).json()
    key, uid = d["game_key"], d["host_uid"]
    headers = {"X-Player-Token": d["host_token"]}
    assert client.post(f"/api/games/{key}/characters",
                       json={"action": "auto", "name": "爱丽丝"},
                       headers=headers).status_code == 200
    client.post(f"/api/games/{key}/actions", json={"text": "我四处看看"}, headers=headers)

    captured: dict = {}

    class FakeLLM:
        available = True
        async def chat(self, messages, **kw):
            captured["content"] = messages[-1]["content"]
            if "裁判阶段" in messages[-1]["content"]:
                return _json.dumps({"dice_checks": [], "private_notes": ""})
            return _json.dumps({"narrative": "无事发生", "state_changes": []})

    await run_round(key, llm=FakeLLM())
    content = captured["content"]
    assert "线索台账" in content and "守密人视角" in content
    assert "[C-01]" in content and "[未获得]" in content

    # 获得 C-01 后再跑一轮：台账显示已获得
    state_apply.apply_state_changes(
        store.get_store(key), key, 1,
        [{"type": "clue", "player_uid": uid, "clue_id": "C-01", "text": "来信"}],
        module_id="the-haunting")
    await run_round(key, llm=FakeLLM())
    assert "[C-01] [已获得]" in captured["content"]
