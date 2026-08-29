# -*- coding: utf-8 -*-
"""一键重生所有 references/ 缓存：help-cache + modules-cache。

用法：
  python build_all_cache.py
  python build_all_cache.py --quiet

跑完即把 references/help-cache.{md,json} 与 references/modules-cache.{md,json}
都重新生成。建议每次：
  - 增删指令（help.py 的 COMMON/KP/PL 表）
  - 增删 modules/<id>/meta.json

之后都跑一次本脚本。

只写 workspace 内 skill 目录，不读外部（DSH workspace-write 权限自动通过）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_help_cache as _help  # noqa: E402
import build_modules_cache as _modules  # noqa: E402

# 用 UTF-8 直接写 stdout，绕过 Windows GBK 控制台编码问题
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Py 3.7+
except Exception:  # pragma: no cover
    pass


def main() -> int:
    ap = argparse.ArgumentParser(description="重生所有 references/ 缓存")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    verbose = not args.quiet
    rc1 = _help.cmd_build(verbose=verbose)
    rc2 = _modules.cmd_build(verbose=verbose)
    if verbose:
        print("[build_all_cache] done")
    return rc1 or rc2


if __name__ == "__main__":
    raise SystemExit(main())