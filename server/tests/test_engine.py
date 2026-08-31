# -*- coding: utf-8 -*-
"""规则引擎回归测试（M1 验收：`roll 1d100` / `check skill "侦查" 60` / `build` 与归档版一致）。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from server.engine import (
    attack_roll,
    build_character,
    judge,
    luck_check,
    roll_expr,
    sanity_check_roll,
    skill_check,
)

ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = ROOT / "server" / "engine"


# ---------------- 通用掷骰 ----------------

def test_roll_expr_range_and_shape():
    r = roll_expr("1d100", by="t", why="回归", no_log=True)
    assert r["ok"] is True
    assert r["kind"] == "roll"
    assert 1 <= r["total"] <= 100
    assert sum(r["rolls"]) + r["k"] == r["total"]


def test_roll_expr_modifiers():
    r = roll_expr("2d6+3", no_log=True)
    assert 5 <= r["total"] <= 15
    r2 = roll_expr("d20", no_log=True)
    assert 1 <= r2["total"] <= 20
    r3 = roll_expr("3d10-2", no_log=True)
    assert 1 <= r3["total"] <= 28


def test_roll_expr_invalid():
    with pytest.raises(ValueError):
        roll_expr("abc", no_log=True)


# ---------------- 检定判定档位 ----------------

def test_judge_bands():
    assert judge(1, 60) == "critical"          # 大成功
    assert judge(10, 60) == "extreme"          # 10 <= 12
    assert judge(25, 60) == "hard"             # 25 <= 30
    assert judge(50, 60) == "regular"
    assert judge(80, 60) == "failure"
    assert judge(100, 60) == "fumble"          # 大失败


def test_skill_check_payload():
    c = skill_check("侦查", 60, by="t", why="检查")
    assert c["kind"] == "check"
    assert c["skill"] == "侦查" and c["skill_value"] == 60
    assert 1 <= c["roll"] <= 100
    assert c["result"] in ("critical", "extreme", "hard", "regular", "failure", "fumble")
    cn = {"critical": "大成功", "extreme": "极难成功", "hard": "困难成功",
          "regular": "成功", "failure": "失败", "fumble": "大失败"}
    assert c["result_cn"] == cn[c["result"]]


def test_skill_check_invalid_value():
    with pytest.raises(ValueError):
        skill_check("侦查", 0)


def test_luck_check():
    l = luck_check(55)
    assert l["kind"] == "luck" and l["skill"] == "Luck" and l["skill_value"] == 55


# ---------------- 角色 build ----------------

def test_build_character_structure():
    b = build_character("测试调查员", 25)
    assert b["schema"] == "coc7-character/v1"
    assert b["name"] == "测试调查员"
    attrs = b["attributes"]
    for k in ("STR", "CON", "SIZ", "DEX", "APP", "INT", "POW", "EDU", "LUK"):
        assert 3 <= attrs[k] <= 99, k
    d = b["derived"]
    assert d["HP"] == -(-(attrs["CON"] + attrs["SIZ"]) // 10)   # ceil
    assert d["MP"] == -(-attrs["POW"] // 5)
    assert d["SAN"] == attrs["POW"] * 5
    assert b["sanity"]["current"] == d["SAN"]
    assert b["sanity"]["max"] == d["SAN"]
    assert "Spot Hidden" in b["skills"] and "Dodge" in b["skills"]


# ---------------- 理智检定 ----------------

def test_sanity_success_gives_zero_loss():
    # san 100 几乎必然成功（roll<=100）
    s = sanity_check_roll(100, 2)
    assert s["kind"] == "san_check"
    assert s["success"] is True
    assert s["actual_loss"] == 0
    assert s["current_san"] == 100
    assert s["insane_now"] is False


def test_sanity_loss_ge5_triggers_insanity():
    # san=0 → roll>=1 必然失败；loss>=5 → 实时疯狂
    s = sanity_check_roll(0, 5, why="直视实体")
    assert s["success"] is False
    assert s["insane_now"] is True
    assert s["insane_kind"] is not None and s["insane_kind"]["type"] == "real"
    assert 1 <= s["actual_loss"] <= 6
    assert s["current_san"] == 0


def test_sanity_small_loss_no_insanity():
    s = sanity_check_roll(0, 2)
    assert s["success"] is False
    assert s["insane_now"] is False
    assert 1 <= s["actual_loss"] <= 4


# ---------------- 战斗 ----------------

def test_attack_roll():
    a = attack_roll(60, 40, "1d6", "+0")
    assert a["kind"] == "attack"
    assert a["hit"] in (True, False)
    assert a["damage"] >= 0
    assert a["weapon_dmg"] == "1d6"


# ---------------- CLI 向后兼容（回归：与归档版输出一致） ----------------

def _cli(*args: str):
    return subprocess.run(
        [sys.executable, str(ENGINE_DIR / args[0]), *args[1:]],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT),
    )


def test_roll_cli_backward_compat():
    r = _cli("roll.py", "1d100", "--no-log")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["ok"] is True and d["kind"] == "roll"
    assert 1 <= d["total"] <= 100


def test_check_cli_backward_compat():
    r = _cli("check.py", "skill", "侦查", "60")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["ok"] is True and d["kind"] == "check"
    assert d["skill"] == "侦查" and d["skill_value"] == 60


def test_build_cli_backward_compat():
    r = _cli("build.py", "CLI测试")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["ok"] is True and d["character"]["schema"] == "coc7-character/v1"
