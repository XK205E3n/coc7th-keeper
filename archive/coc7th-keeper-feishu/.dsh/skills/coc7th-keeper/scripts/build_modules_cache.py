# -*- coding: utf-8 -*-
"""预渲染 /coc modules 输出到 references/modules-cache.md (+ .json)。

为什么需要这个脚本：
  /coc modules 是高频指令。如果每次都让 Agent 调 modules.py，
  DSH 的 plan-gate 会反复弹"请批准"对话框——既打断玩家，也消耗用户注意力。

  本脚本把模块列表**预渲染**到 workspace 内的 references/ 目录。Agent 收到
  /coc modules 时只需要 read 一次即可，永远不会触发 plan-gate。

触发时机：
  - 新增 / 删除模组（手动跑一次重生）
  - 修改任何 modules/<id>/meta.json（手动跑一次重生）

输出位置：
  <skill-root>/references/modules-cache.md
  <skill-root>/references/modules-cache.json

本脚本只写 workspace 内的 skill 目录（DSH workspace-write 权限自动放行），
不读外部、不写 ~/.dsh/（避免需要 danger-full-access）。
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
import modules as _modules_mod  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
CACHE_MD = SKILL_ROOT / "references" / "modules-cache.md"
CACHE_JSON = SKILL_ROOT / "references" / "modules-cache.json"

def _render_markdown(data: dict) -> str:
    """把模块列表渲染成 SKILL.md 第 9 节里那张可直接发到飞书群的表格。"""
    if not data.get("ok"):
        return (
            "📚 **可玩模组**\n\n"
            f"> ⚠️ {data.get('error', '暂无可玩模组')}\n"
        )
    mods = data.get("modules", [])
    if not mods:
        return "📚 **可玩模组**\n\n> （暂无可玩模组）\n"

    lines = [f"📚 **可玩模组（共 {len(mods)} 个）**", ""]
    lines.append("| # | 模组 ID | 中文名 | 推荐人数 | 时长 |")
    lines.append("|---|---|---|---|---|")
    for m in mods:
        lines.append(
            f"| {m.get('number')} | `{m.get('id')}` | {m.get('cn')} | "
            f"{m.get('players', '-')} | {m.get('duration', '-')} |"
        )
    lines.append("")
    lines.append("> 回复 **数字编号** 即可查看该模组的完整简介，例如：`2`")
    lines.append("> 或直接 `/coc modules <编号|id>` 查看详情。")
    lines.append("")
    # 简介列表
    lines.append("**简介速览**")
    for m in mods:
        summary = (m.get("summary") or "").strip()
        if summary:
            lines.append(f"- **#{m.get('number')} {m.get('cn')}** —— {summary}")
    lines.append("")
    return "\n".join(lines)


def _render_per_module_cache(mods: list[dict]) -> dict[str, str]:
    """为每个模块生成一份独立的 Markdown 缓存（用于 /coc modules <编号>）。"""
    out: dict[str, str] = {}
    for m in mods:
        tags = m.get("tags") or []
        tag_str = "、".join(tags) if isinstance(tags, list) else str(tags)
        md = []
        md.append(f"📖 **模组简介：{m.get('cn')}**")
        md.append(f"- **编号**：{m.get('number')} ｜ **模组 ID**：`{m.get('id')}`")
        md.append(f"- **英文名**：{m.get('name', '-')}")
        md.append(f"- **系统**：COC7th ｜ **推荐人数**：{m.get('players', '-')} "
                  f"｜ **时长**：{m.get('duration', '-')}")
        if tag_str:
            md.append(f"- **标签**：{tag_str}")
        md.append("")
        summary = (m.get("summary") or "").strip()
        if summary:
            md.append(summary)
        md.append("")
        md.append("💡 **KP 接下来**：确认玩此模组后请发送 "
                  f"`/coc init <房间号> --module {m.get('id')} --kp <你的名字>`。")
        out[str(m.get("number"))] = "\n".join(md)
        out[m.get("id", "")] = "\n".join(md)
    return out


def cmd_build(verbose: bool = True) -> int:
    list_data = _modules_mod.cmd_list()
    md_main = _render_markdown(list_data)
    per_module = _render_per_module_cache(list_data.get("modules", []) or [])

    CACHE_MD.parent.mkdir(parents=True, exist_ok=True)
    CACHE_MD.write_text(md_main + "\n", encoding="utf-8")

    payload = {
        "ok": list_data.get("ok", False),
        "count": len(list_data.get("modules", []) or []),
        "modules": list_data.get("modules", []) or [],
        "markdown_main": md_main,
        "markdown_by_token": per_module,
    }
    CACHE_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if verbose:
        n_mods = len(list_data.get("modules", []) or [])
        print(f"[modules-cache] 写入 {CACHE_MD.relative_to(SKILL_ROOT)} "
              f"({len(md_main)} 字节, {n_mods} 模组)")
        print(f"[modules-cache] 写入 {CACHE_JSON.relative_to(SKILL_ROOT)} "
              f"({n_mods * 2} 个 per-module 缓存)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="预渲染 /coc modules 到 references/")
    ap.add_argument("--quiet", action="store_true", help="静默模式")
    args = ap.parse_args()
    try:
        return cmd_build(verbose=not args.quiet)
    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())