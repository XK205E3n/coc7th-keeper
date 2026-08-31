# -*- coding: utf-8 -*-
"""pytest 公共夹具（M1.8）。

- 每个测试获得独立 DATA_DIR（临时目录），并清空 store 注册表，互不污染
- COC_MODULES_DIR 固定指向仓库 modules/
- client：FastAPI TestClient
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """每个测试独立数据目录 + 清空存档缓存 + 重置限流器（防整套测试互触 429）。"""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("COC_MODULES_DIR", str(ROOT / "modules"))
    from server import store
    store._stores.clear()
    try:
        from server.main import app
        app.state.ratelimiter.reset()
    except Exception:  # noqa: BLE001 - app 未导入时忽略
        pass
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from server.main import app
    with TestClient(app) as c:
        yield c
