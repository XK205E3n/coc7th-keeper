# -*- coding: utf-8 -*-
"""M8R6 验收测试：T-E8 建房频控 / T-B1 建卡服务端校验。"""
from __future__ import annotations

import secrets


def _create(client, xff=None, **kw):
    """建房辅助：可选 X-Forwarded-For 头，返回响应。"""
    headers = {"X-Forwarded-For": xff} if xff else None
    return client.post("/api/games", json={"name": "频控团", **kw}, headers=headers)


# ---------------- T-E8 建房频控 ----------------

def test_create_rate_limit_blocks_sixth_room(client):
    """同 IP 第 6 间 429，提示含频控语义；前 5 间正常。"""
    for i in range(5):
        r = _create(client)
        assert r.status_code == 200, f"第 {i + 1} 间不应被拦"
    r = _create(client)
    assert r.status_code == 429
    assert "每小时最多" in r.json()["detail"]


def test_create_rate_limit_per_ip_isolated(client):
    """频控按 IP 分桶：1.1.1.1 打满后 2.2.2.2 不受影响。"""
    for _ in range(5):
        assert _create(client, xff="1.1.1.1").status_code == 200
    assert _create(client, xff="1.1.1.1").status_code == 429
    assert _create(client, xff="2.2.2.2").status_code == 200


def test_create_rate_limit_uses_xff_first_segment(client):
    """穿透场景取 XFF 首段：多级代理链按第一跳（真实客户端）计数。"""
    for _ in range(5):
        assert _create(client, xff="3.3.3.3, 10.0.0.1").status_code == 200
    # 同一真实客户端换了中间代理链，仍按首段识别
    r = _create(client, xff="3.3.3.3")
    assert r.status_code == 429


def test_create_rate_limit_gate_authorized_exempt(client):
    """已通过进站门禁（持有效 access cookie）的请求豁免建房频控。"""
    from server import config as cfgmod

    def set_pwd(value):
        cfg_now = cfgmod.load_config()
        cfg_now["access_password"] = value
        cfgmod.save_config(cfg_now)

    gate_pwd = secrets.token_hex(6)  # 运行时生成，避免硬编码凭据
    set_pwd(gate_pwd)
    r = client.post("/api/access", json={"password": gate_pwd})
    assert r.status_code == 200
    for i in range(7):
        r = _create(client)
        assert r.status_code == 200, f"门禁已认证第 {i + 1} 间不应被拦"
    set_pwd(None)


# ---------------- T-B1 建卡服务端校验 ----------------

def _room_and_token(client):
    d = client.post("/api/games", json={"name": "建卡团", "host_name": "房主"}).json()
    return d["game_key"], {"X-Player-Token": d["host_token"]}


def test_create_character_rejects_invalid_card(client):
    """直打 API 写非法卡：schema 错 / 属性非 int / 取值越界 → 422。"""
    key, auth = _room_and_token(client)
    url = f"/api/games/{key}/characters"
    bad_cards = [
        {"schema": "coc7-character/v2", "attributes": {}, "skills": {}},
        {"schema": "coc7-character/v1", "attributes": {"STR": "强壮"}, "skills": {}},
        {"schema": "coc7-character/v1", "attributes": {"STR": 250}, "skills": {}},
        {"schema": "coc7-character/v1", "attributes": {}, "skills": {"Spot Hidden": 999}},
    ]
    for card in bad_cards:
        r = client.post(url, json={"character": card}, headers=auth)
        assert r.status_code == 422, f"{card['attributes']} 应被拒"


def test_create_character_minimal_card_gets_defaults(client):
    """手动最小卡（仅 schema+attributes）通过，state/sanity 由服务端补默认。"""
    key, auth = _room_and_token(client)
    r = client.post(f"/api/games/{key}/characters", json={
        "character": {"schema": "coc7-character/v1", "name": "极简卡",
                      "attributes": {"STR": 50}, "skills": {}},
    }, headers=auth)
    assert r.status_code == 200
    char = r.json()["character"]
    assert char["state"]["san"] == 50 and char["state"]["max_san"] == 50
    assert char["state"]["hp"] == 10 and char["state"]["clues"] == []
    assert char["sanity"]["current"] == 50
    # 未知字段保留，不静默丢弃
    assert "extra_field" not in char  # 先确认默认无此键
    r = client.post(f"/api/games/{key}/characters", json={
        "character": {"schema": "coc7-character/v1", "attributes": {},
                      "skills": {}, "custom_backstory": " homemade"},
    }, headers=auth)
    assert r.status_code == 200
    assert r.json()["character"]["custom_backstory"] == " homemade"


def test_create_character_accepts_real_pregen(client):
    """真实预置卡（缺 state）照常通过且服务端补全 state —— 9 卡零回归的代表用例。"""
    import glob
    import json as _json
    pregen_files = sorted(glob.glob("modules/*/pregens/*.json"))
    assert pregen_files, "预置卡缺失？"
    card = _json.load(open(pregen_files[0], encoding="utf-8"))
    assert "state" not in card  # 前提：预置卡本来缺 state
    key, auth = _room_and_token(client)
    r = client.post(f"/api/games/{key}/characters",
                    json={"character": card, "name": "预置角色"}, headers=auth)
    assert r.status_code == 200
    char = r.json()["character"]
    assert char["state"]["max_san"] == (card.get("derived") or {}).get("SAN", 50)


def test_create_character_auto_unaffected(client):
    """action=auto 分支不经直传校验，行为不变。"""
    key, auth = _room_and_token(client)
    r = client.post(f"/api/games/{key}/characters", json={"action": "auto"},
                    headers=auth)
    assert r.status_code == 200
    assert r.json()["character"]["schema"] == "coc7-character/v1"
