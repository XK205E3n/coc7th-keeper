# -*- coding: utf-8 -*-
"""CoC7th 可玩模组列表与简介查询 CLI。

用法：
  modules.py list                 列出所有可玩模组（编号 + 中英文名）
  modules.py show <id|编号>       显示指定模组的简介
  modules.py pick                 同 list，但在最后给出"选号回复"提示
  modules.py ids                  仅输出所有可用模组 ID（用于 /coc init --module 校验）

数据源：
  默认扫描 <coC_MODULES_DIR|skill-root>/modules/*/meta.json
  （模块根目录统一走 _common.modules_dir()：环境变量 COC_MODULES_DIR 优先，
   否则 = skill 根目录下 modules/，即 <skill-root>/modules/）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 用 UTF-8 直接写 stdout，绕过 Windows GBK 控制台编码问题
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Py 3.7+
except Exception:  # pragma: no cover
    pass

sys.path.insert(0, str(Path(__file__).parent))
from _common import modules_dir, out, read_json  # noqa: E402

# 解析 modules/ 目录：模块根目录统一锚定（工作区内）
MODULES_DIR = modules_dir()


def _load_all_modules() -> list[dict]:
    """扫描 modules/<id>/meta.json，返回按 number 升序的模组列表。"""
    if not MODULES_DIR.exists():
        return []
    out_list: list[dict] = []
    for child in sorted(MODULES_DIR.iterdir()):
        if not child.is_dir():
            continue
        meta_path = child / "meta.json"
        if not meta_path.exists():
            continue
        meta = read_json(meta_path, default={})
        if not meta or meta.get("schema") != "coc7-module/v1":
            continue
        # 确保 number 字段存在；若缺失则按目录顺序补
        if "number" not in meta:
            meta["number"] = 999
        out_list.append(meta)
    out_list.sort(key=lambda m: (m.get("number", 999), m.get("id", "")))
    return out_list


def _find_by_id_or_number(token: str, all_modules: list[dict]) -> dict | None:
    """按 ID 或编号查找模组。"""
    token = (token or "").strip()
    if not token:
        return None
    # 先按编号（数字）
    if token.isdigit():
        n = int(token)
        for m in all_modules:
            if int(m.get("number", -1)) == n:
                return m
    # 再按 ID（不区分大小写）
    low = token.lower()
    for m in all_modules:
        if m.get("id", "").lower() == low:
            return m
    return None


def cmd_list() -> dict:
    """列出所有可玩模组（编号 + 中英文名 + 简介）。"""
    modules = _load_all_modules()
    if not modules:
        # 隐私净化：错误信息只给友好相对标签，绝不暴露机器绝对路径；
        # 设 COC_DEBUG=1 时才输出真实目录供 KP 排查。
        label = str(MODULES_DIR) if os.environ.get("COC_DEBUG") else "modules"
        return {
            "ok": False,
            "error": f"未在 {label} 下找到任何 meta.json（schema=coc7-module/v1）",
            "modules": [],
        }
    items = []
    for m in modules:
        items.append({
            "number": m.get("number"),
            "id": m.get("id"),
            "cn": m.get("cn"),
            "name": m.get("name"),
            "players": m.get("players"),
            "duration": m.get("duration"),
            "tags": m.get("tags", []),
            "summary": m.get("summary", ""),
        })
    return {
        "ok": True,
        "count": len(items),
        # 隐私净化：默认输出模块根目录的相对标签，不暴露机器绝对路径；
        # 设 COC_DEBUG=1 时输出完整路径供 KP 排查。
        "modules_dir": str(MODULES_DIR) if os.environ.get("COC_DEBUG") else "modules",
        "modules": items,
    }


def cmd_show(token: str) -> dict:
    """显示一个模组的简介。"""
    modules = _load_all_modules()
    target = _find_by_id_or_number(token, modules)
    if not target:
        available = [f"{m.get('number')}.{m.get('cn')}({m.get('id')})" for m in modules]
        return {
            "ok": False,
            "error": f"找不到模组：{token!r}",
            "available": available,
        }
    return {"ok": True, "module": target}


def cmd_pick() -> dict:
    """list 的同义词，但在文案上提示用户'回复编号选择'，供 Agent 渲染时引用。"""
    res = cmd_list()
    res["hint"] = "回复数字编号即可查看该模组的简介，例如：2"
    return res


def cmd_ids() -> dict:
    """仅输出所有模组 ID 列表（用于校验 /coc init --module 的合法值）。"""
    modules = _load_all_modules()
    return {
        "ok": True,
        "ids": [m.get("id") for m in modules],
        "by_number": {str(m.get("number")): m.get("id") for m in modules},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="CoC7th 可玩模组查询")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出所有可玩模组")
    sub.add_parser("pick", help="列出可玩模组（带选号提示）")
    sub.add_parser("ids", help="输出所有可用模组 ID")
    p = sub.add_parser("show", help="显示一个模组的简介")
    p.add_argument("token", help="模组 ID 或编号")

    args = ap.parse_args()
    try:
        if args.cmd == "list":
            result = cmd_list()
        elif args.cmd == "pick":
            result = cmd_pick()
        elif args.cmd == "ids":
            result = cmd_ids()
        elif args.cmd == "show":
            result = cmd_show(args.token)
        else:
            result = {"ok": False, "error": f"未知命令：{args.cmd}"}
    except Exception as e:
        return out({"ok": False, "error": str(e)})

    out(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
