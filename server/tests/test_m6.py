# -*- coding: utf-8 -*-
"""M6 部署加固测试：访问限流（429）与安全配置。"""
from __future__ import annotations

import json

import pytest

from server.ratelimit import RateLimiter


# ---------------- M6.5 限流：单元 ----------------

def test_ratelimiter_per_minute():
    rl = RateLimiter(per_minute=5, burst=100)
    assert all(rl.allow("1.2.3.4") for _ in range(5))
    assert not rl.allow("1.2.3.4")          # 超 5/分钟
    assert rl.allow("5.6.7.8")              # 其他 IP 不受影响
    rl.reset("1.2.3.4")
    assert rl.allow("1.2.3.4")              # 重置后放行


def test_ratelimiter_burst():
    rl = RateLimiter(per_minute=1000, burst=2)
    assert rl.allow("9.9.9.9")
    assert rl.allow("9.9.9.9")
    assert not rl.allow("9.9.9.9")          # 单秒突发上限 2


# ---------------- M6.5 限流：中间件 ----------------

def test_rate_limit_middleware_429(client):
    from server.main import app
    app.state.ratelimiter = RateLimiter(per_minute=3, burst=100)
    for _ in range(3):
        assert client.get("/api/health").status_code == 200
    assert client.get("/api/health").status_code == 429
    assert client.get("/api/health").json()["detail"]


def test_rate_limit_reset_between_tests(client):
    """每测试重置限流器：上一用例把 per_minute=3 打满后，本用例不受影响。"""
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health").status_code == 200


# ---------------- M6.5 安全配置：默认值完整 ----------------

def test_config_security_defaults():
    from server import config
    cfg = config.default_config()
    assert "dev_token" in cfg and cfg["dev_token"] is None      # 默认关闭监视
    rl = cfg.get("rate_limit") or {}
    assert rl.get("enabled", True) is True
    assert rl.get("per_minute", 0) >= 1
    assert rl.get("burst", 0) >= 1


def test_secrets_roundtrip(tmp_path, monkeypatch):
    """secrets.json 只存 api_key；损坏/缺失回退空。"""
    from server import config
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    config.save_secrets({"api_key": "sk-test"})
    assert config.load_secrets()["api_key"] == "sk-test"
    # 只保留 api_key，夹带字段被丢弃
    p = config.data_dir() / "secrets.json"
    p.write_text(json.dumps({"api_key": "a", "evil": "x"}), encoding="utf-8")
    assert config.load_secrets() == {"api_key": "a"}
    # 损坏回退
    p.write_text("{bad json", encoding="utf-8")
    assert config.load_secrets() == {"api_key": ""}
