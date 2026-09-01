# -*- coding: utf-8 -*-
"""LLM 客户端（M2.2）：AsyncOpenAI 封装。

- 从 `data/config.json`（model.*）+ `data/secrets.json`（api_key）构建
- chat() 失败重试 2 次（指数退避）；LLM 不可用（无 api_key / 网络错误）返回 None
  → 上层（adjudicate/narrate）走规则兜底，**不阻塞状态应用**
- json_mode=True 时要求 provider 输出 JSON 对象（OpenAI 兼容 response_format）
- **隐私铁律（推理模型）**：只读取 `message.content`（最终输出），
  **绝不读取/返回 `reasoning_content`（思考过程）**——思考内容不允许出现在
  任何玩家可见的窗口/文本；content 为 None 时一律返回 None，绝不降级用思考内容。
- 截断检测：`finish_reason == "length"` 时 `LLMResult.truncated=True`，
  上层据此通知房主调高 `max_tokens`（每局可覆盖，见 /llm-limit）。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("gm.llm")

# 单次输出上限的合法区间（房主调限端点校验用）
MAX_TOKENS_MIN = 1000
MAX_TOKENS_MAX = 32000


@dataclass
class LLMResult:
    """一次 LLM 调用的结构化结果。

    只携带**最终输出** `content` 与截断元信息；**不含** reasoning_content。
    """
    content: str | None
    truncated: bool = False
    finish_reason: str | None = None


class LLMClient:
    """OpenAI 兼容客户端（DeepSeek / Ollama / 硅基流动等）。"""

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, timeout: float = 90.0,
                 max_tokens: int | None = None):
        self.base_url = base_url or None
        self.api_key = api_key or ""
        self.model = model or "deepseek-chat"
        self.timeout = timeout
        self.max_tokens = max_tokens or 4000
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
    def from_config(cls, cfg: dict | None = None, secrets: dict | None = None,
                    max_tokens: int | None = None) -> "LLMClient":
        """从 data/config.json + data/secrets.json 构建。

        max_tokens 显式传入（每局覆盖）时优先；否则用 config 的 model.max_tokens。
        """
        from server import config
        cfg = cfg or config.load_config()
        secrets = secrets or config.load_secrets()
        m = cfg.get("model", {}) or {}
        return cls(
            base_url=m.get("base_url"),
            api_key=secrets.get("api_key"),
            model=m.get("model"),
            max_tokens=max_tokens if max_tokens is not None else m.get("max_tokens"),
        )

    # ---------- 对话 ----------

    async def chat(self, messages: list[dict], max_tokens: int | None = None,
                   json_mode: bool = False, temperature: float = 0.7,
                   retries: int = 2) -> str | None:
        """单轮对话，返回**最终输出**文本；失败/截断无内容返回 None。

        只返回 `content`；`reasoning_content`（思考过程）绝不返回。
        """
        res = await self.chat_detailed(messages, max_tokens=max_tokens,
                                       json_mode=json_mode, temperature=temperature,
                                       retries=retries)
        return res.content if res else None

    async def chat_detailed(self, messages: list[dict],
                            max_tokens: int | None = None,
                            json_mode: bool = False, temperature: float = 0.7,
                            retries: int = 2) -> LLMResult | None:
        """单轮对话（结构化）：返回 LLMResult（content / truncated / finish_reason）。

        - 失败重试 retries 次；最终失败返回 None（降级信号）
        - `truncated=True` 表示输出被 max_tokens 截断（finish_reason=length）
        - **隐私铁律**：只读 `message.content`；content 为 None 时返回
          LLMResult(content=None, truncated=...)，绝不把 reasoning_content 带出。
        """
        if not self.available or self._client is None:
            return None
        limit = max_tokens or self.max_tokens
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": limit,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = await self._client.chat.completions.create(**kwargs)
                choice = resp.choices[0]
                # 只取最终输出；推理模型的 reasoning_content 一律不读、不返回
                content: str | None = choice.message.content
                finish = getattr(choice, "finish_reason", None)
                truncated = finish == "length"
                return LLMResult(
                    content=content.strip() if content else None,
                    truncated=truncated,
                    finish_reason=finish,
                )
            except Exception as e:  # noqa: BLE001
                last_err = e
                logger.warning("LLM 调用失败(第 %d 次): %s", attempt + 1, e)
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
        return None

    # ---------- 便捷 ----------

    def is_available(self) -> bool:
        return self.available
