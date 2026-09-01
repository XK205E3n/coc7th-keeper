# -*- coding: utf-8 -*-
"""运行时配置读写（M1.1）。

- `data/config.json`：服务端口 / 模型接口 / CORS / 访问密码 / 分享地址
- `data/secrets.json`：API Key（本地文件，不入库）

数据目录可用环境变量 `DATA_DIR` 覆盖（测试用临时目录）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# 仓库根目录 = server/ 的上一级
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """返回运行时数据根目录（环境变量 DATA_DIR 优先，否则 <仓库根>/data）。"""
    env = os.environ.get("DATA_DIR")
    return Path(env).resolve() if env else (PROJECT_ROOT / "data").resolve()


def games_dir() -> Path:
    """每游戏一个 SQLite 数据库目录：data/games/。"""
    return data_dir() / "games"


def ensure_data_dirs() -> None:
    """确保 data/ 与 data/games/ 存在。"""
    data_dir().mkdir(parents=True, exist_ok=True)
    games_dir().mkdir(parents=True, exist_ok=True)


# ---------------- config.json ----------------

DEFAULT_CONFIG: dict[str, Any] = {
    "server": {"host": "127.0.0.1", "port": 18000},
    "model": {
        "provider": "deepseek",          # deepseek | openai | ollama | siliconflow
        "base_url": None,                # OpenAI 兼容端点；None 用 provider 默认
        "model": None,                   # 主模型
        "backup_model": None,            # 备用模型（M2 起用）
        "max_tokens": 4000,              # 单次 LLM 输出上限（默认；每局可覆盖，见 /llm-limit）
    },
    "cors_origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
    "access_password": None,             # 可选：加入游戏需密码（已由 M5 每局密码落实，此处保留全局开关占位）
    "share_url": None,                   # 对外分享地址：隧道/反代后公网地址（前端也可用 VITE_SHARE_URL）
    "dev_token": None,                   # M5.5 开发者监视接口（X-Dev-Token）；配置后启用
    "rate_limit": {                      # M6.5 访问限流（每 IP 滑动窗口；仅作用于 /api）
        "enabled": True,
        "per_minute": 300,               # 每分钟上限
        "burst": 20,                     # 单秒突发上限
    },
}


def default_config() -> dict[str, Any]:
    import copy
    return copy.deepcopy(DEFAULT_CONFIG)


def _merge(defaults: dict, user: dict) -> dict:
    """深合并：用户配置覆盖默认值（嵌套 dict 按层合并）。"""
    out = dict(defaults)
    for k, v in (user or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict[str, Any]:
    """读取 data/config.json；缺省/损坏时回退默认值并返回。"""
    ensure_data_dirs()
    p = data_dir() / "config.json"
    user: dict = {}
    if p.exists():
        try:
            user = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            user = {}
    cfg = _merge(DEFAULT_CONFIG, user)
    _normalise(cfg)
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    """把配置写回 data/config.json。"""
    ensure_data_dirs()
    _normalise(cfg)
    p = data_dir() / "config.json"
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalise(cfg: dict[str, Any]) -> None:
    """把配置里的端口/布尔等类型修正为合法值。"""
    try:
        cfg["server"]["port"] = int(cfg["server"]["port"])
    except (KeyError, TypeError, ValueError):
        cfg.setdefault("server", {})["port"] = 18000
    if cfg["server"].get("host") is None:
        cfg["server"]["host"] = "127.0.0.1"


# ---------------- secrets.json ----------------

def load_secrets() -> dict[str, str]:
    """读取 data/secrets.json；不存在时返回空 API Key。"""
    ensure_data_dirs()
    p = data_dir() / "secrets.json"
    if not p.exists():
        return {"api_key": ""}
    try:
        s = json.loads(p.read_text(encoding="utf-8"))
        return {"api_key": str(s.get("api_key", "") or "")}
    except (json.JSONDecodeError, OSError):
        return {"api_key": ""}


def save_secrets(secrets: dict[str, str]) -> None:
    """写回 data/secrets.json（仅保存 api_key，避免夹带其它字段）。"""
    ensure_data_dirs()
    p = data_dir() / "secrets.json"
    p.write_text(
        json.dumps({"api_key": str(secrets.get("api_key", "") or "")},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
