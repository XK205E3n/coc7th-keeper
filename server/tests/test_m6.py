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
    from server.ratelimit import RateLimiter
    original = app.state.ratelimiter
    app.state.ratelimiter = RateLimiter(per_minute=3, burst=100)
    try:
        for _ in range(3):
            assert client.get("/api/health").status_code == 200
        assert client.get("/api/health").status_code == 429
        assert client.get("/api/health").json()["detail"]
    finally:
        app.state.ratelimiter = original


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


def test_spa_deep_link_fallback(client):
    """M6.3 修复：生产静态托管下 /play/xxx 深链回 index.html，/api 404 保持 JSON。"""
    from pathlib import Path
    dist_index = Path(__file__).resolve().parents[2] / "frontend" / "dist" / "index.html"
    if not dist_index.exists():
        pytest.skip("前端 dist 未构建，跳过")

    r = client.get("/play/demo")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<div id=\"app\">" in r.text or "app" in r.text
    # /api 404 仍返回 JSON
    r = client.get("/api/not-exists")
    assert r.status_code == 404 and "detail" in r.json()
