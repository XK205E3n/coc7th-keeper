# -*- coding: utf-8 -*-
"""CoC7th 理智机制 CLI。

SAN 损失判定：
  loss 1        → 无效果（成功时 0/1d3，失败时 1d3）
  loss 2-4      → 成功 0 / 失败 1d4
  loss 5+       → 成功 0 / 失败 1d6 → 触发"实时疯狂"（不定或临时）
  0             → 失败时 1d10

实时疯狂 / 临时疯狂 / 不定疯狂（简化）：
  实时疯狂   → 取"疯狂发作表"1d10（简化版文本）
  临时疯狂   → 1d10 小时发作 + 取"恐惧症/躁狂表"
  不定疯狂   → PL 与 KP 协商重塑人物概念

成功阈值比较（CoC7th SAN check）：
  skill = 当前 SAN（即 SAN × 5 在 build 后；按当前 SAN 投）
  失败 → 掷 SAN 损失骰（按上表）
  成功 → 损失掷 0
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

# 用 UTF-8 直接写 stdout，绕过 Windows GBK 控制台编码问题
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Py 3.7+
except Exception:  # pragma: no cover
    pass

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    append_dice_log, out, secure_d100, read_json, write_json, room_dir,
    session_root,
)


def _resolve_player_file(player_file: str) -> Path:
    """把 --player-file 解析为绝对路径。

    优先级：
      1) 原样当 Path 试一次（用户给的已经是绝对路径）
      2) 相对路径一律相对 COC_SESSION_ROOT 解析（避免跨工作区写错）
      3) 也支持 "demo/players/alice.json" 这种相对 session 根的写法
    """
    p = Path(player_file)
    if p.is_absolute():
        return p
    # 相对路径 → 锚定到 session root
    return (session_root() / p).resolve()


# ---------- SAN 损失骰表 ----------
def san_loss_die(loss: int) -> tuple[int, int]:
    """返回 (骰面数, 失败时损失值个数)；成功损失为 0。"""
    if loss <= 0:    return (10, 1)
    if loss == 1:    return (3, 1)
    if loss <= 4:    return (4, 1)
    return (6, 1)


# ---------- 疯狂表（简化） ----------
REAL_INSANITY = [
    "1. 失忆：你醒来，发现自己身处陌生之地，身上带伤，无人来救。",
    "2. 暴力：你像野兽一样狂怒，对周围一切事物进行破坏。",
    "3. 偏执：你感到被跟踪，丧失对周围人的信任。",
    "4. 恐慌：你极度恐慌，无法移动或自控。",
    "5. 惊厥：你陷入短暂的肌肉痉挛，可能失去意识。",
    "6. 恍惚：你陷入失神状态，对外界刺激毫无反应。",
    "7. 歇斯底里：你大笑、尖叫或哭泣，无法自我控制。",
    "8. 恐惧症：你突然对某个常见物品产生极端恐惧。",
    "9. 躁狂：你陷入极度乐观或自大状态，丧失现实感。",
    "10. 自残：你伤害自己，可能造成严重后果。",
]

PHOBIAS = [
    "害怕黑暗", "害怕密闭空间", "害怕高处", "害怕开放空间",
    "害怕水", "害怕火", "害怕血液", "害怕昆虫",
    "害怕陌生人", "害怕孤独", "害怕人群", "害怕野兽",
    "害怕噪音", "害怕镜子", "害怕触摸", "害怕死亡",
    "害怕疾病", "害怕魔法/超自然", "害怕自己", "害怕过去",
]

MANIAS = [
    "沉迷书籍", "囤积物品", "酗酒", "沉迷工作",
    "不停洗手", "不停自言自语", "画符号", "记下一切",
    "观察他人", "反复开关门/灯", "囤积食物", "熬夜",
    "拒绝睡眠", "反复回忆", "寻找意义", "自我伤害",
    "远离他人", "依赖他人", "恋物", "强迫清洁",
]


def roll_die(faces: int) -> int:
    return secrets.randbelow(faces) + 1


def san_loss_roll(loss: int) -> int:
    faces, n = san_loss_die(loss)
    return sum(roll_die(faces) for _ in range(n))


def sanity_check_roll(san_skill: int, loss: int, by: str = "kp", why: str = "") -> dict:
    """库化纯函数（M1.2）：按当前 SAN 值做一次理智检定，不读写角色文件。

    返回判定字段（与 perform_san_check 一致，不含 `ok` 包装）：
    kind / success / roll / skill / loss_source / actual_loss / current_san /
    insane_now / insane_kind。
    """
    if loss < 0:
        raise ValueError("理智损失必须 >= 0")
    roll = secure_d100()
    success = roll <= san_skill

    if success:
        actual_loss = 0
        insane_now = False
        insane_kind = None
    else:
        actual_loss = san_loss_roll(loss)
        insane_now = loss >= 5
        if insane_now:
            # 实时疯狂：掷 1d10
            r = roll_die(10)
            insane_kind = {"type": "real", "table_hit": r,
                           "table_text": REAL_INSANITY[r-1]}
        else:
            insane_kind = None

    return {
        "kind": "san_check",
        "by": by,
        "why": why,
        "loss_source": loss,
        "skill": san_skill,
        "roll": roll,
        "success": success,
        "actual_loss": actual_loss,
        "current_san": max(0, san_skill - actual_loss) if not success else san_skill,
        "insane_now": insane_now,
        "insane_kind": insane_kind,
    }


def perform_san_check(player_file: Path, loss: int, san_skill: int | None = None,
                      by: str = "kp", why: str = "") -> dict:
    if loss < 0:
        raise ValueError("理智损失必须 >= 0")
    char = read_json(player_file, default={})
    if san_skill is None:
        # 用当前 SAN 作为技能值（CoC7th 标准做法）
        san_skill = char.get("sanity", {}).get("current", 50)
    result = sanity_check_roll(san_skill, loss, by, why)

    # 更新角色卡
    if char:
        s = char.setdefault("sanity", {"current": san_skill, "max": san_skill, "history": []})
        s["current"] = result["current_san"]
        s["history"] = s.get("history", []) + [{
            "ts": None, "roll": result["roll"], "skill": san_skill,
            "loss": result["actual_loss"], "reason": why,
            "insane_kind": result["insane_kind"],
        }]
        write_json(player_file, char)

    result["ok"] = True
    return result


# 库化别名（M1.2）：sanity_check() 保持文件版入口；Web 层用纯函数 sanity_check_roll()。
sanity_check = perform_san_check


def roll_indef_insanity() -> dict:
    """不定/临时疯狂的骰子：从恐惧症或躁狂各取一项。"""
    return {
        "phobia": PHOBIAS[roll_die(len(PHOBIAS)) - 1],
        "mania": MANIAS[roll_die(len(MANIAS)) - 1],
        "duration_hours": roll_die(10),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="CoC7th 理智机制")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("check", help="SAN 检定")
    p1.add_argument("--player-file", required=True)
    p1.add_argument("loss", type=int)
    p1.add_argument("--skill", type=int, default=None)
    p1.add_argument("--by", default="kp"); p1.add_argument("--why", default="")
    p1.add_argument("--room", default=None)

    p2 = sub.add_parser("indef", help="掷不定/临时疯狂表（恐惧症+躁狂）")
    args = ap.parse_args()

    if args.cmd == "check":
        rd = room_dir(args.room); rd.mkdir(parents=True, exist_ok=True)
        pf = _resolve_player_file(args.player_file)
        result = perform_san_check(pf, args.loss, args.skill, args.by, args.why)
        append_dice_log(rd, result)
        out(result)
    else:
        out({"ok": True, **roll_indef_insanity()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
