# 个人 Agent Skills

本仓库维护 4 个个人技能，使用 `~/.agents/skills/` 作为全局技能目录。
[GitHub 仓库](https://github.com/baysicx/baysicx-skills)是技能源码和安装更新的唯一来源。

| 技能 | 用途 |
| --- | --- |
| `name-session` | 为当前会话命名 |
| `python-standards` | Python 开发与代码审查规范 |
| `resume-session` | 从已保存的检查点恢复工作上下文 |
| `session-log` | 将当前工作状态保存为可恢复的检查点 |

## 使用 skills

[`skills`](https://github.com/vercel-labs/skills) 是 Vercel Labs 开源的技能安装管理工具，
负责从 Git 仓库获取技能、安装到客户端目录，并记录来源以便更新和卸载。
本仓库里的技能文件与这个安装工具分别维护。

推荐通过 `npx` 使用，无需提前全局安装 `skills`。首次运行会下载工具，本文将工具版本固定为 `1.7.4`。
这只固定安装器版本；下面的仓库安装命令获取仓库默认分支的技能内容。

新机器需要准备：

- Git。
- Node.js **22.20.0 或更高版本**，以及随附的 npm / npx。
- 能访问 npm registry 和 GitHub；读取这个公开仓库无需配置 GitHub 推送凭据。

可以先检查环境和仓库访问权限：

```bash
git --version
node --version
npm --version
git ls-remote https://github.com/baysicx/baysicx-skills.git HEAD
```

## 新机器一键安装

下面命令适用于使用安装器管理技能副本的机器。维护源码的 Git 工作区使用后文的 Git 流程。

安装本仓库全部技能到用户级 `~/.agents/skills/`：

```bash
npx --yes skills@1.7.4 add \
  baysicx/baysicx-skills \
  --global --agent codex --skill '*' --yes
```

- `--global`：安装为当前用户的全局技能，供多个项目使用。
- `--agent codex`：选择安装器预设的 `.agents/skills/` 目录。
- `--skill '*'`：安装本仓库全部技能；替换为技能名称即可按需安装。
- `--yes`：跳过安装器的交互确认；`npx` 后的 `--yes` 用于确认下载运行工具。

如果要安装到当前项目的 `.agents/skills/`，在项目根目录执行同一命令，去掉 `--global`。
安装完成后，在客户端的技能列表中确认；如果尚未显示，重新启动客户端。

## 查看、更新和卸载安装副本

查看仓库可安装的技能，以及本机已安装的全局技能：

```bash
npx --yes skills@1.7.4 add \
  baysicx/baysicx-skills --list
npx --yes skills@1.7.4 list -g
```

源码维护者提交并推送后，更新本仓库已安装的 4 个技能：

```bash
npx --yes skills@1.7.4 update -g \
  name-session python-standards resume-session session-log
```

仓库新增技能后，重新执行“新机器一键安装”命令以补齐新技能。

卸载某个技能，例如 `name-session`：

```bash
npx --yes skills@1.7.4 remove name-session --global --agent codex --yes
```

安装目录中的本地修改不会自动提交回仓库，更新可能覆盖这些修改。
需要维护技能时，使用 Git 工作区修改、提交和推送。

## 维护源码工作区

本机的 `~/.agents/skills/` 同时是本仓库的 Git 工作区，使用 Git 管理。
移动目录不会自动将它登记为 `skills` 安装器管理的副本。
此工作区中的技能使用 Git 更新，保留 Git 对本地改动的跟踪。
默认远端 `origin` 为 `git@github.com:baysicx/baysicx-skills.git`，维护分支为 `main`。
推送修改需要在 GitHub 配置本机的 SSH 公钥，并具有仓库写入权限。

查看状态并拉取远端更新；拉取前先提交或使用 `git stash` 保存本地修改：

```bash
git -C "$HOME/.agents/skills" status
git -C "$HOME/.agents/skills" pull --ff-only
```

修改技能后，在仓库内提交并推送：

```bash
cd "$HOME/.agents/skills"
git add -- README.md name-session python-standards resume-session session-log
git commit -m "Update personal skills"
git push origin main
```

其他需要维护源码的机器也可以克隆该仓库；克隆到 `~/.agents/skills/` 时，目标目录应不存在或为空。
新建的个人技能目录会自动纳入 Git 的候选文件，提交前用 `git status` 核对文件范围。
Codex 内置技能仍位于 `~/.codex/skills/.system/`；本地运行和测试产物由 `.gitignore` 排除。

## 参考

- [skills 使用说明](https://github.com/vercel-labs/skills)
- [命令参数](https://github.com/vercel-labs/skills/blob/main/docs/commands.md)
- [客户端与安装目录](https://github.com/vercel-labs/skills/blob/main/docs/agents.md)
