# -*- coding: utf-8 -*-
"""打印当前可用的游玩网址（M8R8 · 一键开启.bat 收尾显示件）。

用法：
    python tools/print_urls.py          # 打印网址汇总块（本地 / 公网 / 密码状态 / 关闭方式）
    python tools/print_urls.py check    # 仅探测后端是否健康：exit 0 = 在跑，1 = 未跑（不打印）

只读 config 与健康检查端点，不做任何写操作；不打印密码明文。
"""
import json
import os
import sys
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "server")))

import config  # noqa: E402


def backend_healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health", timeout=1.5) as r:
            return json.load(r).get("status") == "ok"
    except Exception:
        return False


def main() -> int:
    cfg = config.load_config()
    port = int(cfg["server"]["port"])
    healthy = backend_healthy(port)

    if len(sys.argv) > 1 and sys.argv[1] == "check":
        return 0 if healthy else 1

    share = cfg.get("share_url")
    provider = (cfg.get("tunnel") or {}).get("provider", "?")
    pwd_state = "已设置（进站需输入密码）" if cfg.get("access_password") \
        else "未设置（公网任何人可进站）"
    if not healthy:
        note = "（后端当前未运行——若是刚执行一键开启失败，请查看上方报错；可双击「一键关闭.bat」清理后重试）"
    elif not share:
        note = "（公网地址未取得——穿透未成功；本机游玩可用本地地址）"
    else:
        note = ""
    print("=" * 60)
    print(" 🎲 跑团平台网址汇总")
    print("-" * 60)
    print(f" 后端状态　：{'运行中' if healthy else '未运行'}")
    print(f" 本机游玩　： http://localhost:{port}")
    print(f" 公网分享　： {share if share else '（未取得）'} {note}")
    print(f" 隧道类型　： {provider}")
    print(f" 进站密码　： {pwd_state}")
    print("-" * 60)
    print(" 关闭方式　：双击根目录「一键关闭.bat」，")
    print(" 　　　　　　或命令行执行  .\\stop-web.ps1")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
