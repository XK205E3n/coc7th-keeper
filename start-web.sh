#!/usr/bin/env bash
# 跑团 Web 平台 · 一键启动（Linux，M8R6 自 start-web.ps1 移植，语义对齐）
# 用法：
#   ./start-web.sh                    # 前台阻塞启动（无穿透），Ctrl+C 退出
#   ./start-web.sh --dev              # 开发模式：后端后台 + Vite dev server(5173) 前台
#   ./start-web.sh --daemon           # 后台起后端（无穿透），打印 PID 后退出
#   ./start-web.sh --tunnel           # 后台：后端 + 内网穿透，抓公网 URL → 写 share_url → 退出
#   ./start-web.sh --tunnel --provider mock   # mock provider 演练（不启真进程）
#   ./start-web.sh --tunnel --force           # 跳过 access_password 安全确认
# 说明：后台进程经 setsid 独立成进程组，stop-web.sh 按 pid 树杀（kill -- -PID）。
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

RUN_DIR="$ROOT/data/.run"
BACKEND_PID="$RUN_DIR/backend.pid"
TUNNEL_PID="$RUN_DIR/tunnel.pid"
BACKEND_LOG="$RUN_DIR/backend.log"
TUNNEL_LOG="$RUN_DIR/tunnel.log"
# stderr 单独成文件（对齐 ps1）：穿透程序的公网地址常打在 stderr（如 cloudflared），
# Get-TunnelUrl 两个文件都要读。
TUNNEL_LOG_ERR="$TUNNEL_LOG.err"

DEV=0; DAEMON=0; TUNNEL=0; FORCE=0; PROVIDER=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dev) DEV=1 ;;
        --daemon) DAEMON=1 ;;
        --tunnel) TUNNEL=1 ;;
        --force) FORCE=1 ;;
        --provider) PROVIDER="${2:-}"; shift ;;
        *) echo "[错误] 未知参数：$1"; exit 1 ;;
    esac
    shift
done

ensure_venv() {
    PY="$ROOT/.venv/bin/python"
    if [ ! -x "$PY" ]; then
        echo "[错误] 未找到虚拟环境，请先执行："
        echo "  python3 -m venv .venv"
        echo "  .venv/bin/python -m pip install -r requirements.txt"
        exit 1
    fi
}

ensure_dist() {
    if [ ! -f "$ROOT/frontend/dist/index.html" ]; then
        echo "[首次启动] 构建前端静态产物..."
        ( cd "$ROOT/frontend" && npm install && npm run build ) || {
            echo "[错误] 前端构建失败"; exit 1; }
    fi
}

# 配置只经 tools/config_cli.py 读取（与 ps1 同源，避免各写一套解析）。
cfg_get() {  # $1=点路径 如 server.port / tunnel.provider
    "$PY" tools/config_cli.py get | "$PY" -c '
import json, sys
node = json.load(sys.stdin)
for part in sys.argv[1].split("."):
    node = node.get(part) if isinstance(node, dict) else None
    if node is None:
        break
print("" if node is None else node)
' "$1"
}

start_bg() {  # $1=可执行 $2=参数串 $3=pid文件 $4=stdout日志
    mkdir -p "$RUN_DIR"
    # setsid：子进程独立进程组，停止时 kill -- -PID 可整树杀。
    # 参数串按空白分词（本脚本所有参数均不含空格；frp 配置路径含空格时需自行加引号改造）。
    setsid nohup "$1" $2 >"$4" 2>"$4.err" </dev/null &
    echo $! > "$3"
}

stop_local() {
    for f in "$BACKEND_PID" "$TUNNEL_PID"; do
        if [ -f "$f" ]; then
            p="$(cat "$f" 2>/dev/null || true)"
            if [ -n "$p" ] && [ "$p" -gt 0 ] 2>/dev/null && kill -0 "$p" 2>/dev/null; then
                kill -- -"$p" 2>/dev/null || kill "$p" 2>/dev/null || true
            fi
            rm -f "$f"
        fi
    done
}

wait_backend_ready() {  # $1=端口；端口取自 config（用户可改），不硬编码
    for _ in $(seq 1 30); do
        if "$PY" -c '
import sys, json, urllib.request
try:
    d = json.load(urllib.request.urlopen(
        "http://127.0.0.1:%s/api/health" % sys.argv[1], timeout=2))
    sys.exit(0 if d.get("status") == "ok" else 1)
except Exception:
    sys.exit(1)
' "$1" 2>/dev/null; then return 0; fi
        sleep 1
    done
    return 1
}

