# -*- coding: utf-8 -*-
"""M2 AI 守密人测试：提示词评审 / 裁判三态 / 状态校验 / 场景调度 / LLM 断网降级 / CLI 模拟。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from server import roundman, state_apply, store
from server.engine import build_character
from server.gm import adjudicate, narrate, prompts
from server.gm.llm import LLMClient
from server.gm.pipeline import run_round
from server.state_apply import apply_state_changes, ensure_char_state, filter_forbidden

ROOT = Path(__file__).resolve().parents[2]


def _make_game(module_id: str = "the-haunting") -> tuple[str, str, "store.GameStore"]:
    created = roundman.create_game(name="测试团", module_id=module_id, host_name="爱丽丝")
    key, uid = created["game_key"], created["host_uid"]
    st = store.get_store(key)
    st.set_character(key, uid, "爱丽丝", ensure_char_state(build_character("爱丽丝")))
    return key, uid, st


# ---------------- 提示词评审（M2 验收：无群聊残留、隐私铁律完整） ----------------

def test_prompt_no_lark_residue():
    text = prompts.system_prompt()
    assert text, "gm_system.md 应为非空"
    for word in prompts.LARK_RESIDUE:
        assert word not in text, f"提示词残留飞书/群聊表述: {word}"
    # 隐私铁律完整性
    assert "没能看出更多端倪" in text
    assert "dice_checks" in text and "state_changes" in text
    assert "private_notes" in text
    # §7/§8 思考流程已注入
    assert "规则自检清单" in text and "合规清单" in text


# ---------------- 裁判阶段：三类行动 + 白名单 + 角色卡取值 ----------------

def test_fallback_adjudicate_three_kinds():
    """兜底裁判三态：技能（显式技能名）/ 理智特判 / 无需（none）。"""
    chars = {
        "u1": {"data": {"skills": {"Spot Hidden": 60}, "state": {"san": 50}}},
        "u2": {"data": {"skills": {}}},
        "u3": {"data": {"skills": {}}},
    }
    r = adjudicate.fallback_adjudicate(actions=[
        {"uid": "u1", "text": "我仔细检查这扇门（侦查）"},
        {"uid": "u2", "text": "我直视那团缓缓蠕动的东西"},
        {"uid": "u3", "text": "我沿着走廊慢慢走着"},
    ], characters=chars)
    by_uid = {c["player_uid"]: c for c in r["dice_checks"]}
    assert by_uid["u1"]["kind"] == "skill"
    assert by_uid["u1"]["skill"] == "侦查"
    assert by_uid["u1"]["target"] == 60          # 从角色卡技能值补齐
    assert by_uid["u2"]["kind"] == "sanity" and by_uid["u2"]["loss"] == 1
    assert by_uid["u3"]["kind"] == "none"        # 无需检定


def test_fallback_natural_language_inference():
    """TODO-A 验收：纯自然语言行动无需括号标注，兜底裁判自行推断技能。"""
    actions = [
        {"uid": "u1", "text": "我翻遍整个房间寻找暗门"},    # → 侦查（Spot Hidden）
        {"uid": "u2", "text": "我撬开抽屉的锁"},           # → 开锁（Locksmith）
        {"uid": "u3", "text": "我盯着那团血肉模糊的东西"},   # → sanity（看见+恐怖词）
        {"uid": "u4", "text": "我沿着走廊走着"},           # → none（无关键词）
        {"uid": "u5", "text": "我侧耳听门后的动静"},        # → 倾听（Listen）
        {"uid": "u6", "text": "我偷偷溜进卧室"},           # → 潜行（Stealth）
        {"uid": "u7", "text": "我威胁门口的男人交出钥匙"},   # → 威胁（Intimidate）
    ]
    chars = {a["uid"]: {"data": {"skills": {}}} for a in actions}
    r = adjudicate.fallback_adjudicate(actions=actions, characters=chars)
    assert r["source"] == "fallback"
    assert len(r["dice_checks"]) == len(actions)   # 每玩家一条
    by_uid = {c["player_uid"]: c for c in r["dice_checks"]}

    expect = {
        "u1": ("skill", "侦查"),
        "u2": ("skill", "开锁"),
        "u3": ("sanity", None),
        "u4": ("none", None),
        "u5": ("skill", "倾听"),
        "u6": ("skill", "潜行"),
        "u7": ("skill", "威胁"),
    }
    for uid, (kind, skill) in expect.items():
        c = by_uid[uid]
        assert c["kind"] == kind, f"{uid}: {c}"
        if kind == "skill":
            assert c["skill"] == skill and c["target"] > 0, f"{uid}: {c}"
        elif kind == "sanity":
            assert c["loss"] == 1, f"{uid}: {c}"


@pytest.mark.anyio
async def test_adjudicate_llm_normalization():
    class FakeLLM:
        available = True
        async def chat(self, messages, **kw):
            return json.dumps({
                "dice_checks": [
                    {"player_uid": "u1", "kind": "skill", "skill": "侦查", "reason": "检查"},
                    {"player_uid": "u1", "kind": "sanity", "loss": 2, "reason": "重复玩家应被去重"},
                    {"player_uid": "u2", "kind": "combat", "reason": "非法 kind 应被丢弃"},
                ],
                "private_notes": "它确实在动",
            })

    chars = {"u1": {"data": {"skills": {"Spot Hidden": 55}}},
             "u2": {"data": {"skills": {}}}}
    r = await adjudicate.adjudicate(actions=[{"uid": "u1", "text": "查"}],
                                    characters=chars, llm=FakeLLM())
    assert r["source"] == "llm"
    assert r["private_notes"] == "它确实在动"
    checks = r["dice_checks"]
    assert len(checks) == 1                       # 每玩家一条 + 白名单过滤
    assert checks[0]["target"] == 55              # target 缺省从角色卡补齐


@pytest.mark.anyio
async def test_adjudicate_llm_broken_json_falls_back():
    class BrokenLLM:
        available = True
        async def chat(self, messages, **kw):
            return "这不是 JSON"

    r = await adjudicate.adjudicate(
        actions=[{"uid": "u1", "text": "我检查柜子"}],
        characters={"u1": {"data": {"skills": {}}}}, llm=BrokenLLM())
    assert r["source"] == "fallback"
    assert r["dice_checks"][0]["kind"] == "skill"


# ---------------- 状态应用器：五类校验 + 非法值拒绝 ----------------

def test_filter_forbidden_rewrites():
    assert filter_forbidden("你仔细检查了柜子，没有发现异常。") == "没能看出更多端倪。"
    assert "没能看出更多端倪" in filter_forbidden("你环顾四周，其实你漏掉了墙上的暗门。")
    assert filter_forbidden("走廊尽头有微光。") == "走廊尽头有微光。"


def test_ensure_char_state():
    data = ensure_char_state({"derived": {"HP": 12, "SAN": 60},
                              "sanity": {"max": 60, "current": 60}})
    st = data["state"]
    assert st["hp"] == 12 and st["san"] == 60
    assert st["clues"] == [] and st["conditions"] == [] and st["gold"] == 0


def test_state_apply_hp_validation():
    key, uid, st = _make_game()
    char = st.get_character(key, uid)["data"]
    max_hp = char["derived"]["HP"]
    # 越界拒绝
    out = apply_state_changes(st, key, 1,
                              [{"type": "hp", "player_uid": uid, "delta": -9999}])
    assert len(out["rejected"]) == 1 and "越界" in out["rejected"][0]["reason"]
    # 正常扣血落库
    out = apply_state_changes(st, key, 1,
                              [{"type": "hp", "player_uid": uid, "delta": -2}])
    assert len(out["applied"]) == 1
    assert out["applied"][0]["hp"] == max_hp - 2
    # 审计可查
    changes = st.list_state_changes(key)
    assert changes and changes[0]["type"] == "hp"


def test_state_apply_san_and_item():
    key, uid, st = _make_game()
    # SAN 越界拒绝（+100 超过上限）
    out = apply_state_changes(st, key, 1,
                              [{"type": "san", "player_uid": uid, "delta": 100}])
    assert len(out["rejected"]) == 1 and "越界" in out["rejected"][0]["reason"]
    # SAN 受伤落库 + 理智历史
    out = apply_state_changes(st, key, 1,
                              [{"type": "san", "player_uid": uid, "delta": -3}])
    assert len(out["applied"]) == 1
    char = st.get_character(key, uid)["data"]
    assert char["state"]["san"] == char["derived"]["SAN"] - 3
    # 物品：gain → lose；余额不足拒绝
    out = apply_state_changes(st, key, 1,
                              [{"type": "item", "player_uid": uid,
                                "action": "gain", "item": "旧钥匙"}])
    assert len(out["applied"]) == 1
    out = apply_state_changes(st, key, 1,
                              [{"type": "item", "player_uid": uid,
                                "action": "lose", "item": "不存在的剑"}])
    assert len(out["rejected"]) == 1 and "余额不足" in out["rejected"][0]["reason"]


def test_state_apply_clue_dedupe_and_perception():
    key, uid, st = _make_game()
    out = apply_state_changes(st, key, 1,
                              [{"type": "clue", "player_uid": uid,
                                "clue_id": "C-01", "text": "符文的呼吸"}])
    assert len(out["applied"]) == 1
    assert len(out["perceptions"]) == 1
    assert out["perceptions"][0]["to_uid"] == uid
    # 重复线索拒绝
    out = apply_state_changes(st, key, 2,
                              [{"type": "clue", "player_uid": uid,
                                "clue_id": "C-01", "text": "重复"}])
    assert len(out["rejected"]) == 1 and "已持有" in out["rejected"][0]["reason"]
    # 目标玩家可查感知，别人查不到
    perc = st.list_perceptions(key, to_uid=uid)
    assert perc and perc[0]["clue_id"] == "C-01"


def test_state_apply_scene_switch_and_handouts():
    key, uid, st = _make_game(module_id="toy-dancer-comes")
    out = apply_state_changes(st, key, 1,
                              [{"type": "scene", "text": "阁楼（铁门后）"}],
                              module_id="toy-dancer-comes")
    assert len(out["applied"]) == 1
    assert st.get_game(key)["current_scene"] == "s07"
    assert out["scene"]["id"] == "s07"
    assert "house-of-tragedies.jpeg" in out["handouts"]   # 附件展示数据
    # 未知场景拒绝
    out = apply_state_changes(st, key, 2, [{"type": "scene", "text": "不存在的场景"}],
                              module_id="toy-dancer-comes")
    assert len(out["rejected"]) == 1 and "场景不存在" in out["rejected"][0]["reason"]


# ---------------- 管线：断网降级 / LLM 全流程 / 场景注入 ----------------

@pytest.mark.anyio
async def test_pipeline_offline_completes():
    """LLM 断网（无 key）时游戏不崩溃，状态应用仍完成（M2 验收）。"""
    key, uid, st = _make_game()
    st.set_action(key, uid, 0, "我仔细检查这扇门")
    res = await run_round(key, llm=LLMClient(api_key="", model="x"))   # 未配置 → 离线
    assert res["sources"] == {"adjudicate": "fallback", "narrate": "fallback"}
    assert res["dice_results"] and res["dice_results"][0]["kind"] == "check"
    assert res["narrative"]
    assert len(st.list_dice_log(key)) >= 1
    assert "narration" in [m["kind"] for m in st.list_messages(key)]


@pytest.mark.anyio
async def test_pipeline_with_llm_full_round():
    key, uid, st = _make_game()

    class FakeLLM:
        available = True
        def __init__(self):
            self.stage = None
        async def chat(self, messages, **kw):
            content = messages[-1]["content"]
            if "裁判阶段" in content:
                self.stage = "adjudicate"
                return json.dumps({
                    "dice_checks": [{"player_uid": uid, "kind": "sanity",
                                     "loss": 1, "reason": "直视"}],
                    "private_notes": "它确实在动，但我不能告诉玩家",
                })
            self.stage = "narrate"
            return json.dumps({
                "narrative": "你直视那团蠕动的东西，心头发寒，但你稳住了。",
                "state_changes": [{"type": "san", "player_uid": uid, "delta": -1}],
            })

    st.set_action(key, uid, 0, "我直视那团缓缓蠕动的东西")
    res = await run_round(key, llm=FakeLLM())
    assert res["sources"] == {"adjudicate": "llm", "narrate": "llm"}
    assert res["dice_results"][0]["kind"] == "san_check"
    # 私密笔记落库（只进 KP 上下文）
    notes = st.list_kp_notes(key)
    assert notes and "不能告诉玩家" in notes[0]["text"]
    # 状态落库
    char = st.get_character(key, uid)["data"]
    assert char["state"]["san"] == char["derived"]["SAN"] - 1


@pytest.mark.anyio
async def test_pipeline_narrate_scene_injection():
    """场景切换经叙事 state_changes 注入 scenes.json 数据并带出附件。"""
    key, uid, st = _make_game(module_id="toy-dancer-comes")

    class FakeLLM:
        available = True
        async def chat(self, messages, **kw):
            content = messages[-1]["content"]
            if "裁判阶段" in content:
                return json.dumps({"dice_checks": [], "private_notes": ""})
            return json.dumps({
                "narrative": "你推开了书架后的铁门，通向阁楼。",
                "state_changes": [{"type": "scene", "text": "阁楼（铁门后）"}],
            })

    st.set_action(key, uid, 0, "我推开书架后的铁门")
    res = await run_round(key, llm=FakeLLM())
    assert res["scene"] is not None and res["scene"]["id"] == "s07"
    assert "house-of-tragedies.jpeg" in res["handouts"]
    assert st.get_game(key)["current_scene"] == "s07"


# ---------------- CLI 模拟（M2 验收：3 类行动正确判定并掷骰） ----------------

def test_simulate_cli_three_modes():
    for mode, expect_kind in (("skill", "skill"), ("sanity", "sanity"), ("none", "none")):
        r = subprocess.run(
            [sys.executable, "-m", "server.gm.simulate", "--mode", mode],
            capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))
        assert r.returncode == 0, r.stderr
        d = json.loads(r.stdout)
        assert d["dice_checks"][0]["kind"] == expect_kind, mode
        if mode == "sanity":
            assert d["dice_results"][0]["kind"] == "san_check"
        if mode == "skill":
            assert d["dice_results"][0]["kind"] == "check"
            assert d["dice_results"][0]["result"] in (
                "critical", "extreme", "hard", "regular", "failure", "fumble")
        if mode == "none":
            assert d["dice_results"] == []
