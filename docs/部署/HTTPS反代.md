# HTTPS 反代（M6.2）· Caddy / Nginx

> 后端默认跑纯 HTTP `127.0.0.1:18000`，HTTPS 交给反代终结（证书 + 加密 + 转发）。
> 关键点：**必须透传 SSE**（`/api/games/*/events` 是长连接流），否则游玩页实时更新会断。

## 方案一：Caddy（推荐，自动 HTTPS 证书）

Caddy 自动申请/续期 Let's Encrypt 证书，配置即文档：

```caddyfile
# /etc/caddy/Caddyfile
your-domain.com {
    reverse_proxy 127.0.0.1:18000
}
```

- 保存后 `systemctl reload caddy` 即生效（首次会自动拉证书，确保 80/443 已对公网开放、域名 A 记录已指向本机）。
- Caddy 默认**缓存关闭、SSE/流式透传正常**，无需额外配置。
- 需要限制访问：应用层设了访问密码即可；要在 Caddy 层再加一道，可用 `basicauth`（可选，不推荐与业务密码叠加）。

## 方案二：Nginx + certbot（手动证书）

```nginx
# /etc/nginx/conf.d/coc.conf
server {
    listen 80;
    server_name your-domain.com;
    # 跳转 HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:18000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 透传（关键）：关闭缓冲，长连接不断
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;

        # WebSocket（预留，当前未用但无害）
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

证书获取（首次）：
```bash
apt install -y nginx certbot python3-certbot-nginx
certbot --nginx -d your-domain.com      # 自动改 nginx 配置并续期
```

## 验证清单

- [ ] `https://your-domain.com/api/health` 返回 `{"status":"ok"}`（HTTPS 生效）
- [ ] 建房 → 行动 → 自动推进：游玩页叙事流**实时刷新**（SSE 透传 OK）
- [ ] 刷新页面叙事流完整恢复（重连/校准 OK）
- [ ] 异地（手机流量）输入访问密码可加入并跑一轮
- [ ] 邀请链接指向 `https://your-domain.com/?key=...&invite=...`

## 常见坑

1. **Nginx 504/断流**：多数是 `proxy_buffering off` 没加，或 `proxy_read_timeout` 默认 60s 超时踢掉 SSE。
2. **页面 200 但 /api 404**：`location /` 覆盖了全部路径，`proxy_pass` 不要带尾斜杠多余路径。
3. **证书续期失败**：确认 80 端口只给 certbot/nginx 用；`certbot renew --dry-run` 自查。
4. 后端 `log_level=warning` 已关闭访问日志（日志脱敏，M6.5）；反代层日志按需自管。
