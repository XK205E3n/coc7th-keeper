# -*- coding: utf-8 -*-
"""模组表侧投影与开场白隐私（玩家可见性边界）测试。

背景（E3n 实测反馈，sleeping-cat 引入实测）：
- 开场直接把场景 summary（KP 视角，含怪物身份/检定安排）亮给玩家；
- /api/modules/{id}/scenes 把全部场景的 summary/checks/clues/npcs 发给玩家端。

契约：
- /api/modules(/detail) 与 /scenes(/detail) 只发玩家可见投影；
- 开场消息用场景 intro（玩家可见引入文本），缺失时只发表头；
- 首场景 handouts（玩家资料）随开场注入叙事流；
- scene 变动的广播数据（state_apply 返回值）同样只含投影字段。
"""
from __future__ import annotations

import json

KP_MARKERS = ("冷蛛", "幻梦境", "检定", "SAN 1", "归还台座")


def test_scenes_api_projection(client):
    """/scenes 只含表侧字段，且全文不含 KP 视角关键词。"""
    r = client.get("/api/modules/sleeping-cat/scenes")
    assert r.status_code == 200
    scenes = r.json()["scenes"]
    assert len(scenes) == 8
    for s in scenes:
        assert set(s.keys()) <= {"id", "name", "location", "intro", "handouts"}
    dump = json.dumps(scenes, ensure_ascii=False)
    for marker in KP_MARKERS:
        assert marker not in dump, f"玩家可见投影泄漏 KP 关键词: {marker}"
    # 首场景必须带玩家可见开场白
    assert "红叶" in scenes[0].get("intro", "")


def test_module_list_api_hides_kp_meta(client):
    """/api/modules 的 meta 不含 summary/tags/source；简介走 public_summary。"""
    r = client.get("/api/modules")
    assert r.status_code == 200
    for m in r.json()["modules"]:
        for field in ("summary", "tags", "source"):
            assert field not in m, f"{m['id']} meta 泄漏 KP 字段: {field}"
        assert m.get("public_summary"), f"{m['id']} 缺玩家可见简介"
    sleeping = next(m for m in r.json()["modules"] if m["id"] == "sleeping-cat")
    assert "冷蛛" not in sleeping["public_summary"]


def test_opening_uses_intro_and_injects_handouts(client):
    """开局：开场白来自 intro（无 KP 关键词），首场景手卡随开场落叙事流。"""
    r = client.post("/api/games", json={"name": "开场隐私测试",
                                        "module_id": "sleeping-cat"})
    assert r.status_code == 200
    body = r.json()
    key, token = body["game_key"], body["host_token"]
    host_headers = {"X-Player-Token": token}   # 房主的玩家令牌即 host_token

    msgs = client.get(f"/api/games/{key}/messages",
                      headers=host_headers).json()["messages"]
    scene_msgs = [m for m in msgs if m["kind"] == "scene"]
    assert scene_msgs, "缺开场场景消息"
    text = str(scene_msgs[0]["payload"]["text"])
    assert scene_msgs[0]["payload"]["scene_id"] == "s01"
    assert "红叶" in text                      # 为什么来 / 现在在哪（intro 钩子）
    assert "担心" in text
    for marker in KP_MARKERS:
        assert marker not in text, f"开场白泄漏 KP 关键词: {marker}"

    handouts = [str(m["payload"]["file"]) for m in msgs if m["kind"] == "handout"]
    assert "sms-worrying.png" in handouts      # 担心的短信（玩家资料）
    assert "sns-short-posts.png" in handouts


def test_scene_change_broadcast_is_projection(client):
    """scene 状态变动的返回值（供 scene_changed 广播）只含玩家可见字段。"""
    from server import modules, state_apply, store
    r = client.post("/api/games", json={"name": "场景投影测试",
                                        "module_id": "sleeping-cat"})
    key = r.json()["game_key"]
    st = store.get_store(key)
    outcome = state_apply.apply_state_changes(
        st, key, 1, [{"type": "scene", "text": "s02"}],
        module_id="sleeping-cat")
    scene = outcome["scene"]
    assert scene is not None
    assert set(scene.keys()) <= {"id", "name", "location", "intro", "handouts"}
    assert modules.get_scene("sleeping-cat", "s02") is not None  # 数据层仍保留全量


# 各模组玩家可见字段（name/location/intro）中的禁用词：怪物真名 / 机制词 / 结构词
MODULE_NAME_MARKERS = {
    "the-haunting": ("鬼魂", "德拉波尔", "亡魂", "高潮", "收尾"),
    "toy-dancer-comes": ("献祭", "恶灵", "谢尔顿", "犹格", "木偶化", "最终战", "肉体改造", "NPC"),
    "yuren-pie": ("深潜者", "异界", "收尾", "遭遇"),
    "sleeping-cat": ("冷蛛", "幻梦境", "终末", "切断连接", "检定"),
}

ALL_MODULES = ("the-haunting", "toy-dancer-comes", "yuren-pie", "sleeping-cat")


def test_all_scenes_have_intro(client):
    """全部模组的每个场景都配置玩家可见入场白（回归保护：开场/切场不再裸奔 summary）。"""
    for mid in ALL_MODULES:
        scenes = client.get(f"/api/modules/{mid}/scenes").json()["scenes"]
        assert scenes, mid
        for s in scenes:
            assert str(s.get("intro", "")).strip(), f"{mid} 场景 {s['id']} 缺 intro"


def test_scene_names_locations_intros_are_player_safe(client):
    """场景 name/location/intro 不含各模组的怪物真名 / 机制词 / 结构词。"""
    for mid, markers in MODULE_NAME_MARKERS.items():
        scenes = client.get(f"/api/modules/{mid}/scenes").json()["scenes"]
        for s in scenes:
            text = " ".join((s.get("name", ""), s.get("location", ""),
                             s.get("intro", "")))
            for m in markers:
                assert m not in text, f"{mid}:{s['id']} 玩家可见字段含 KP 词 {m!r}"


def test_validate_module_enforces_intro_public_summary_handouts(tmp_path, monkeypatch):
    """validate_module 强制拦截缺 intro / 缺 public_summary / handout 路径不存在
    （M8R7 起为程序校验项：未来新模组不合规直接报错，不等人工审阅兜底）。"""
    from server import modules as m
    real_dir = str(m.modules_dir())
    root = tmp_path / "mods" / "broken-mod"
    (root / "handouts").mkdir(parents=True)
    (root / "meta.json").write_text(json.dumps({
        "schema": "trpg-module/v1", "id": "broken-mod", "number": 99,
        "cn": "坏模组", "system": "coc7", "summary": "KP 梗概",
        "files": {},
    }, ensure_ascii=False), encoding="utf-8")
    (root / "scenes.json").write_text(json.dumps({"scenes": [
        {"id": "s01", "name": "场地", "summary": "KP 摘要",
         "handouts": ["nope.png"]},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("COC_MODULES_DIR", str(tmp_path / "mods"))
    errs = m.validate_module("broken-mod")
    joined = " | ".join(errs)
    assert "缺 public_summary" in joined
    assert "s01 缺 intro" in joined
    assert "nope.png" in joined
    # 恢复真实模组目录：已发布模组零误伤
    monkeypatch.setenv("COC_MODULES_DIR", real_dir)
    for mid in ALL_MODULES:
        assert m.validate_module(mid) == []