start_tunnel() {  # $1=provider $2=port → 输出 "ok|失败原因"（经全局变量 TR_URL/TR_PID 带回）
    TR_URL=""; TR_PID=""
    local provider="$1" port="$2"
    local bin
    case "$provider" in
        cloudflared)
            bin="$(cfg_get tunnel.cloudflared.bin)"
            if ! command -v "$bin" >/dev/null 2>&1; then
                echo "[错误] 未找到穿透二进制 '$bin'。"
                echo "  安装：https://developers.cloudflare.com/cloudflared/"
                return 1
            fi
            local args="tunnel --url http://127.0.0.1:$port"
            local tname; tname="$(cfg_get tunnel.cloudflared.tunnel_name)"
            [ -n "$tname" ] && args="$args --name $tname"
            start_bg "$bin" "$args" "$TUNNEL_PID" "$TUNNEL_LOG"
            TR_PID="$(cat "$TUNNEL_PID")"
            ;;
        frp)
            bin="$(cfg_get tunnel.frp.bin)"
            if ! command -v "$bin" >/dev/null 2>&1; then
                echo "[错误] 未找到穿透二进制 '$bin'。"
                echo "  安装：https://gofrp.org"
                return 1
            fi
            local cfgpath; cfgpath="$(cfg_get tunnel.frp.config)"
            if [ ! -f "$cfgpath" ]; then
                echo "[错误] 缺少 frp 配置 '$cfgpath'（参考 tools/frpc.toml 模板填写）。"
                return 1
            fi
            start_bg "$bin" "-c $cfgpath" "$TUNNEL_PID" "$TUNNEL_LOG"
            TR_PID="$(cat "$TUNNEL_PID")"
            ;;
        cpolar)
            bin="$(cfg_get tunnel.cpolar.bin)"
            if ! command -v "$bin" >/dev/null 2>&1; then
                echo "[错误] 未找到穿透二进制 '$bin'。"
                echo "  安装：https://www.cpolar.com"
                return 1
            fi
            start_bg "$bin" "http $port" "$TUNNEL_PID" "$TUNNEL_LOG"
            TR_PID="$(cat "$TUNNEL_PID")"
            ;;
        mock)
            TR_URL="$(cfg_get tunnel.mock.url)"
            echo "[穿透] mock provider（自测模式，不启真进程）→ $TR_URL"
            ;;
        *)
            echo "[错误] 未知 tunnel.provider: '$provider'（可选 cloudflared/frp/cpolar/mock）。"
            return 1
            ;;
    esac
    return 0
}

get_tunnel_url() {  # $1=provider → 公网地址（60s 轮询日志；cpolar 先查本地 API）
    local provider="$1"
    if [ -n "$TR_URL" ]; then echo "$TR_URL"; return 0; fi
    if [ "$provider" = "cpolar" ]; then
        local u
        u="$("$PY" -c '
import sys, json, urllib.request
try:
    d = json.load(urllib.request.urlopen(
        "http://127.0.0.1:4040/api/tunnels", timeout=2))
    ts = d.get("tunnels") or []
    print(ts[0]["public_url"] if ts else "")
except Exception:
    print("")
' 2>/dev/null)"
        [ -n "$u" ] && { echo "$u"; return 0; }
    fi
    # 轮询两个日志流，剥 ANSI 颜色码后提取 URL（地址常打在 stderr）
    local regex='https?://[^"<>'"'"' ]+'
    [ "$provider" = "cloudflared" ] && \
        regex='https://[A-Za-z0-9-]+\.trycloudflare\.com'
    for _ in $(seq 1 60); do
        local txt=""
        [ -f "$TUNNEL_LOG" ] && txt+="$(cat "$TUNNEL_LOG" 2>/dev/null)"$'\n'
        [ -f "$TUNNEL_LOG_ERR" ] && txt+="$(cat "$TUNNEL_LOG_ERR" 2>/dev/null)"$'\n'
        if [ -n "$(printf '%s' "$txt" | tr -d '[:space:]')" ]; then
            local hit
            hit="$(printf '%s' "$txt" | sed $'s/\x1b\\[[0-9;]*m//g' \
                  | grep -Eo "$regex" | head -n 1)"
            [ -n "$hit" ] && { echo "$hit"; return 0; }
        fi
        sleep 1
    done
    return 1
}

