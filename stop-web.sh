#!/usr/bin/env bash
# 跑团 Web 平台 · 一键关闭（Linux，M8R6 自 stop-web.ps1 移植，语义对齐）
# 行为：按 data/.run/*.pid 树杀（kill -- -PID），并对缺失/失效的 pid 做命令行兜底过滤；
#       只杀本项目后端（server/main.py）、穿透二进制（cloudflared/frpc/cpolar）、Vite，
#       绝不无差别杀所有 python / node。重复执行幂等（无进程时打印「无运行中进程」）。
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/data/.run"
KILLED=0

kill_tree() {  # $1=pid；先确认存活再杀，保证幂等且不对已死进程报错
    local p="${1:-0}"
    case "$p" in ''|*[!0-9]*) return ;; esac
    [ "$p" -le 0 ] && return
    kill -0 "$p" 2>/dev/null || return
    # 进程组杀优先（start-web.sh 用 setsid 起的进程自带独立进程组），
    # 组不存在（如兜底抓到的非组长进程）退化为单杀。
    kill -- -"$p" 2>/dev/null || kill "$p" 2>/dev/null || true
    KILLED=$((KILLED + 1))
}

# 1) 按 pid 文件树杀
if [ -d "$RUN_DIR" ]; then
    for f in "$RUN_DIR"/*.pid; do
        [ -e "$f" ] || continue
        p="$(cat "$f" 2>/dev/null || true)"
        kill_tree "$p"
        rm -f "$f"
    done
fi

# 2) 兜底：命令行过滤（只杀本项目相关进程）
#    vite 额外要求命令行含本项目根目录，避免误杀别的项目里的 vite 进程。
for p in $(pgrep -f 'server/main\.py' 2>/dev/null; pgrep -x cloudflared 2>/dev/null; \
           pgrep -x frpc 2>/dev/null; pgrep -x cpolar 2>/dev/null); do
    kill_tree "$p"
done
for p in $(pgrep -f 'vite' 2>/dev/null); do
    if tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | grep -qF "$ROOT"; then
        kill_tree "$p"
    fi
done

# 3) 清理残留 pid 文件（日志保留）
if [ -d "$RUN_DIR" ]; then
    find "$RUN_DIR" -maxdepth 1 -name '*.pid' -delete 2>/dev/null || true
fi

if [ "$KILLED" -eq 0 ]; then
    echo "[停止] 无运行中进程。"
else
    echo "[停止] 已关闭 $KILLED 个进程（后端 / 穿透 / Vite），pid 文件已清空，日志保留在 data/.run/。"
fi
