# -*- coding: utf-8 -*-
"""配置 CLI：供 start-web.ps1 / stop-web.ps1 调用。

存在理由：PowerShell 5.1 向原生 exe 传参会剥掉内嵌双引号（native argument
quoting bug），`python -c "...\"server\"..."` 会变成裸 `server` 触发 NameError
（v1.0.3 实测踩坑）。把逻辑放进文件、命令行只传简单参数，彻底绕开该坑。

用法：
    python tools/config_cli.py get                       # 打印全量配置 JSON
    python tools/config_cli.py set-share-url <url>       # 写入 share_url 并回显
    python tools/config_cli.py set-dev-token <token>     # 设置开发者监视令牌并回显
    python tools/config_cli.py set-access-password <pwd> # 设置进站密码（M8R8，不回显明文）
    python tools/config_cli.py ensure-access-password    # 未设密码时交互式补设（M8R8；
                                                         #  密码经 input 输入，不进命令行历史）
"""
import json
import os
import sys

# server/ 目录加入 sys.path（基于本文件定位，与 CWD 无关）
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "server")))

import config  # noqa: E402


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "get"

    if cmd == "get":
        print(json.dumps(config.load_config()))
        return 0

    if cmd == "set-share-url":
        if len(args) < 2:
            print("usage: config_cli.py set-share-url <url>", file=sys.stderr)
            return 1
        c = config.load_config()
        c["share_url"] = args[1]
        config.save_config(c)
        print(c["share_url"])
        return 0

    if cmd == "set-dev-token":
        if len(args) < 2:
            print("usage: config_cli.py set-dev-token <token>", file=sys.stderr)
            return 1
        c = config.load_config()
        c["dev_token"] = args[1]
        config.save_config(c)
        print(c["dev_token"])
        return 0

    if cmd == "set-access-password":
        if len(args) < 2:
            print("usage: config_cli.py set-access-password <pwd>", file=sys.stderr)
            return 1
        c = config.load_config()
        c["access_password"] = args[1]
        config.save_config(c)
        print("进站密码已保存（不回显明文）。")
        return 0

    if cmd == "ensure-access-password":
        c = config.load_config()
        if c.get("access_password"):
            print("进站密码已设置，跳过。")
            return 0
        try:
            pwd = input("设置进站密码（公网进站需输入；直接回车 = 不设密码）：").strip()
        except (EOFError, KeyboardInterrupt):
            pwd = ""
        if not pwd:
            print("未设置密码：公网任何人可进站（之后可运行 set-access-password 补设）。")
            return 0
        c["access_password"] = pwd
        config.save_config(c)
        print("进站密码已保存到 data/config.json。")
        return 0

    print("unknown command: %s（可选 get / set-share-url / set-dev-token /"
          " set-access-password / ensure-access-password）" % cmd, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
