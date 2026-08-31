# -*- coding: utf-8 -*-
"""规则引擎库（M1.2）：自归档 skill 复制并库化，供 Web 层 / 测试导入。

来源：`archive/coc7th-keeper-feishu/.dsh/skills/coc7th-keeper/scripts/`
（本目录为库化副本；原 skill 目录不动，飞书版仍可运行。）

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
