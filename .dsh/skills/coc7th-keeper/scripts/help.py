# -*- coding: utf-8 -*-
"""CoC7th 守密人 /coc help 实现（权威渲染源）。

用法：
  help.py                    列出全部飞书指令（按 通用 / KP / PL 三组），含动态模组
  help.py md                 同上，但只输出可直接发到飞书群的 Markdown 字符串
  help.py json               输出结构化 JSON（供 Agent 拼装卡片用）

设计要点：
  - 单一权威源：本文件硬编码所有指令，避免依赖 Agent 是否照搬 SKILL.md 模板。
  - 动态模块：调用 modules.py 的扫描逻辑，确保 /coc modules 永远显示当前真实可用模组。
  - 一次拉取：把 help 当作可执行指令（落 dice.log？不落，仅 stdout）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 用 UTF-8 直接写 stdout，绕过 Windows GBK 控制台编码问题
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Py 3.7+
except Exception:  # pragma: no cover
    pass

sys.path.insert(0, str(Path(__file__).parent))
from _common import out  # noqa: E402
import modules as _modules_mod  # noqa: E402


# --------- 静态指令表（与 SKILL.md 第 4 节同步）---------
# 字段：(section, command, description, kw_flags)
#   section: "通用" | "KP" | "PL"
#   kw_flags: 是否在 Markdown 里加粗（突出显示）

COMMON = [
    ("help", "列出所有指令（本指令）", False),
    ("guide / 使用说明 / tutorial / 教程", "完整使用说明书（新人必读）", False),
    ("quickstart", "5 分钟快速上手", False),
    ("status", "查看房间与全部玩家状态", False),
    ("audit [--last N]", "最近 N 条投骰审计（掷骰与理由玩家可见）", False),
    ("save", "保存房间快照（群聊只回显相对路径）", False),
    ("load <快照路径>", "从快照恢复（路径用相对形式）", False),
    ("pwd", "显示当前房间数据目录（群聊只显示相对路径）", False),
]

KP = [
    ("init <房间号> [--module <id>]", "新建房间并指定模组（群聊输出不含机器路径）", False),
    ("scene <位置>", "描述当前位置", False),
    ("npc <名>", "召唤/查看 NPC 速查（群聊只显示玩家可见信息）", False),
    ("reveal <编号>", "解锁一条线索给玩家（只输出线索本身）", False),
    ("handout <文件>", "展示剧本附件", False),
    ("kp-note <内容>", "追加守密人私有笔记（内容永不外发）", False),
]

PL = [
    ("join", "加入房间", False),
    ("leave", "离开房间", False),
    ("build [--age N]", "随机生成角色（5d6 取大3）", False),
    ("use-pregen <名>", "选用预制角色（theron-quist / delphine-mcquire）", False),
    ("stat / sheet", "查看自己的角色卡", False),
    ("roll <表达式>", "任意投骰（1d100 / 2d6+3 / d20）", False),
    ("check <技能> [值] [--why ...]", "技能检定", False),
    ("luck", "幸运检定", False),
    ("attack <攻击技能> <对方闪避> <伤害骰> <伤害加值>", "攻击", False),
    ("dodge <对方攻击>", "闪避", False),
    ("san <损失量> [原因]", "理智损失检定", False),
    ("say <台词>", "角色发言，记入剧本日志", False),
]


def _mod_summary_lines() -> list[str]:
    """动态生成 /coc modules 列表的简短行（编号 + 中文名 + id）。"""
    res = _modules_mod.cmd_list()
    if not res.get("ok"):
        return ["（暂无可玩模组）"]
    lines = []
    for m in res.get("modules", []):
        lines.append(f"  - `#{m.get('number')} {m.get('cn')}` — `{m.get('id')}` · {m.get('players')} · {m.get('duration')}")
    return lines


def build_markdown() -> str:
    """生成可直接发到飞书群的 Markdown help 字符串。"""
    # 动态 /coc modules 行
    mod_list = _mod_summary_lines()
    modules_block = "\n".join(mod_list)
    count = len(mod_list) if mod_list != ["（暂无可玩模组）"] else 0

    def _line(cmd: str, desc: str) -> str:
        return f"- `/coc {cmd}` — {desc}"

    md = []
    md.append("📜 **CoC7th 守密人指令清单**")
    md.append("")
    md.append("**通用**")
    for cmd, desc, _ in COMMON:
        md.append(_line(cmd, desc))
    md.append(f"- **`/coc modules`** — 查看所有可玩模组（共 {count} 个，编号 + 中文名 + 简介）")
    md.append("- **`/coc modules <编号|id>`** — 查看某个模组的完整简介")
    md.append("")
    md.append("**守密人专用**")
    for cmd, desc, _ in KP:
        md.append(_line(cmd, desc))
    md.append("")
    md.append("**玩家专用**")
    for cmd, desc, _ in PL:
        md.append(_line(cmd, desc))
    md.append("")
    md.append("**当前可玩模组**")
    md.append(modules_block)
    md.append("")
    md.append("💡 **第一次玩？** 先看 `/coc 使用说明`，或者直接发 `/coc modules` 选一个模组。")
    md.append("")
    md.append("📖 想看更详细的工作流与场景示例？发 `/coc 使用说明` 即可。")
    return "\n".join(md)


def build_json() -> dict:
    """输出结构化 JSON：让 Agent 可以拼成飞书卡片。"""
    res = _modules_mod.cmd_list()
    mods = res.get("modules", []) if res.get("ok") else []
    return {
        "ok": True,
        "title": "CoC7th 守密人指令清单",
        "sections": [
            {
                "name": "通用",
                "commands": [
                    {"cmd": f"/coc {c}", "desc": d} for c, d, _ in COMMON
                ] + [
                    {"cmd": "/coc modules", "desc": f"查看所有可玩模组（共 {len(mods)} 个，编号 + 中文名 + 简介）", "highlight": True},
                    {"cmd": "/coc modules <编号|id>", "desc": "查看某个模组的完整简介", "highlight": True},
                ],
            },
            {
                "name": "守密人专用",
                "commands": [
                    {"cmd": f"/coc {c}", "desc": d} for c, d, _ in KP
                ],
            },
            {
                "name": "玩家专用",
                "commands": [
                    {"cmd": f"/coc {c}", "desc": d} for c, d, _ in PL
                ],
            },
        ],
        "modules": mods,
        "markdown": build_markdown(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="CoC7th /coc help 渲染")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("md", help="输出 Markdown 字符串")
    sub.add_parser("json", help="输出结构化 JSON")

    args = ap.parse_args()
    try:
        if args.cmd == "md":
            # 走 stdout.buffer.write(utf-8 字节) 而不是 print()：
            # print() 会先经 Windows GBK 控制台编码，UTF-8 中文会被替换为 '?'。
            # DSH 的 capture 拿到的也会是 '?' 字符串，导致 Agent 拿到乱码。
            # 用 buffer.write 直接送 UTF-8 字节流，DSH capture 拿到完整字符串。
            #
            # 提示：高频使用请改走 references/help-cache.md（build_help_cache.py
            # 预渲染）；本命令仍可用，但每次都会触发 plan-gate 审批。
            text = build_markdown() + "\n"
            sys.stdout.buffer.write(text.encode("utf-8"))
            sys.stdout.buffer.flush()
            return 0
        elif args.cmd == "json":
            out(build_json())
            return 0
    except Exception as e:
        return out({"ok": False, "error": str(e)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())