# -*- coding: utf-8 -*-
"""每 IP 访问限流（M6.5）：滑动窗口，仅作用于 /api。

- 每分钟 per_minute 次（上限）
- 单秒 burst 次（突发上限，防脚本连发）
- 内存实现（单进程够用）；跨进程/多实例部署再换 Redis
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, per_minute: int = 300, burst: int = 20):
        self.per_minute = max(1, int(per_minute))
        self.burst = max(1, int(burst))
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, ip: str) -> bool:
        """放行返回 True；超限返回 False（调用方回 429）。"""
        now = time.time()
        with self._lock:
            dq = self._hits[ip if ip else "unknown"]
            # 清理 60s 前的时间戳
            while dq and dq[0] <= now - 60:
                dq.popleft()
            if len(dq) >= self.per_minute:
                return False
            # 单秒突发
            recent_1s = sum(1 for t in dq if t > now - 1)
            if recent_1s >= self.burst:
                return False
            dq.append(now)
            return True

    def reset(self, ip: str | None = None) -> None:
        with self._lock:
            if ip is None:
                self._hits.clear()
            else:
                self._hits.pop(ip, None)
