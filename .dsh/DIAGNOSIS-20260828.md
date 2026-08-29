# 诊断记录 · 飞书 agent 每条消息必失败（2026-08-28）

## 现象

`dsh --profile dsh-lark` 启动正常（ws client ready），但在飞书群里 @bot 发任何消息
（如「你好」）都回复「⚠️ Agent 运行失败。可重试」。jobs.json 中 **10/10 条记录全部
`state: failed`、`attempts: 1`、checkpoint 停在 `finalizing`**，收到消息后约 3 秒即失败。

## 根因 1（主因）：桥接 model 为空字符串，短路了路由回退链

- 真实报错在原生会话记录里（`~/.dsh/sessions/--C-Users-xingk-.dsh-lark-profiles-default-workspace--/session-*/session.jsonl.zstd`，多帧 zstd，用 `.dsh/bin/decompress-session.py` 解压）：

  ```
  turn/end → reason.kind=error
  "agent \"session-...\" has no provider/model: set AgentOptions.provider
   and AgentOptions.model or supply both via the agent/request waterfall"
  ```

- dsh-lark-bot `plugin.js:18738` 的模型解析链：

  ```js
  resolvedModel = models.get(scope) ?? role?.model ?? liveSettingsModel
    ?? activeProfile.preferences.model ?? dshDefault ?? defaultModel;
  ```

  `??` 只跳过 `null/undefined`，**不跳过空字符串**。而桥接
  `~/.dsh-lark/config.json` 里 `"preferences": { "model": "" }`，
  于是 `resolvedModel = ""`（falsy）→ 不解析路由 → run 时
  `model: modelRoute2?.model ?? resolvedModel` 传入空字符串、provider 缺失
  → SDK spawn 的 DSH agent 没有任何 provider/model → 必然失败。

- 全局 `~/.dsh/settings.yaml` 明明配了 `agent-default-model: minimax-cn/minimax-m3`，
  但永远轮不到这个兜底（被空字符串短路）。
- 佐证：`.dsh/bin/sdk-probe-full.mjs` 探针在 `initialize` 显式传
  `provider: "minimax-cn", model: "minimax-m3"` 后**成功**拿到 MiniMax 回复
  （会话 `full-probe-1787909401424`，responseId 06e0881d…），
  说明凭据（`.credentials.yaml`）与 SDK 链路都正常，唯独真实桥接传参为空。

### 修复

`~/.dsh-lark/config.json` → `profiles.default.preferences.model`：
`""` → `"minimax-cn/minimax-m3"`（备份：`.dsh/backup/config.json.bak-20260828`）。

> 注意：不要改 `~/.dsh/profiles/dsh-lark-sdk/cordis.patch.yml` 来兜底——
> 该文件由 dsh-lark-bot 托管（`ensureSdkProfile` 检测内容不匹配就整体重写，
> plugin.js:2865-2876），手改不持久。修桥接 config 才是正确层级。
> 之前加在 `~/.dsh/profiles/dsh-lark/cordis.patch.yml` 的 agent-default-model
> 覆盖只影响交互 profile，不影响 SDK 子进程路径。

## 根因 2：coc7th-keeper skill 对飞书 agent 不可见

- 飞书 agent 的 cwd 是 `~/.dsh-lark/profiles/default/workspace`（空目录），
  DSH 只扫描 `~/.dsh/skills/` 与 `<cwd>/.dsh/skills/`（DEPLOY.md 第 4 步）。
  两者都没有 coc7th-keeper → 失败会话的 skill 目录里只有 `dsh-lark-bot`，
  `/coc` 指令即使模型修好也无法处理。

### 修复

已按 DEPLOY.md 把整个 skill 复制到用户级目录：
`C:\Users\xingk\.dsh\skills\coc7th-keeper\`（24 个文件）。

## 启动注意（dsh.cmd 注释里的坑）

DSH Desktop 会向子进程注入 `DSH_HOME=C:\Users\xingk\AppData\Roaming\dsh-desktop\harness`，
该 home 没有 dsh-lark profile。从本会话内启动桥接必须显式
`$env:DSH_HOME = "$env:USERPROFILE\.dsh"`。用户在普通 PowerShell 里直接跑
`dsh --profile dsh-lark`（或项目里的 `.dsh/bin/dsh.cmd`，它已固定 DSH_HOME）不受影响。

## 当前状态

- 桥接已重启：PID 25064，`ws client ready`，心跳 channel=ready。
- ✅ **2026-08-28 用户已在飞书群实测确认：bot 正常回复，修复生效。**
- fleet.json 的 `botName` 乱码只是控制台 GBK 显示问题，文件本身是合法 UTF-8 JSON（已验证）。