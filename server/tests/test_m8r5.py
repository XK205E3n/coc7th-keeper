# -*- coding: utf-8 -*-
"""M8R5 验收测试：强制推进语义 / 删除房间 / 行动回显 / 进站门禁 / LLM 状态事件。"""
from __future__ import annotations

import secrets


def _create_room(client, name="M8R5团"):
    d = client.post("/api/games", json={"name": name, "host_name": "房主"}).json()
    return d["game_key"], d["host_token"]


def test_force_advance_two_players(client):
    """双人房：一人提交、一人未提交 → 强制推进 → 结算产出叙事且未提交者被点名。"""
    d = client.post("/api/games", json={"name": "双人团", "host_name": "房主"}).json()
    key, host_token = d["game_key"], d["host_token"]
    j = client.post(f"/api/games/{key}/join", json={"name": "乔治"},
                    headers={"X-Join-Token": d["invite_token"]})
    assert j.status_code == 200
    host = {"X-Host-Token": host_token}

    # 房主提交行动（乔治未提交）
    r = client.post(f"/api/games/{key}/actions", json={"text": "观察四周"},
                    headers={"X-Player-Token": host_token})
    assert r.status_code == 200
    # M8R5 语义 2.0：提交不再自动推进，round 保持 0
    assert client.get(f"/api/games/{key}").json()["game"]["round"] == 0

    # 强制推进 → 结算
    r = client.post(f"/api/games/{key}/advance", headers=host)
    assert r.status_code == 200
    body = r.json()
    assert body["triggered"] is True
    assert body["skipped"] == ["乔治"]

    # 结算产出叙事（round 0 的行动进入裁判，而非被丢弃）
    msgs = client.get(f"/api/games/{key}/messages",
                      headers={"X-Player-Token": host_token}).json()["messages"]
    assert any(m["kind"] == "narration" for m in msgs)
    # 回合已 +1
    view = client.get(f"/api/games/{key}").json()["game"]
    assert view["round"] == 1


def test_force_advance_requires_host(client):
    key, _ = _create_room(client)
    r = client.post(f"/api/games/{key}/advance")
    assert r.status_code in (401, 403)


def test_my_action_echo(client):
    """行动回显：提交后能查到自己本轮提交的文本。

    用双人房（另一人未提交 → 不触发自动推进），否则单人提交即推进、
    行动随回合清空，查不到属预期。
    """
    d = client.post("/api/games", json={"name": "回显团", "host_name": "房主"}).json()
    key, host_token = d["game_key"], d["host_token"]
    client.post(f"/api/games/{key}/join", json={"name": "乔治"},
                headers={"X-Join-Token": d["invite_token"]})
    r = client.get(f"/api/games/{key}/my-action",
                   headers={"X-Player-Token": host_token})
    assert r.status_code == 200
    assert r.json()["text"] is None
    client.post(f"/api/games/{key}/actions", json={"text": "检查装备"},
                headers={"X-Player-Token": host_token})
    r = client.get(f"/api/games/{key}/my-action",
                   headers={"X-Player-Token": host_token})
    assert r.json()["text"] == "检查装备"
    assert r.json()["round"] == 0


def test_close_room_by_host_only(client):
    """删除房间：房主软关闭成功；join 被拒；非房主 403。"""
    d = client.post("/api/games", json={"name": "关闭团", "host_name": "房主"}).json()
    key, host_token = d["game_key"], d["host_token"]
    # 非房主
    r = client.delete(f"/api/games/{key}")
    assert r.status_code in (401, 403)
    # 房主关闭
    r = client.delete(f"/api/games/{key}", headers={"X-Host-Token": host_token})
    assert r.status_code == 200
    assert r.json()["closed"] is True
    # 幂等
    r = client.delete(f"/api/games/{key}", headers={"X-Host-Token": host_token})
    assert r.status_code == 200
    # 关闭后 join 拒绝（410）
    r = client.post(f"/api/games/{key}/join", json={"name": "迟到者"},
                    headers={"X-Join-Token": d["invite_token"]})
    assert r.status_code == 410


def test_access_gate_enforced_when_configured(client, monkeypatch, tmp_path):
    """进站门禁：设置 access_password 后无 cookie 401，/api/health 豁免，
    正确密码换 cookie 后放行；未设置时全放行。"""
    from server import config as cfgmod

    def set_pwd(value):
        cfg_now = cfgmod.load_config()
        cfg_now["access_password"] = value
        cfgmod.save_config(cfg_now)

    # 未设置 → 放行
    set_pwd(None)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/modules").status_code == 200

    # 设置 → 拦截，health 豁免
    gate_pwd = secrets.token_hex(6)  # 运行时生成，避免硬编码凭据
    set_pwd(gate_pwd)
    r = client.get("/api/modules")
    assert r.status_code == 401
    assert r.json()["code"] == "access_denied"
    assert client.get("/api/health").status_code == 200
    # 页面请求必须放行（否则前端密码门本身加载不出来 —— v1.0.3 实测踩坑）
    r = client.get("/")
    assert r.status_code == 200

    # 错密码
    r = client.post("/api/access", json={"password": "wrong"})
    assert r.status_code == 401

    # 对密码 → 下发 cookie → 放行
    r = client.post("/api/access", json={"password": gate_pwd})
    assert r.status_code == 200
    assert "access_ok" in r.cookies
    assert client.get("/api/modules").status_code == 200

    # check 端点
    assert client.get("/api/access/check").json() == {"required": True,
                                                      "authenticated": True}

    # 清除密码 → 恢复放行
    set_pwd(None)
    assert client.get("/api/modules").status_code == 200
