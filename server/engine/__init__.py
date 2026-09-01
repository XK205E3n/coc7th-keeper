# -*- coding: utf-8 -*-
"""规则引擎库（M1.2）：CoC7th 规则实现，供 Web 层 / 测试导入。

实现口径见 `docs/CoC7th规则依据与来源.md`（判定档位 / 派生公式 / 理智与战斗）。
其中 **SAN = POW**（与 POW 同为百分位刻度），不是 POW×5。

统一入口：
    roll_expr()            通用掷骰（含审计 payload）
    skill_check()          技能检定（= check_skill）
    luck_check()           幸运检定（= check_luck）
    check_opposed()        对抗检定
    check_combined()       联合检定
    build_character()      角色 build（属性/派生/技能）
    sanity_check_roll()    理智检定（纯函数，不动文件）
    perform_san_check()    理智检定（文件版，向后兼容）
    attack_roll()          攻击检定+伤害+DB（= attack_round）
    initiative()           先攻
    major_wound_roll()     重伤表
CLI 入口保留：`python server/engine/roll.py 1d100` 等。
"""
from __future__ import annotations

from server.engine._common import (  # noqa: F401
    append_dice_log,
    err,
    modules_dir,
    out,
    parse_dice,
    read_json,
    relabel,
    roll_expression,
    room_dir,
    secure_d100,
    secure_randint,
    seed_hex,
    session_root,
    write_json,
)
from server.engine.build import DEFAULT_SKILLS, build_character, derived, gen_attributes  # noqa: F401
from server.engine.check import (  # noqa: F401
    check_combined,
    check_luck,
    check_opposed,
    check_skill,
    judge,
    luck_check,
    skill_check,
)
from server.engine.combat import (  # noqa: F401
    MAJOR_WOUND_TABLE,
    attack_roll,
    attack_round,
    initiative,
    major_wound_roll,
    parse_db,
    parse_dmg,
)
from server.engine.roll import roll_expr  # noqa: F401
from server.engine.sanity import (  # noqa: F401
    MANIAS,
    PHOBIAS,
    REAL_INSANITY,
    perform_san_check,
    roll_indef_insanity,
    san_loss_die,
    san_loss_roll,
    sanity_check,
    sanity_check_roll,
)
