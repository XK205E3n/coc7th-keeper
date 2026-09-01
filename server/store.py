# -*- coding: utf-8 -*-
"""SQLite 存档层（M1.3）。

- 每游戏一个数据库：`data/games/<game_key>.db`（WAL 模式）
- 十张表：games / players / characters / rounds / messages / actions /
  dice_log / kp_notes / state_changes / perceptions
- 并发安全：WAL（读不阻塞写）+ 每操作独立连接事务 + API 层房间级写锁
  （见 server/roundman.py room_lock）

数据目录可用环境变量 `DATA_DIR` 覆盖（测试用临时目录）。
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from server import config

# 数据库连接锁：SQLite 连接不能在多线程间共享，每操作新建连接。
# __init__ 用到的模块级缓存注册表由 get_store() 持有。
_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
  game_key      TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  rule          TEXT NOT NULL DEFAULT 'coc7',
  module_id     TEXT,
  world_summary TEXT,
  host_uid      TEXT,
  password_hash TEXT,
  phase         TEXT NOT NULL DEFAULT 'lobby',
  round         INTEGER NOT NULL DEFAULT 0,
  current_scene TEXT,
  max_tokens    INTEGER,          -- 每局 LLM 输出上限覆盖（NULL=用 config 默认）
  created_at    INTEGER NOT NULL,
  updated_at    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS players (
  uid            TEXT PRIMARY KEY,
  game_key       TEXT NOT NULL REFERENCES games(game_key) ON DELETE CASCADE,
  name           TEXT NOT NULL,
  token_hash     TEXT,
  role_file      TEXT,
  is_host        INTEGER NOT NULL DEFAULT 0,
  is_away        INTEGER NOT NULL DEFAULT 0,
  has_submitted  INTEGER NOT NULL DEFAULT 0,
  action         TEXT,
  action_version INTEGER NOT NULL DEFAULT 0,
  joined_at      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_players_game ON players(game_key);
CREATE TABLE IF NOT EXISTS characters (
  uid        TEXT PRIMARY KEY,
  game_key   TEXT NOT NULL REFERENCES games(game_key) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  data       TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_characters_game ON characters(game_key);
CREATE TABLE IF NOT EXISTS rounds (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  game_key   TEXT NOT NULL REFERENCES games(game_key) ON DELETE CASCADE,
  round      INTEGER NOT NULL,
  phase      TEXT NOT NULL,
  started_at INTEGER NOT NULL,
  ended_at   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_rounds_game ON rounds(game_key, round);
CREATE TABLE IF NOT EXISTS messages (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  game_key   TEXT NOT NULL REFERENCES games(game_key) ON DELETE CASCADE,
  round      INTEGER NOT NULL,
  kind       TEXT NOT NULL,
  seq        INTEGER NOT NULL DEFAULT 0,
  payload    TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_game ON messages(game_key, id);
CREATE TABLE IF NOT EXISTS actions (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  game_key       TEXT NOT NULL REFERENCES games(game_key) ON DELETE CASCADE,
  round          INTEGER NOT NULL,
  uid            TEXT NOT NULL,
  text           TEXT NOT NULL,
  action_version INTEGER NOT NULL,
  submitted_at   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_actions_game ON actions(game_key, round, uid);
CREATE TABLE IF NOT EXISTS dice_log (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  game_key TEXT NOT NULL REFERENCES games(game_key) ON DELETE CASCADE,
  round    INTEGER,
  ts       INTEGER NOT NULL,
  kind     TEXT NOT NULL,
  payload  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dice_game ON dice_log(game_key, id);
CREATE TABLE IF NOT EXISTS kp_notes (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  game_key TEXT NOT NULL REFERENCES games(game_key) ON DELETE CASCADE,
  round    INTEGER,
  ts       INTEGER NOT NULL,
  text     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kp_game ON kp_notes(game_key, id);
CREATE TABLE IF NOT EXISTS state_changes (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  game_key   TEXT NOT NULL REFERENCES games(game_key) ON DELETE CASCADE,
  round      INTEGER NOT NULL,
  type       TEXT NOT NULL,
  uid        TEXT,
  payload    TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_state_game ON state_changes(game_key, round);
CREATE TABLE IF NOT EXISTS perceptions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  game_key   TEXT NOT NULL REFERENCES games(game_key) ON DELETE CASCADE,
  round      INTEGER NOT NULL,
  to_uid     TEXT NOT NULL,
  text       TEXT NOT NULL,
  clue_id    TEXT,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_perc_game ON perceptions(game_key, to_uid);
CREATE TABLE IF NOT EXISTS llm_log (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  game_key TEXT NOT NULL,
  round    INTEGER,
  ts       INTEGER NOT NULL,
  stage    TEXT NOT NULL,
  ok       INTEGER NOT NULL DEFAULT 0,
  ms       INTEGER NOT NULL DEFAULT 0,
  detail   TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_game ON llm_log(game_key, id);
CREATE TABLE IF NOT EXISTS clue_ledger (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  game_key    TEXT NOT NULL REFERENCES games(game_key) ON DELETE CASCADE,
  clue_id     TEXT NOT NULL,
  title       TEXT,
  text        TEXT NOT NULL,
  state       TEXT NOT NULL DEFAULT 'locked',   -- locked | unlocked（M7 线索台账）
  acquired_at INTEGER,
  acquired_by TEXT,
  UNIQUE(game_key, clue_id)
);
CREATE INDEX IF NOT EXISTS idx_ledger_game ON clue_ledger(game_key, state);
"""

