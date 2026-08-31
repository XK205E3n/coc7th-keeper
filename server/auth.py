# -*- coding: utf-8 -*-
"""认证与凭证（M5.1）：密码哈希、邀请凭证、玩家/host token。

- 密码：盐化 sha256，存 `salt$hex`（M6 安全清单再评估更强者）
- 邀请凭证：轮换制（POST /invite 生成新码，旧码立即失效）
- token：secrets.token_urlsafe（玩家/host 各自独立）
"""
from __future__ import annotations

import hashlib
import secrets


def hash_password(pw: str) -> str:
    """盐化 SHA-256：返回 `salt$hex`。"""
    salt = secrets.token_hex(8)
    digest = hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(pw: str, stored: str) -> bool:
    """校验密码；stored 格式 `salt$hex`，格式非法返回 False。"""
    if not stored or "$" not in stored:
        return False
    salt, expected = stored.split("$", 1)
    digest = hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()
    return secrets.compare_digest(digest, expected)


def new_token() -> str:
    """玩家 / 房主 token。"""
    return secrets.token_urlsafe(24)


def new_invite_token() -> str:
    """邀请凭证（一次性、可轮换）。"""
    return secrets.token_urlsafe(12)
