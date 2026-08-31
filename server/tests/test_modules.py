# -*- coding: utf-8 -*-
"""模组数据层测试（M1 验收：/api/modules 返回 v2 模组与场景数据）。"""
from __future__ import annotations

from server import modules as m


def test_list_modules_is_v2():
    lst = m.list_modules()
    ids = {x["id"] for x in lst}
    assert {"the-haunting", "toy-dancer-comes"} <= ids
    assert all(x["schema"] == "trpg-module/v1" for x in lst)
    assert all(x["system"] == "coc7" for x in lst)


def test_all_modules_pass_validation():
    for meta in m.list_modules():
        assert m.validate_module(meta["id"]) == [], meta["id"]


def test_haunting_scenes():
    flow = m.get_scene_flow("the-haunting")
    assert flow == ["s01", "s02", "s03", "s04", "s05", "s06", "s07"]
    scenes = m.get_scenes("the-haunting")
    assert len(scenes) == 7
    for s in scenes:
        for field in ("id", "name", "location", "summary", "checks", "clues"):
            assert field in s, s.get("id")
    s06 = m.get_scene("the-haunting", "s06")
    assert "joseph_ghost" in s06["npcs"]
    assert any(c["kind"] == "combat" for c in s06["checks"])


def test_toy_dancer_scenes_and_handouts():
    flow = m.get_scene_flow("toy-dancer-comes")
    assert len(flow) == 10 and flow[0] == "s01" and flow[-1] == "s10"
    s01 = m.get_scene("toy-dancer-comes", "s01")
    assert "fake_shen" in s01["npcs"]
    # 场景引用的附件都能解析
    for h in s01["handouts"]:
        assert m.handout_path("toy-dancer-comes", h) is not None, h
    s07 = m.get_scene("toy-dancer-comes", "s07")
    assert m.handout_path("toy-dancer-comes", s07["handouts"][0]) is not None


def test_handout_path_no_traversal():
    assert m.handout_path("toy-dancer-comes", "../../meta.json") is None
    assert m.handout_path("toy-dancer-comes", "不存在的图.png") is None
    assert m.handout_path("toy-dancer-comes", "../plot.md") is None


def test_pregens():
    pregens = m.list_pregens("the-haunting")
    assert len(pregens) == 2
    assert all(p["schema"] == "coc7-character/v1" for p in pregens)
    assert m.list_pregens("不存在模组") == []


def test_unknown_module_returns_none():
    assert m.get_module("nope") is None
    assert m.get_scene("nope", "s01") is None
