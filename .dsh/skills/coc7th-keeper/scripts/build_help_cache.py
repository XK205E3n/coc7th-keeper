# -*- coding: utf-8 -*-
"""预渲染 /coc help 输出到 references/help-cache.md (+ .json)。

为什么需要这个脚本：
  /coc help 是高频指令。如果每次都让 Agent 调 help.py 跑 stdout.buffer.write，
  DSH 的 plan-gate 会反复弹"请批准"对话框——既打断玩家，也消耗用户的注意力。

  本脚本把 help 文本**预渲染**到 workspace 内的 references/ 目录。Agent 收到
  /coc help 时只需要 read 一次即可，永远不会触发 plan-gate。

触发时机：
  - 首次部署（手动跑一次）
  - 新增 / 删除模组（手动跑一次重生）
  - 增删 /coc <指令> 时（手动跑一次）

输出位置：
  <skill-root>/references/help-cache.md   ← Agent read 的目标
  <skill-root>/references/help-cache.json ← 结构化（Agent 拼卡片用，可选）

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

# 复用 help.py 已有的渲染逻辑（单一权威源）
import help as _help_mod  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
CACHE_MD = SKILL_ROOT / "references" / "help-cache.md"
CACHE_JSON = SKILL_ROOT / "references" / "help-cache.json"


def cmd_build(verbose: bool = True) -> int:
    """重新生成两份 cache 文件。"""
    md = _help_mod.build_markdown()
    js = _help_mod.build_json()

    CACHE_MD.parent.mkdir(parents=True, exist_ok=True)
    CACHE_MD.write_text(md + "\n", encoding="utf-8")
    CACHE_JSON.write_text(
        json.dumps(js, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if verbose:
        # 统计
        n_static = sum(len(s["commands"]) for s in js["sections"])
        n_modules = len(js.get("modules", []))
        print(f"[help-cache] 写入 {CACHE_MD.relative_to(SKILL_ROOT)} "
              f"({len(md)} 字节, {n_static} 指令 + {n_modules} 模组)")
        print(f"[help-cache] 写入 {CACHE_JSON.relative_to(SKILL_ROOT)} "
              f"({len(json.dumps(js, ensure_ascii=False))} 字节)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="预渲染 /coc help 到 references/")
    ap.add_argument("--quiet", action="store_true", help="静默模式，不打印统计")
    args = ap.parse_args()
    try:
        return cmd_build(verbose=not args.quiet)
    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())