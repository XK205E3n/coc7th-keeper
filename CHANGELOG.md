# 变更日志（Changelog）

本项目遵循 [SemVer](https://semver.org/lang/zh-CN/)：`MAJOR.MINOR.PATCH`。版本号与根目录 `VERSION` 文件保持一致。

---

## [v0.2.3] - 2026-08-29（未发布）

修复：桥接 git worktree 导致 bot 读不到跑团存档。

- **根因**：dsh-lark-bot 为每个群会话创建隔离 git worktree（设计特性）；把工作区转为 git 仓库后，gitignored 的运行数据 `coc-session/` 不再出现在 worktree 中，bot 报「找不到房间存档」；且 worktree 是创建时的静态检出，仓库更新不自动跟进。
- **修复**：新增 `tools/fix-bridge-worktrees.ps1` —— 为每个本仓库 worktree 创建 `coc-session` 目录 junction（双向透明，bot 写、主仓库读同一份数据）并 `git fetch + merge origin/master` 同步最新代码（顺带解决旧版本 worktree 缺 toy-dancer-comes 的问题）。
- SKILL.md §3.2 新增「worktree 环境自救」：找不到房间目录时用 `git rev-parse --git-common-dir` 定位主仓库，仍失败则引导管理员运行修复脚本（群聊不暴露路径细节）。
- README 新增「桥接 worktree 与运行数据」章节；DEPLOY 新增故障排查两行 + 测试节提示。

---

## [v0.2.2] - 2026-08-29（未发布）

内置模组全部入库 + 模组目录约定。

- **《玩具跳着舞蹈来》（`toy-dancer-comes`）随仓库分发**：按项目所有者决定移除 .gitignore / 打包脚本对该模块的排除；作者原条款（禁止商业用途、禁止修改后二次发布）保留于模块内 `README.md`，根 README 版权说明同步更新。
- **模组目录约定**：所有模组（内置 + 未来导入）一律放工作区 `modules/<id>/`；`COC_MODULES_DIR` 可重定位但必须仍在工作区内；新增模组步骤写入根 README 与 DEPLOY.md。
- 原版 PDF 与转换源稿（`模组/`）仍不入库、不随发布分发。

---

## [v0.2.1] - 2026-08-29（未发布）

失败检定叙事措辞修正：**不再断言「没有发现异常」**。

- 背景：断言"没有异常 / 没有线索"同样是剧透——玩家无法区分"这里真没有"与"你没看出来"，一句「没有发现异常」等于告诉玩家此处无物可查。
- 修正：失败检定一律叙述**检定者没能看出更多**（如「你仔细查看，没能从中看出更多端倪」），只描述检定失败本身，不断言场景状态。
- 同步更新：`SKILL.md`（§2.2 规则 4 + 失败叙事规则 + §2.5 + §10 模板与示例）、`USER_GUIDE.md`、`DEPLOY.md`、根 `README.md`。

---

## [v0.2.0] - 2026-08-29

频道感知隐私铁律 + 单一工作区布局 + 脚本路径净化 + 文档/许可/配置接口 + 公开发布。

**🛡️ 隐私（最高优先级）**

- SKILL.md 新增 §2「频道与隐私铁律」：跑团群聊（group/topic）**零 KP 数据**——守密人旁注、（PL 不可见）标注、内部提示、未揭示线索与真相、隐藏 NPC/怪物数值、检定失败后果剧透、`kp-notes` 摘录、机器绝对路径，一律禁止进群聊。
- KP 数据只在守密人私聊（p2p）且确认守密人身份、明确要求时展示概要，**绝不回流任何群聊**。
- 检定失败一律按玩家视角叙述（如「没能从中看出更多端倪」），不再解释「其实你没发现 X」，也**不断言「没有异常」**（断言"没有"= 剧透，见 v0.2.1）。
- 指令表（§5）为 pwd/init/save/load/npc/kp-note/reveal 补频道行为说明；§7 工作流新增「确认频道 → 隐私自检」；§10 输出模板删除旁注类内容；`help.py` 同步隐私措辞并重生缓存。
- **根治** v0.1.x 真实事故：「守密人旁注（PL 不可见）泄漏进跑团群」（§2.5 反面教材）。

**🗂️ 单一工作区 skill 布局**

- Agent 只加载 `<cwd>/.dsh/skills/` 工作区副本（`bot-start.ps1` 以 `DSH_LARK_WORKSPACE=<workspace>` 锁定仓库根目录）。
- **废弃**「复制 skill 到 `~/.dsh/skills/`」的部署方式；用户级旧副本为历史遗留，不再参与部署。

**🧹 脚本路径净化**

- 模组目标目录统一由 `COC_MODULES_DIR` 环境变量锚定（默认 `<skill-root>/modules`，可重定位到工作区内其它目录），所有脚本经 `_common.modules_dir()` 解析，**不写死任何机器绝对路径**。
- 输出路径一律相对形式（`coc-session/<房间>/...`），不再暴露 `D:\...` / `C:\Users\...`。

**📚 文档 / 许可 / 配置接口**

- 根目录新增 `README.md`（简介/架构/隐私承诺/依赖/快速开始/配置接口/目录/版权/路线图/测试）、`CHANGELOG.md`（本文件）、`VERSION`（0.2.0）、`LICENSE`（MIT，© 2026 XK205E3n）。
- 新增「配置你自己的 API Key / Provider / 模型」双通道接口：飞书内指令（`/config`、`/model`、`/provider`、`/key`）+ 本地脚本 `tools/configure-provider.ps1`（交互式、只读不改缺失文件、写前时间戳备份、密钥绝不回显）。
- skill 内 README / DEPLOY / USER_GUIDE / quickstart / bridge 文档同步更新为单一工作区布局与隐私承诺。

**🚀 公开发布**

- `.gitignore`（排除密钥 / 授权模组 / 运行时数据）+ git init + GitHub 公共仓库 + Release v0.2.0。

---

## [v0.1.2] - 2026-08-28

桥接 model 空串修复。

- **修复**：飞书桥接 `profiles.default.preferences.model` 为空字符串，导致机器人对每条消息全部失败（`??` 不跳过空串 → 模型路由被空串短路 → Agent 无 provider/model）。修复为 `"<provider>/<model>"`（如 `minimax-cn/minimax-m3`）。
- 备份：`.dsh/backup/config.json.bak-20260828`；完整诊断：`.dsh/DIAGNOSIS-20260828.md`。
- **遗留操作**：按当时部署手册把 skill 复制到了用户级 `~/.dsh/skills/coc7th-keeper/`；该副本为历史遗留，v0.2.0 起废弃复制做法、改单一工作区副本。

---

## [v0.1.1]

模组扩展 + 列表缓存。

- 新增第三方模组《玩具跳着舞蹈来》（`toy-dancer-comes`，作者 Yukishiro，授权使用；作者禁止修改后二次发布，因此**不随公开仓库分发**，仅本地按需使用）。
- 新增模组列表预渲染缓存（`references/modules-cache.md` / `.json`），`/coc modules` 走 read 缓存、零 plan-gate。

---

## [v0.1.0]

初始版本。

- CoC7th 规则脚本：`roll`（任意骰子）、`check`（技能/对抗/联合/幸运）、`build`（角色生成）、`sanity`（理智）、`combat`（战斗）、`room`（房间生命周期）。
- 飞书部署（dsh-lark-bot 桥接）+ 官方短模组《惊魂》（`the-haunting`，含 2 张预制角色卡）。
- 5 份规则速查（`references/`）+ 玩家说明书（`USER_GUIDE.md`）+ 5 分钟上手（`assets/quickstart.md`）。

---

## 维护约定

1. **每次版本变更必须在本文件追加对应条目**，并在根目录 `VERSION` 同步更新版本号（内容仅一行纯版本号，如 `0.2.0`）。
2. 语义规则：修复/小改 → PATCH；新增功能/模组/配置接口 → MINOR；破坏性变更或里程碑发布 → MAJOR。
3. 涉及隐私规则、指令表（`COMMON / KP / PL` 三张表）或模组的变更，需同步更新 `SKILL.md`、`scripts/help.py`，并运行 `.dsh\bin\coc.cmd build_all_cache` 重生缓存。
4. 发布条目需说明：变更内容、影响面（文档/脚本/缓存/配置）、已知遗留问题（如历史副本、授权模组分发限制）。
