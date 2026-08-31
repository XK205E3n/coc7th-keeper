# -*- coding: utf-8 -*-
"""房间级 SSE 事件总线（M1.7）。

- 每房间 pub/sub：`publish(game_key, event, data, to_uid=None)`
- 30s 心跳注释行（防连接超时）
- 历史环形缓冲（每房间最近 N 条）：断线重连后先回放（按 to_uid 过滤，私密事件只回放给目标）

事件 wire 格式（实施方案 §4.1）：
    event: <name>
    data: <json>

私密感知（perception）事件：`to_uid` 指定目标，只推给该玩家连接。
"""
from __future__ import annotations

import asyncio
import json
from collections import deque
from typing import Any, AsyncIterator


class EventBus:
    def __init__(self, history_size: int = 50, heartbeat: float = 30.0):
        self._subs: dict[str, set[tuple[asyncio.Queue, str | None]]] = {}
        self._history: dict[str, deque] = {}
        self._lock = asyncio.Lock()
        self._history_size = history_size
        self.heartbeat = heartbeat

    # ---------- 发布 ----------

    async def publish(self, game_key: str, event: str, data: Any,
                      to_uid: str | None = None) -> None:
        """广播（to_uid=None）或定向推送（perception 等私密事件）。"""
        ev: dict = {"event": event, "data": data}
        if to_uid is not None:
            ev["to_uid"] = to_uid
        async with self._lock:
            h = self._history.setdefault(game_key, deque(maxlen=self._history_size))
            h.append(ev)
            targets = list(self._subs.get(game_key, ()))
        for queue, uid in targets:
            if to_uid is None or uid == to_uid:
                queue.put_nowait(ev)

    # ---------- 订阅（供 StreamingResponse 消费） ----------

    async def subscribe(self, game_key: str, uid: str | None = None) -> AsyncIterator[dict]:
        """异步生成器：先回放历史（过滤私密事件），再实时推送；断开时清理。"""
        queue: asyncio.Queue = asyncio.Queue()
        entry = (queue, uid)
        async with self._lock:
            self._subs.setdefault(game_key, set()).add(entry)

        # 回放最近事件（断线重连后全量校准的补强）
        async with self._lock:
            history = list(self._history.get(game_key, ()))
        for ev in history:
            if ev.get("to_uid") in (None, uid):
                yield ev

        try:
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=self.heartbeat)
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": {}}
                    continue
                if ev.get("to_uid") in (None, uid):
                    yield ev
        finally:
            async with self._lock:
                subs = self._subs.get(game_key)
                if subs:
                    subs.discard(entry)
                    if not subs:
                        self._subs.pop(game_key, None)

    # ---------- 统计（监视接口/测试用） ----------

    def subscriber_count(self, game_key: str) -> int:
        return len(self._subs.get(game_key, set()))


def format_sse(ev: dict) -> str:
    """把事件 dict 编码为 SSE wire 文本。"""
    if ev["event"] == "heartbeat":
        return ": ping\n\n"
    data = json.dumps(ev["data"], ensure_ascii=False)
    return f"event: {ev['event']}\ndata: {data}\n\n"