_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{3,63}$")
_JSON_COLS = {"data", "payload", "world_summary", "action"}


def store_path(game_key: str) -> Path:
    """返回游戏数据库路径；非法的 key 直接报错（防路径穿越）。"""
    if not _KEY_RE.match(game_key):
        raise ValueError(f"非法的游戏标识: {game_key!r}")
    return config.games_dir() / f"{game_key}.db"


class GameStore:
    """单个游戏的 SQLite 存档。每操作新建连接（WAL），事务自动提交/回滚。"""

    def __init__(self, game_key: str):
        self.game_key = game_key
        self.path = store_path(game_key)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
            self._migrate(conn)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """轻量列迁移（兼容 M1 时代旧库）：games 表补 invite_token（M5.1）/ max_tokens。"""
        cols = {r[1] for r in conn.execute("PRAGMA table_info(games)").fetchall()}
        if "invite_token" not in cols:
            conn.execute("ALTER TABLE games ADD COLUMN invite_token TEXT")
        if "max_tokens" not in cols:
            conn.execute("ALTER TABLE games ADD COLUMN max_tokens INTEGER")

    # ---------- 连接 ----------

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        d = dict(row)
        for k in list(d):
            if k in _JSON_COLS and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except json.JSONDecodeError:
                    pass
        return d

    @staticmethod
    def _dump(v: Any) -> str:
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False)
        return str(v) if v is not None else None

    def _now(self) -> int:
        return int(time.time() * 1000)

    # ---------- games（房间） ----------

    def create_game(self, game_key: str, name: str, rule: str = "coc7",
                    module_id: str | None = None, world_summary: str | None = None,
                    host_uid: str | None = None,
                    password_hash: str | None = None) -> dict:
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO games (game_key, name, rule, module_id, world_summary,"
                " host_uid, password_hash, phase, round, current_scene, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?, 'lobby', 0, NULL, ?, ?)",
                (game_key, name, rule, module_id, world_summary, host_uid,
                 password_hash, now, now),
            )
        return self.get_game(game_key)

    def get_game(self, game_key: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM games WHERE game_key=?", (game_key,)).fetchone()
        return self._row(row)

    def update_game(self, game_key: str, **fields: Any) -> None:
        allowed = {"name", "rule", "module_id", "world_summary", "host_uid",
                   "password_hash", "phase", "round", "current_scene",
                   "invite_token", "max_tokens"}
        cols = [k for k in fields if k in allowed]
        if not cols:
            return
        sets = ", ".join(f"{c}=?" for c in cols)
        vals = [self._dump(fields[c]) if c in _JSON_COLS else fields[c] for c in cols]
        vals.append(self._now())
        with self._conn() as conn:
            conn.execute(
                f"UPDATE games SET {sets}, updated_at=? WHERE game_key=?",
                (*vals, game_key),
            )

    # ---------- players ----------

    def add_player(self, game_key: str, uid: str, name: str,
                   token_hash: str | None = None, is_host: bool = False) -> dict:
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO players (uid, game_key, name, token_hash, is_host,"
                " is_away, has_submitted, action, action_version, joined_at)"
                " VALUES (?,?,?,?,?,0,0,NULL,0,?)",
                (uid, game_key, name, token_hash, int(is_host), now),
            )
        return self.get_player(game_key, uid)

    def get_player(self, game_key: str, uid: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM players WHERE game_key=? AND uid=?", (game_key, uid)).fetchone()
        return self._row(row)

    def player_by_name(self, game_key: str, name: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM players WHERE game_key=? AND name=?", (game_key, name)).fetchone()
        return self._row(row)

    def list_players(self, game_key: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM players WHERE game_key=? ORDER BY joined_at", (game_key,)).fetchall()
        return [self._row(r) for r in rows]

    def update_player(self, game_key: str, uid: str, **fields: Any) -> None:
        allowed = {"name", "token_hash", "role_file", "is_host", "is_away",
                   "has_submitted", "action", "action_version"}
        cols = [k for k in fields if k in allowed]
        if not cols:
            return
        sets = ", ".join(f"{c}=?" for c in cols)
        vals = [self._dump(fields[c]) if c in _JSON_COLS else fields[c] for c in cols]
        with self._conn() as conn:
            conn.execute(
                f"UPDATE players SET {sets} WHERE game_key=? AND uid=?",
                (*vals, game_key, uid),
            )

    def delete_player(self, game_key: str, uid: str) -> None:
        """移除玩家（M5.4 踢人）；角色卡由 players.uid 外键 CASCADE 跟随删除。

        私密感知/状态变更等历史记录保留（审计需要）。
        """
        with self._conn() as conn:
            conn.execute("DELETE FROM players WHERE game_key=? AND uid=?",
                         (game_key, uid))

    def set_action(self, game_key: str, uid: str, round_no: int, text: str) -> int:
        """提交/修改行动：action_version 每次 +1，并写入 actions 表（审计）。

        返回新的 action_version。AI（M2）只读最后一次版本。
        """
        now = self._now()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT action_version, has_submitted FROM players"
                " WHERE game_key=? AND uid=?",
                (game_key, uid),
            ).fetchone()
            if row is None:
                raise KeyError(f"玩家 {uid} 不在房间 {game_key} 中")
            version = int(row["action_version"]) + 1
            conn.execute(
                "UPDATE players SET action=?, action_version=?, has_submitted=1"
                " WHERE game_key=? AND uid=?",
                (text, version, game_key, uid),
            )
            conn.execute(
                "INSERT INTO actions (game_key, round, uid, text, action_version, submitted_at)"
                " VALUES (?,?,?,?,?,?)",
                (game_key, round_no, uid, text, version, now),
            )
        return version

    def latest_actions(self, game_key: str, round_no: int) -> dict[str, dict]:
        """返回本轮每位玩家最后一次提交的行动（uid → {text, action_version}）。"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT uid, text, action_version FROM actions"
                " WHERE game_key=? AND round=?"
                "   AND id = (SELECT MAX(a2.id) FROM actions a2"
                "             WHERE a2.game_key=actions.game_key"
                "               AND a2.round=actions.round AND a2.uid=actions.uid)",
                (game_key, round_no),
            ).fetchall()
        return {r["uid"]: {"text": r["text"], "action_version": r["action_version"]} for r in rows}

    def list_action_history(self, game_key: str, round_no: int, uid: str | None = None) -> list[dict]:
        """行动修改历史（审计）：按版本升序。"""
        sql = ("SELECT id, round, uid, text, action_version, submitted_at FROM actions"
               " WHERE game_key=? AND round=?")
        args: list = [game_key, round_no]
        if uid is not None:
            sql += " AND uid=?"
            args.append(uid)
        sql += " ORDER BY id"
        with self._conn() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def reset_submissions(self, game_key: str) -> None:
        """回合推进后清空本轮行动（has_submitted/action/action_version 归零）。"""
        with self._conn() as conn:
            conn.execute(
                "UPDATE players SET has_submitted=0, action=NULL, action_version=0"
                " WHERE game_key=?",
                (game_key,),
            )

    # ---------- characters（角色卡） ----------

    def set_character(self, game_key: str, uid: str, name: str, data: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO characters (uid, game_key, name, data, updated_at)"
                " VALUES (?,?,?,?,?)"
                " ON CONFLICT(uid) DO UPDATE SET name=excluded.name,"
                " data=excluded.data, updated_at=excluded.updated_at",
                (uid, game_key, name, self._dump(data), self._now()),
            )

    def get_character(self, game_key: str, uid: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM characters WHERE game_key=? AND uid=?", (game_key, uid)).fetchone()
        return self._row(row)

    def list_characters(self, game_key: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM characters WHERE game_key=? ORDER BY name", (game_key,)).fetchall()
        return [self._row(r) for r in rows]

    # ---------- rounds（回合） ----------

    def add_round(self, game_key: str, round_no: int, phase: str, started_at: int,
                  ended_at: int | None = None) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO rounds (game_key, round, phase, started_at, ended_at)"
                " VALUES (?,?,?,?,?)",
                (game_key, round_no, phase, started_at, ended_at),
            )

    def list_rounds(self, game_key: str, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM rounds WHERE game_key=? ORDER BY id DESC LIMIT ?",
                (game_key, limit)).fetchall()
        return [dict(r) for r in rows]

    def advance_round(self, game_key: str, phase: str = "collecting") -> int:
        """推进一轮：round+1 → 记录 rounds → 清空行动提交。返回新轮次。"""
        now = self._now()
        with self._conn() as conn:
            row = conn.execute("SELECT round FROM games WHERE game_key=?", (game_key,)).fetchone()
            if row is None:
                raise KeyError(f"房间 {game_key} 不存在")
            new_round = int(row["round"]) + 1
            conn.execute(
                "UPDATE games SET round=?, phase=?, updated_at=? WHERE game_key=?",
                (new_round, phase, now, game_key),
            )
            conn.execute(
                "INSERT INTO rounds (game_key, round, phase, started_at) VALUES (?,?,?,?)",
                (game_key, new_round, phase, now),
            )
            conn.execute(
                "UPDATE players SET has_submitted=0, action=NULL, action_version=0"
                " WHERE game_key=?",
                (game_key,),
            )
        return new_round

    def set_phase(self, game_key: str, phase: str) -> None:
        """切换阶段（lobby/collecting/adjudicating/narrating），并记录 rounds 边界。"""
        now = self._now()
        with self._conn() as conn:
            row = conn.execute("SELECT round, phase FROM games WHERE game_key=?", (game_key,)).fetchone()
            if row is None:
                raise KeyError(f"房间 {game_key} 不存在")
            round_no = int(row["round"])
            if row["phase"] != phase:
                conn.execute(
                    "UPDATE rounds SET ended_at=? WHERE game_key=? AND round=? AND phase=? AND ended_at IS NULL",
                    (now, game_key, round_no, row["phase"]),
                )
            conn.execute(
                "UPDATE games SET phase=?, updated_at=? WHERE game_key=?",
                (phase, now, game_key),
            )
            conn.execute(
                "INSERT INTO rounds (game_key, round, phase, started_at) VALUES (?,?,?,?)",
                (game_key, round_no, phase, now),
            )

    # ---------- messages（叙事流） ----------

    def add_message(self, game_key: str, round_no: int, kind: str,
                    payload: dict, seq: int | None = None) -> int:
        now = self._now()
        if seq is None:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) + 1 AS s FROM messages WHERE game_key=?",
                    (game_key,)).fetchone()
                seq = int(row["s"])
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO messages (game_key, round, kind, seq, payload, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (game_key, round_no, kind, seq, self._dump(payload), now),
            )
        return int(cur.lastrowid)

    def list_messages(self, game_key: str, since_id: int = 0, limit: int = 200) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE game_key=? AND id>? ORDER BY id LIMIT ?",
                (game_key, since_id, limit)).fetchall()
        out = []
        for r in rows:
            d = self._row(r)
            d.setdefault("payload", {})
            out.append(d)
        return out

    # ---------- dice_log（审计） ----------

    def add_dice_log(self, game_key: str, kind: str, payload: dict,
                     round_no: int | None = None) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO dice_log (game_key, round, ts, kind, payload)"
                " VALUES (?,?,?,?,?)",
                (game_key, round_no, self._now(), kind, self._dump(payload)),
            )
        return int(cur.lastrowid)

    def list_dice_log(self, game_key: str, last: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM dice_log WHERE game_key=? ORDER BY id DESC LIMIT ?",
                (game_key, last)).fetchall()
        out = []
        for r in reversed(rows):
            d = self._row(r)
            d.setdefault("payload", {})
            out.append(d)
        return out

    # ---------- kp_notes（守密人笔记，绝不出玩家视图） ----------

    def add_kp_note(self, game_key: str, text: str, round_no: int | None = None) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO kp_notes (game_key, round, ts, text) VALUES (?,?,?,?)",
                (game_key, round_no, self._now(), text),
            )
        return int(cur.lastrowid)

    def list_kp_notes(self, game_key: str, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM kp_notes WHERE game_key=? ORDER BY id DESC LIMIT ?",
                (game_key, limit)).fetchall()
        return [dict(r) for r in rows]

    # ---------- state_changes（状态变动） ----------

    def add_state_change(self, game_key: str, round_no: int, change_type: str,
                         uid: str | None, payload: dict) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO state_changes (game_key, round, type, uid, payload, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (game_key, round_no, change_type, uid, self._dump(payload), self._now()),
            )
        return int(cur.lastrowid)

    def list_state_changes(self, game_key: str, round_no: int | None = None,
                           limit: int = 100) -> list[dict]:
        sql = "SELECT * FROM state_changes WHERE game_key=?"
        args: list = [game_key]
        if round_no is not None:
            sql += " AND round=?"
            args.append(round_no)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, args).fetchall()
        out = []
        for r in rows:
            d = self._row(r)
            d.setdefault("payload", {})
            out.append(d)
        return out

    # ---------- perceptions（私密感知，目标玩家可见） ----------

    def add_perception(self, game_key: str, round_no: int, to_uid: str,
                       text: str, clue_id: str | None = None) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO perceptions (game_key, round, to_uid, text, clue_id, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (game_key, round_no, to_uid, text, clue_id, self._now()),
            )
        return int(cur.lastrowid)

    def list_perceptions(self, game_key: str, to_uid: str | None = None,
                         limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM perceptions WHERE game_key=?"
        args: list = [game_key]
        if to_uid is not None:
            sql += " AND to_uid=?"
            args.append(to_uid)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    # ---------- llm_log（LLM 调用记录，M5.5 开发者监视） ----------

    def add_llm_log(self, game_key: str, stage: str, ok: bool, ms: int,
                    detail: str = "", round_no: int | None = None) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO llm_log (game_key, round, ts, stage, ok, ms, detail)"
                " VALUES (?,?,?,?,?,?,?)",
                (game_key, round_no, self._now(), stage, int(ok), int(ms), detail),
            )
        return int(cur.lastrowid)

    def list_llm_log(self, game_key: str, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM llm_log WHERE game_key=? ORDER BY id DESC LIMIT ?",
                (game_key, limit)).fetchall()
        return [dict(r) for r in rows]

    # ---------- clue_ledger（线索台账，M7 建议） ----------

    def init_clue_ledger(self, game_key: str, clues: list[dict]) -> int:
        """建团时初始化线索台账副本（clues.md 的结构化清单）。已存在则忽略。"""
        count = 0
        with self._conn() as conn:
            for c in clues:
                cid = str(c.get("id", "")).strip()
                if not cid:
                    continue
                cur = conn.execute(
                    "INSERT OR IGNORE INTO clue_ledger (game_key, clue_id, title, text, state)"
                    " VALUES (?,?,?,?,'locked')",
                    (game_key, cid, str(c.get("title") or ""),
                     str(c.get("text") or "")),
                )
                count += cur.rowcount
        return count

    def unlock_clue(self, game_key: str, clue_id: str, uid: str | None = None) -> bool:
        """线索获得时更新台账状态（locked → unlocked + 时间/获得者）。"""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE clue_ledger SET state='unlocked', acquired_at=?, acquired_by=?"
                " WHERE game_key=? AND clue_id=? AND state='locked'",
                (self._now(), uid, game_key, clue_id),
            )
            return cur.rowcount > 0

    def list_clue_ledger(self, game_key: str,
                         state: str | None = None) -> list[dict]:
        sql = "SELECT * FROM clue_ledger WHERE game_key=?"
        args: list = [game_key]
        if state in ("locked", "unlocked"):
            sql += " AND state=?"
            args.append(state)
        sql += " ORDER BY id"
        with self._conn() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]


# ---------------- 注册表 ----------------

_stores: dict[str, GameStore] = {}
_stores_lock = threading.Lock()


def get_store(game_key: str) -> GameStore:
    """获取（按需创建）游戏存档。单进程内缓存连接级对象（连接按操作新建，安全）。"""
    with _stores_lock:
        st = _stores.get(game_key)
        if st is None:
            st = GameStore(game_key)
            _stores[game_key] = st
        return st


def close_store(game_key: str) -> None:
    """释放缓存（可选；进程结束自动清理）。"""
    with _stores_lock:
        _stores.pop(game_key, None)
