# -*- coding: utf-8 -*-
"""配置 CLI：供 start-web.ps1 / stop-web.ps1 调用。

存在理由：PowerShell 5.1 向原生 exe 传参会剥掉内嵌双引号（native argument
quoting bug），`python -c "...\"server\"..."` 会变成裸 `server` 触发 NameError
（v1.0.3 实测踩坑）。把逻辑放进文件、命令行只传简单参数，彻底绕开该坑。

用法：
    python tools/config_cli.py get                       # 打印全量配置 JSON
    python tools/config_cli.py set-share-url <url>       # 写入 share_url 并回显
    python tools/config_cli.py set-dev-token <token>     # 设置开发者监视令牌并回显
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

    print("unknown command: %s（可选 get / set-share-url / set-dev-token）" % cmd, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
