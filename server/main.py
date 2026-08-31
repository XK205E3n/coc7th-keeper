# -*- coding: utf-8 -*-
"""FastAPI 入口（M0 / M1.1）。

启动：
    python server/main.py            # 缺省端口 18000（见 data/config.json server.port）
    uvicorn server.main:app --port 18000

路由：
    GET  /api/health                 健康检查 → {"status":"ok"}
    /api/games/*                      见 server/api/games.py（M1.5）
    /api/modules                      见 server/api/modules.py（M1.4）
前端静态文件：若存在 frontend/dist，则挂载到 /（M6 部署用）。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 无论以 `python server/main.py` 还是 `uvicorn server.main:app` 启动，
# 都保证仓库根目录在 sys.path 上，使 `server.*` 导入一致可用。
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from server import config  # noqa: E402
from server.api import dev, games, modules  # noqa: E402
from server.sse import EventBus  # noqa: E402


def create_app() -> FastAPI:
    cfg = config.load_config()
    app = FastAPI(
        title="跑团 Web 平台",
        description="自托管 AI 跑团（TRPG）Web 平台 · CoC7th",
        version="0.1.0",
    )
    # 运行时实例：事件总线 / 配置（供各路由通过 request.app.state 访问）
    app.state.config = cfg
    app.state.bus = EventBus()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.get("cors_origins") or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(games.router, prefix="/api")
    app.include_router(modules.router, prefix="/api")
    app.include_router(dev.router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    # 部署时若存在前端构建产物则挂载（开发期由 Vite dev server 承担）
    dist = _ROOT / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")

    return app


app = create_app()


if __name__ == "__main__":
    cfg = config.load_config()
    host = cfg["server"]["host"]
    port = int(cfg["server"]["port"])
    print(f"跑团 Web 平台 · http://{host}:{port}  (/api/health)")
    uvicorn.run(app, host=host, port=port)
