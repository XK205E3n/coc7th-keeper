# -*- coding: utf-8 -*-
"""coc7th-keeper 共用工具

- 解析工作区路径（环境变量 COC_SESSION_ROOT 优先；否则 ./coc-session）
- CSPRNG（secrets.SystemRandom）单例
- 写骰子审计 log（append-only；含 ts / caller / expr / seed / result）
- 读/写 JSON 时统一编码与中文
- 安全打印到 stdout（不阻塞非 UTF-8 控制台）
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any


# -------------------- 路径 --------------------

def session_root() -> Path:
    """返回当前房间工作区根目录。

    优先级：
      1) 环境变量 COC_SESSION_ROOT
      2) 当前工作目录下 ./coc-session
    """
    env = os.environ.get("COC_SESSION_ROOT")
    return Path(env).resolve() if env else (Path.cwd() / "coc-session").resolve()


def room_dir(room_id: str | None = None) -> Path:
    """返回指定房间目录；未指定则从 room.json / 环境变量 / 默认 'default'。"""
    if not room_id:
        env = os.environ.get("COC_ROOM")
        room_id = env or "default"
    return session_root() / room_id


def ensure_room(room_id: str) -> Path:
    """确保房间目录与必备子目录存在。"""
    base = room_dir(room_id)
    (base / "players").mkdir(parents=True, exist_ok=True)
    return base


def modules_dir() -> Path:
    """返回可玩模组根目录。

    优先级：
      1) 环境变量 COC_MODULES_DIR（把预设模组的目标目录显式锚定到任意工作区目录）
      2) <skill-root>/modules（默认：skill 根目录下的 modules/，随工作区走）

    目标：所有预设模组的目标目录都必须落在 DSH 工作区内，
    由各脚本（modules.py / room.py / use_pregen.py / build_modules_cache.py）统一走本函数。
    """
    env = os.environ.get("COC_MODULES_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent.parent / "modules"


def relabel(path: Path) -> str:
    """把机器绝对路径转成对人友好的相对标签（隐私净化）。

    - 在 COC_SESSION_ROOT 下 → "coc-session/<相对路径>"
    - 否则在 cwd 下 → 相对 cwd
    - 否则只保留文件名（绝不回显盘符/机器绝对路径，如 D:\\... / C:\\Users/...）

    设置 COC_DEBUG=1 时始终返回绝对路径（KP/管理员排查用，绝不用于群聊输出）。
    """
    if os.environ.get("COC_DEBUG"):
        return str(path)
    p = Path(path)
    root = session_root()
    try:
        rel = p.resolve().relative_to(root.resolve())
    except ValueError:
        rel = None
    if rel is not None:
        if str(rel) == ".":
            return "coc-session"
        return "coc-session/" + rel.as_posix()
    try:
        rel = p.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return p.name or str(p)
    if str(rel) == ".":
        return "."
    return rel.as_posix()


# -------------------- 随机数 --------------------

_RNG = secrets.SystemRandom()


def secure_randint(a: int, b: int) -> int:
    """加密安全 [a, b] 区间整数。"""
    return _RNG.randint(a, b)


def secure_d100() -> int:
    """加密安全 1d100。"""
    return secure_randint(1, 100)


def seed_hex(nbytes: int = 8) -> str:
    """返回当前调用点附带的随机种子（hex），仅用于审计可回放。"""
    return secrets.token_hex(nbytes)


# -------------------- 表达式投骰 --------------------

def parse_dice(expr: str) -> tuple[int, int, int]:
    """解析 'NdM[+/-K]' 为 (n, m, k)。

    接受 '1d100', '2d6+1', '3d10-2', 'd20' (n=1)。
    """
    e = expr.strip().lower().replace(" ", "")
    sign = 1
    if e.startswith("-"):
        sign = -1
        e = e[1:]
    elif e.startswith("+"):
        e = e[1:]
    k = 0
    head = e  # 默认就是整个表达式（无 +/-K 时）
    if "+" in e:
        head, k_str = e.split("+", 1)
        k = int(k_str) * sign
    elif "-" in e:
        head, k_str = e.split("-", 1)
        k = -int(k_str)
    if "d" not in head:
        raise ValueError(f"非法骰子表达式: {expr}")
    n_str, m_str = head.split("d", 1)
    n = int(n_str) if n_str else 1
    m = int(m_str)
    if n <= 0 or n > 1000 or m <= 0 or m > 10000:
        raise ValueError(f"骰子表达式超出允许范围: {expr}")
    return n, m, k


def roll_expression(expr: str) -> dict:
    """执行 'NdM[+/-K]' 并返回审计 dict。"""
    n, m, k = parse_dice(expr)
    rolls = [secure_randint(1, m) for _ in range(n)]
    total = sum(rolls) + k
    return {
        "expr": expr,
        "n": n, "m": m, "k": k,
        "rolls": rolls,
        "total": total,
    }


# -------------------- 审计日志 --------------------

def append_dice_log(room_dir_path: Path, entry: dict) -> None:
    """追加一条骰子审计记录到 dice.log（NDJSON，每行一条）。

    不可篡改性靠：文件路径对外只 append；如需强一致请配合 git hook / OS ACL。
    """
    (room_dir_path).mkdir(parents=True, exist_ok=True)
    log = room_dir_path / "dice.log"
    entry = {"ts": int(time.time() * 1000), **entry}
    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
    with log.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# -------------------- JSON IO --------------------

def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False),
        encoding="utf-8",
    )


# -------------------- 输出 --------------------

def out(obj: Any) -> None:
    """向 stdout 输出 JSON 结果（带 UTF-8 BOM 头兼容 Windows 控制台）。"""
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    try:
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
    except Exception:
        sys.stdout.write(text + "\n")


def err(msg: str, code: int = 1) -> None:
    sys.stderr.write(f"ERROR: {msg}\n")
    sys.exit(code)
