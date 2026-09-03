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

import hashlib
import logging
import sys
from pathlib import Path

# 无论以 `python server/main.py` 还是 `uvicorn server.main:app` 启动，
# 都保证仓库根目录在 sys.path 上，使 `server.*` 导入一致可用。
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 应用日志（M8R5 可观测性）：INFO 级输出结算/推进/房间生命周期；脱敏约定不变。
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from server import config  # noqa: E402
from server.api import dev, games, modules  # noqa: E402
from server.ratelimit import RateLimiter  # noqa: E402
from server.sse import EventBus  # noqa: E402


def create_app() -> FastAPI:
    cfg = config.load_config()
    app = FastAPI(
        title="跑团 Web 平台",
        description="自托管 AI 跑团（TRPG）Web 平台 · CoC7th",
        version="0.1.0",
    )
    # 运行时实例：事件总线 / 配置 / 限流器（供各路由通过 request.app.state 访问）
    app.state.config = cfg
    app.state.bus = EventBus()
    rl = cfg.get("rate_limit") or {}
    app.state.ratelimiter = RateLimiter(
        per_minute=rl.get("per_minute", 300), burst=rl.get("burst", 20))

    @app.middleware("http")
    async def _rate_limit(request: Request, call_next):
        """M6.5 访问限流：每 IP 滑动窗口，仅作用于 /api；超限回 429。"""
        rl_cfg = cfg.get("rate_limit") or {}
        if rl_cfg.get("enabled", True) and request.url.path.startswith("/api"):
            ip = request.client.host if request.client else "unknown"
            if not app.state.ratelimiter.allow(ip):
                return JSONResponse({"detail": "请求过于频繁，请稍后再试"},
                                    status_code=429)
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.get("cors_origins") or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # M8R5 进站门禁：access_password 设置后，所有 /api 请求需携带访问凭证
    # （cookie 由 POST /api/access 校验密码后下发；/api/health 与 /api/access 豁免）。
    # 页面与静态资源放行 —— 前端启动时经 /api/access/check 检测并显示密码门。
    # 与房间级密码（M5，加入房间校验）语义区分：本门禁管「能否访问本站 API」。
    # 注意必须每请求动态 load_config：app 单例在 import 时固化，静态 cfg 会让
    # 测试夹具（DATA_DIR 隔离）与「改密码即生效」双双失效。
    def _access_cookie_value(password: str) -> str:
        return hashlib.sha256(("kp-access:" + password).encode("utf-8")).hexdigest()[:24]

    @app.middleware("http")
    async def _access_gate(request: Request, call_next):
        from server import config as _cfg
        pwd = _cfg.load_config().get("access_password")
        if pwd and request.method != "OPTIONS":
            path = request.url.path
            # 只拦 /api：页面与静态资源必须放行，否则前端密码门本身加载不出来
            # （前端启动时经 /api/access/check 探测并显示密码门）
            if path.startswith("/api") and not (
                    path == "/api/health" or path.startswith("/api/access")):
                if request.cookies.get("access_ok") != _access_cookie_value(pwd):
                    return JSONResponse(
                        {"detail": "需要访问密码", "code": "access_denied"},
                        status_code=401)
        return await call_next(request)

    @app.post("/api/access")
    async def access_login(request: Request) -> JSONResponse:
        """校验访问密码并下发门禁 cookie（access_password 未设置时无需认证）。"""
        from server import config as _cfg
        cfg_now = _cfg.load_config()
        try:
            body = await request.json()
        except Exception:
            body = {}
        password = str((body or {}).get("password") or "")
        pwd = cfg_now.get("access_password")
        if not pwd:
            resp = JSONResponse({"authenticated": True, "required": False})
            resp.set_cookie("access_ok", _access_cookie_value("open"))
            return resp
        if password != pwd:
            return JSONResponse({"authenticated": False, "detail": "访问密码错误"},
                                status_code=401)
        resp = JSONResponse({"authenticated": True, "required": True})
        resp.set_cookie("access_ok", _access_cookie_value(pwd),
                        max_age=30 * 24 * 3600, samesite="lax")
        return resp

    @app.get("/api/access/check")
    async def access_check(request: Request) -> dict:
        """前端启动时探测：站点是否启用了门禁、当前会话是否已认证。"""
        from server import config as _cfg
        pwd = _cfg.load_config().get("access_password")
        if not pwd:
            return {"required": False, "authenticated": True}
        ok = request.cookies.get("access_ok") == _access_cookie_value(pwd)
        return {"required": True, "authenticated": ok}

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

    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc):
        """SPA 深链兜底（M6.3 修复）：非 /api 路径 404 时回 index.html，
        使 /play/xxx 等前端路由在生产静态托管下可直接访问。"""
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        index = dist / "index.html" if dist.is_dir() else None
        if index is not None and index.exists():
            from fastapi.responses import FileResponse
            return FileResponse(str(index))
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    return app


app = create_app()


if __name__ == "__main__":
    cfg = config.load_config()
    host = cfg["server"]["host"]
    port = int(cfg["server"]["port"])
    print(f"跑团 Web 平台 · http://{host}:{port}  (/api/health)")
    # log_level=warning：关闭 uvicorn 访问日志（M6.5 日志脱敏，不落 IP 明细）
    uvicorn.run(app, host=host, port=port, log_level="warning")
