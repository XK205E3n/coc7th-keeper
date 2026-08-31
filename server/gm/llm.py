# -*- coding: utf-8 -*-
"""LLM 客户端（M2.2）：AsyncOpenAI 封装。

- 从 `data/config.json`（model.*）+ `data/secrets.json`（api_key）构建
- chat() 失败重试 2 次（指数退避）；LLM 不可用（无 api_key / 网络错误）返回 None
  → 上层（adjudicate/narrate）走规则兜底，**不阻塞状态应用**
- json_mode=True 时要求 provider 输出 JSON 对象（OpenAI 兼容 response_format）
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("gm.llm")


class LLMClient:
    """OpenAI 兼容客户端（DeepSeek / Ollama / 硅基流动等）。"""

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, timeout: float = 90.0):
        self.base_url = base_url or None
        self.api_key = api_key or ""
        self.model = model or "deepseek-chat"
        self.timeout = timeout
        self.available = bool(self.api_key) and self.api_key not in ("", "sk-no-key")
        self._client: Any = None
        if self.available:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    base_url=self.base_url, api_key=self.api_key, timeout=timeout)
            except Exception:  # noqa: BLE001
                logger.exception("AsyncOpenAI 初始化失败，进入离线模式")
                self.available = False
                self._client = None

    @classmethod
    def from_config(cls, cfg: dict | None = None, secrets: dict | None = None) -> "LLMClient":
        """从 data/config.json + data/secrets.json 构建。"""
        from server import config
        cfg = cfg or config.load_config()
        secrets = secrets or config.load_secrets()
        m = cfg.get("model", {}) or {}
        return cls(
            base_url=m.get("base_url"),
            api_key=secrets.get("api_key"),
            model=m.get("model"),
        )

    # ---------- 对话 ----------

    async def chat(self, messages: list[dict], max_tokens: int = 2000,
                   json_mode: bool = False, temperature: float = 0.7,
                   retries: int = 2) -> str | None:
        """单轮对话。失败重试 retries 次；最终失败返回 None（降级信号）。"""
        if not self.available or self._client is None:
            return None
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = await self._client.chat.completions.create(**kwargs)
                content: str | None = resp.choices[0].message.content
                return content.strip() if content else None
            except Exception as e:  # noqa: BLE001
                last_err = e
                logger.warning("LLM 调用失败(第 %d 次): %s", attempt + 1, e)
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
        return None

    # ---------- 便捷 ----------

    def is_available(self) -> bool:
        return self.available
