# -*- coding: utf-8 -*-
"""SQLite 存档层测试（M1 验收：可建可读；并发不脏写）。"""
from __future__ import annotations

import threading

import pytest

from server import store
from server.roundman import room_lock


def _make(key: str, name: str = "房间", module: str | None = "the-haunting") -> store.GameStore:
    st = store.get_store(key)
    st.create_game(key, name, "coc7", module, "测试简介", "u_host", None)
    return st


def test_store_path_rejects_bad_keys():
    for bad in ("../evil", "a/b", "UPPER", "ab", "a" * 65):
        with pytest.raises(ValueError):
            store.store_path(bad)
    # 合法 key
    assert store.store_path("a1b2c3d4").name == "a1b2c3d4.db"


def test_create_and_read_game():
    st = _make("t1aabb")
    g = st.get_game("t1aabb")
    assert g["name"] == "房间"
    assert g["phase"] == "lobby" and g["round"] == 0
    assert g["module_id"] == "the-haunting"
    assert g["rule"] == "coc7"


def test_player_action_version_history():
    key = "t2aabb"
    st = _make(key)
    st.add_player(key, "u1", "爱丽丝")
    st.add_player(key, "u2", "鲍勃")
    assert st.set_action(key, "u1", 3, "我检查柜子") == 1
    assert st.set_action(key, "u1", 3, "我检查书桌") == 2   # 修改递增版本

    latest = st.latest_actions(key, 3)
    assert latest["u1"]["text"] == "我检查书桌"
    assert latest["u1"]["action_version"] == 2

    hist = st.list_action_history(key, 3, "u1")
    assert [h["action_version"] for h in hist] == [1, 2]
    assert [h["text"] for h in hist] == ["我检查柜子", "我检查书桌"]

    # 玩家信息同步
    p = st.get_player(key, "u1")
    assert p["has_submitted"] == 1 and p["action"] == "我检查书桌"


def test_advance_round_resets_submissions():
    key = "t3aabb"
    st = _make(key)
    st.add_player(key, "u1", "爱丽丝")
    st.set_action(key, "u1", 0, "行动内容")
    new_round = st.advance_round(key, phase="collecting")
    assert new_round == 1
    assert st.get_game(key)["round"] == 1
    assert st.get_game(key)["phase"] == "collecting"
    p = st.get_player(key, "u1")
    assert p["has_submitted"] == 0 and p["action"] is None
    # 历史仍在（审计不丢）
    assert len(st.list_action_history(key, 0, "u1")) == 1


def test_messages_rounds_state_perceptions():
    key = "t4aabb"
    st = _make(key)
    mid = st.add_message(key, 0, "scene", {"text": "开场"})
    assert mid >= 1
    st.add_message(key, 0, "narration", {"text": "你走入走廊"})
    msgs = st.list_messages(key)
    assert [m["kind"] for m in msgs] == ["scene", "narration"]
    assert msgs[0]["payload"]["text"] == "开场"

    st.add_round(key, 0, "collecting", 1)
    st.add_state_change(key, 0, "hp", "u1", {"delta": -2})
    st.add_state_change(key, 0, "clue", "u1", {"clue_id": "C-01"})
    sc = st.list_state_changes(key)
    assert {c["type"] for c in sc} == {"hp", "clue"}

    st.add_perception(key, 0, "u1", "你注意到符文在呼吸", "C-01")
    perc = st.list_perceptions(key, "u1")
    assert len(perc) == 1 and perc[0]["text"] == "你注意到符文在呼吸"
    # 别人收不到
    assert st.list_perceptions(key, "u2") == []


def test_kp_notes_and_dice_log():
    key = "t5aabb"
    st = _make(key)
    st.add_kp_note(key, "德拉波尔家族真相", 0)
    st.add_kp_note(key, "下一幕：地下室", 1)
    notes = st.list_kp_notes(key)
    assert len(notes) == 2
    st.add_dice_log(key, "roll", {"expr": "1d100", "total": 42}, round_no=1)
    audit = st.list_dice_log(key)
    assert len(audit) == 1 and audit[0]["kind"] == "roll"
    assert audit[0]["payload"]["total"] == 42


def test_concurrent_writes_no_dirty_data():
    """房间级写锁 + WAL 事务：20 个并发 set_action 全部落库、版本连续无丢失。"""
    key = "t6aabb"
    st = _make(key)
    st.add_player(key, "u1", "爱丽丝")
    errors: list[Exception] = []

    def worker(i: int):
        try:
            with room_lock(key):
                st.set_action(key, "u1", 1, f"行动{i}")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    p = st.get_player(key, "u1")
    assert p["action_version"] == 20
    hist = st.list_action_history(key, 1, "u1")
    versions = sorted(h["action_version"] for h in hist)
    assert versions == list(range(1, 21))      # 无丢失、无重复
    assert len({h["text"] for h in hist}) == 20


def test_concurrent_readers_during_writes():
    """WAL：写入进行中，读者不阻塞、不报错。"""
    key = "t7aabb"
    st = _make(key)
    st.add_player(key, "u1", "爱丽丝")
    read_errors: list[Exception] = []
    stop = threading.Event()

    def writer():
        i = 0
        while not stop.is_set():
            with room_lock(key):
                st.set_action(key, "u1", 1, f"写{i}")
            i += 1

    def reader():
        try:
            for _ in range(40):
                st.get_game(key)
                st.list_players(key)
        except Exception as e:  # noqa: BLE001
            read_errors.append(e)

    w = threading.Thread(target=writer)
    readers = [threading.Thread(target=reader) for _ in range(3)]
    w.start()
    for r in readers:
        r.start()
    for r in readers:
        r.join()
    stop.set()
    w.join()

    assert read_errors == []
