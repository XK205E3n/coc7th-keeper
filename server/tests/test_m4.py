# -*- coding: utf-8 -*-
"""M4 单人 Web 闭环测试：开局注入 / 消息端点 / 单人自动推进 / 事件无 KP 泄漏。"""
from __future__ import annotations

import json

import httpx
import pytest

from server.tests.test_api import _start_live_server


def test_create_with_module_injects_opening(client):
    r = client.post("/api/games", json={
        "name": "惊魂开局", "module_id": "the-haunting", "host_name": "房主"})
    assert r.status_code == 200
    key, host_token = r.json()["game_key"], r.json()["host_token"]
    headers = {"X-Player-Token": host_token}

    view = client.get(f"/api/games/{key}").json()["game"]
    assert view["current_scene"] == "s01"          # 首场景注入

    # 消息端点（无 token 401；有 token 返回开场消息）
    assert client.get(f"/api/games/{key}/messages").status_code == 401
    r = client.get(f"/api/games/{key}/messages", headers=headers)
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert any(m["kind"] == "scene" for m in msgs)
    scene_msg = [m for m in msgs if m["kind"] == "scene"][0]
    assert "s01" in json.dumps(scene_msg["payload"])

    # kp-notes 已注入守密人上下文，但公共视图/消息绝不含
    body = json.dumps(client.get(f"/api/games/{key}").json())
    assert "kp_notes" not in body
    assert "kp_notes" not in json.dumps(msgs)


def test_single_player_auto_advance_full_loop(client):
    """建卡 → 行动 → 自动推进 → 检定 → 叙事 → 落库（M4 验收核心链路）。"""
    r = client.post("/api/games", json={
        "name": "单人团", "module_id": "the-haunting", "host_name": "爱丽丝"})
    d = r.json()
    key, host_token = d["game_key"], d["host_token"]
    headers = {"X-Player-Token": host_token}

    # 建卡
    r = client.post(f"/api/games/{key}/characters",
                    json={"action": "auto", "name": "爱丽丝"}, headers=headers)
    assert r.status_code == 200
    char = r.json()["character"]
    assert char["schema"] == "coc7-character/v1"

    # 提交行动（M8R5：不再自动推进）→ 房主/玩家手动推进
    r = client.post(f"/api/games/{key}/actions",
                    json={"text": "我仔细检查这扇门（侦查）"}, headers=headers)
    assert r.status_code == 200
    adv = client.post(f"/api/games/{key}/advance", headers={"X-Host-Token": host_token})
    assert adv.status_code == 200 and adv.json()["triggered"] is True

    # 轮次推进 + 提交清空
    view = client.get(f"/api/games/{key}").json()["game"]
    assert view["round"] == 1
    assert all(not p["has_submitted"] for p in view["players"])

    # 叙事流落库（dice 卡片 + 叙事）
    msgs = client.get(f"/api/games/{key}/messages", headers=headers).json()["messages"]
    kinds = [m["kind"] for m in msgs]
    assert "dice" in kinds and "narration" in kinds

    # 审计可查
    audit = client.get(f"/api/games/{key}/audit?last=10", headers=headers).json()["audit"]
    assert len(audit) >= 1 and audit[-1]["kind"] in ("check", "san_check", "luck")

    # 失败措辞铁律：叙事不含禁用词
    nar = [m for m in msgs if m["kind"] == "narration"][-1]["payload"]["text"]
    for bad in ("没有异常", "没有发现异常", "其实你漏掉", "其实你没发现"):
        assert bad not in nar

    # 无 KP 泄漏
    assert "kp_notes" not in json.dumps(msgs)

    # 第二轮：提交 → 手动推进
    r = client.post(f"/api/games/{key}/actions",
                    json={"text": "我倾听门后的动静"}, headers=headers)
    assert r.status_code == 200
    client.post(f"/api/games/{key}/advance", headers={"X-Host-Token": host_token})
    assert client.get(f"/api/games/{key}").json()["game"]["round"] == 2


def test_auto_advance_requires_character(client):
    """未建卡就提交行动：自动推进仍应完成（无角色卡时状态应用跳过，不崩溃）。"""
    r = client.post("/api/games", json={"name": "无卡团", "host_name": "爱丽丝"})
    key, host_token = r.json()["game_key"], r.json()["host_token"]
    headers = {"X-Player-Token": host_token}
    r = client.post(f"/api/games/{key}/actions", json={"text": "我四处看看"}, headers=headers)
    assert r.status_code == 200
    adv = client.post(f"/api/games/{key}/advance", headers={"X-Host-Token": host_token})
    assert adv.status_code == 200 and adv.json()["triggered"] is True


def test_auto_advance_sse_events_live():
    """真实服务器：提交行动 → 自动推进 → SSE 收到 action/dice/narration/round_started。"""
    url, server, thread = _start_live_server()
    try:
        with httpx.Client(base_url=url, timeout=10) as c:
            r = c.post("/api/games", json={
                "name": "SSE自动", "module_id": "the-haunting", "host_name": "爱丽丝"})
            key, host_token = r.json()["game_key"], r.json()["host_token"]
            headers = {"X-Player-Token": host_token}
            assert c.post(f"/api/games/{key}/characters",
                          json={"action": "auto", "name": "爱丽丝"},
                          headers=headers).status_code == 200

            with c.stream("GET", f"/api/games/{key}/events",
                          headers=headers, timeout=httpx.Timeout(15, read=5)) as resp:
                it = resp.iter_lines()
                r = c.post(f"/api/games/{key}/actions",
                           json={"text": "我仔细检查这扇门"}, headers=headers)
                assert r.status_code == 200
                c.post(f"/api/games/{key}/advance", headers={"X-Host-Token": host_token})
                wanted = {"event: action_received", "event: dice_result",
                          "event: narration", "event: round_started"}
                seen = set()
                for line in it:
                    if line in wanted:
                        seen.add(line)
                        if seen == wanted:
                            break
                assert seen == wanted, f"缺少事件: {wanted - seen}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