run_daemon() {
    local port; port="$(cfg_get server.port)"
    echo "[后端] 后台启动中..."
    start_bg "$PY" "server/main.py" "$BACKEND_PID" "$BACKEND_LOG"
    if ! wait_backend_ready "$port"; then
        echo "[错误] 后端 30s 内未就绪，已清理。"
        stop_local; exit 1
    fi
    echo "[后端] 已后台启动 PID $(cat "$BACKEND_PID")  http://localhost:$port"
    echo "日志：data/.run/backend.log    关闭：./stop-web.sh"
}

run_tunnel() {
    local access_pwd; access_pwd="$(cfg_get access_password)"
    if [ -z "$access_pwd" ] && [ "$FORCE" -ne 1 ]; then
        echo "[警告] access_password 未设置 —— 穿透后公网任何人可进入你的房间。"
        echo "        建议先在 data/config.json 设置 access_password，或加 --force 跳过。"
        local ans
        read -r -p "确认继续穿透？(y/N) " ans || ans="n"
        case "$ans" in [yY]|[yY][eE][sS]) ;; *) echo "[已取消] 未穿透。"; exit 1 ;; esac
    fi
    mkdir -p "$RUN_DIR"

    local port provider
    port="$(cfg_get tunnel.target_port)"; [ -n "$port" ] || port="$(cfg_get server.port)"
    provider="${PROVIDER:-$(cfg_get tunnel.provider)}"

    echo "[后端] 启动中..."
    start_bg "$PY" "server/main.py" "$BACKEND_PID" "$BACKEND_LOG"
    if ! wait_backend_ready "$port"; then
        echo "[错误] 后端 30s 内未就绪，已清理。"
        stop_local; exit 1
    fi
    echo "[后端] 就绪 PID $(cat "$BACKEND_PID")"

    if ! start_tunnel "$provider" "$port"; then
        echo "[错误] 穿透启动失败，已清理后端。"
        stop_local; exit 1
    fi
    [ -n "$TR_PID" ] && echo "[穿透] 进程 PID $TR_PID，等待公网地址..."

    local url
    if ! url="$(get_tunnel_url "$provider")"; then
        echo "[错误] 60s 内未抓到公网地址，已关闭穿透。"
        stop_local; exit 1
    fi
    "$PY" tools/config_cli.py set-share-url "$url" >/dev/null
    echo ""
    echo "========== 穿透已建立 =========="
    echo "本地地址 ：http://localhost:$port"
    echo "公网地址 ：$url"
    if [ -n "$TR_PID" ]; then
        echo "后端 PID ：$(cat "$BACKEND_PID")  穿透 PID：$TR_PID"
    else
        echo "后端 PID ：$(cat "$BACKEND_PID")  (mock 无进程)"
    fi
    echo "分享地址已写入 data/config.json 的 share_url"
    echo "关闭命令 ：./stop-web.sh"
    echo "================================"
}

# ---------------- 主流程 ----------------
ensure_venv

if [ "$DEV" -eq 1 ] && [ "$TUNNEL" -eq 1 ]; then
    echo "[错误] --dev 与 --tunnel 不能同时传。"
    echo "        开发模式前端跑在 Vite(5173)，穿透只能暴露 API、拿不到前端资源且跨域。请先 npm run build 再用 --tunnel。"
    exit 1
fi

if [ "$DEV" -eq 1 ]; then
    # 开发模式：后端后台 + Vite 前台，退出时回收后端（对齐 ps1 行为）
    mkdir -p "$RUN_DIR"
    setsid nohup "$PY" server/main.py >/dev/null 2>&1 </dev/null &
    DEV_BE_PID=$!
    echo "[后端] PID $DEV_BE_PID  http://localhost:18000"
    trap 'kill -- -"$DEV_BE_PID" 2>/dev/null || kill "$DEV_BE_PID" 2>/dev/null || true' EXIT
    ( cd "$ROOT/frontend" && npm run dev )
else
    ensure_dist
    if [ "$TUNNEL" -eq 1 ]; then
        run_tunnel
    elif [ "$DAEMON" -eq 1 ]; then
        run_daemon
    else
        echo "[启动] http://localhost:$(cfg_get server.port)  （Ctrl+C 退出）"
        exec "$PY" server/main.py
    fi
fi
