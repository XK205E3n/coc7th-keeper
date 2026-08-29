# 飞书接入说明 · 已选定 dsh-lark-bot

> 本目录保留仅为兼容历史版本。**所有飞书接入已由社区插件 [dsh-lark-bot](https://github.com/PlutoKeating/dsh-lark-bot) 完成**，无需自写。

## 为什么用现成插件，不自己写？

调研了 DSH 社区 7 个飞书集成项目，最终选择 **PlutoKeating/dsh-lark-bot**（36★）：

| 能力 | dsh-lark-bot |
|---|---|
| 扫码自动建飞书应用 | ✅ 一键扫码 |
| WebSocket 长连接（无需公网 IP / 域名） | ✅ |
| 流式卡片 / Markdown 结构化卡片 | ✅ |
| 斜杠命令三级分流（自定义命令注入 Agent） | ✅ |
| 群聊隔离（每群一个 Agent 会话） | ✅ |
| 崩溃自愈 + 后台常驻 | ✅ 安全网守护 |
| 飞书内自更新 | ✅ `/upgrade` 命令 |
| 工作区 / 会话管理 | ✅ |
| 出站通知转其他 IM | ✅ 飞书内 `/channels` |

`/coc` 自定义指令会作为 Tier 3 消息注入 Agent；Agent 加载 `coc7th-keeper` skill 后自动处理。

## 频道上下文（chat_type）与隐私分支

> 备注（v0.2.0）：dsh-lark-bot 向 Agent 会话注入可信的
> `[Channel context — trusted bridge metadata]` 头，其中 `chat_type`（`p2p` | `group` | `topic`）
> 标明本条回复将发往的频道。`coc7th-keeper` skill 据此执行隐私分支（`SKILL.md` §2 隐私铁律）：
>
> - `group` / `topic`（跑团群聊）→ **零 KP 数据**：只发玩家可见内容；
> - `p2p`（私聊）→ 仅在确认对方是守密人本人且明确要求时，才展示 KP 数据概要，且绝不回流任何群聊；
> - 拿不到可信频道头 → 一律按群聊保守处理。

## 安装

一行命令：

```powershell
npx dsh-lark-bot@latest setup --profile dsh-lark
dsh --profile dsh-lark
```

终端打印二维码 → 飞书 App 扫码 → 完成。

## 已废弃的"自写飞书网关"路线

原本计划自写 `bridge/feishu_bot.py`，用 `larksuite-oapi`（飞书官方 Python SDK）走 WebSocket 长连接。但社区已提供完整方案，无重复造轮子的必要。

如果出于学术/学习目的想自写，可参考：

- 飞书 Python SDK：`larksuite-oapi`（PyPI）
- WebSocket 长连接：`lark_oapi.adapter.websocket`
- 消息事件订阅：`im.message.receive_v1`
- 交互卡片：`interactive` 类型（按钮回调 / 表单输入）

但社区方案更稳、更全、更易调试。

## 相关链接

- 完整部署：`DEPLOY.md`
- 玩家说明书：`USER_GUIDE.md`
- 5 分钟上手：`assets/quickstart.md`