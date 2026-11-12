# 上传到 GitHub 仓库计划

## Summary

把当前项目初始化为 Git 仓库，提交源码、文档、截图、模型和日志，推送到公共仓库 `GF77777/AI-Tank-Battle`。仅排除个人配置、Python 缓存、错误日志和本地快捷方式。

## Current State Analysis

- 项目目录**不是 Git 仓库**（无 `.git`），也没有 `.gitignore`。
- Git 版本 2.52.0，全局身份已配置为 `CGF <970162651@qq.com>`。
- 未安装 `gh`（GitHub CLI），但 `winget` 1.29 可用。
- 无 Git Credential Manager，HTTPS 推送需要 `gh` 登录或手动 PAT。
- 截图确认 GitHub 账号为 **GF77777**，新建仓库页已选「公共」，仓库尚未创建，未添加 README/gitignore/许可证。
- 主要体积：`models/` 3.9MB（含 `legacy/` 旧模型与训练 CSV）、`.screenshots/` 0.5MB、`game/` 0.5MB、`.trae/documents/` 0.4MB（66 份计划）。
- 需要排除的本地文件：
  - `prefs.json`：含昵称 `zxc`、按键与音量等个人配置；
  - `__pycache__/`、`*.pyc`：Python 缓存；
  - `err.log`：0 字节运行日志；
  - `AI坦克大战.lnk`：指向本机 Python 绝对路径的快捷方式。
- 用户已确认上传：源码、README、`.screenshots/`、`models/`、`.trae/` 计划文档、`playtest/` 与训练日志。

## Proposed Changes

### 1. 新增 `.gitignore`

新建 `c:\Users\CGF\Desktop\AI坦克大战\.gitignore`：

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
prefs.json
err.log
*.lnk
```

不忽略 `models/`、`.screenshots/`、`.trae/`、`playtest/`，保留用户选择的上传内容。

### 2. 初始化仓库并提交

在项目根目录依次执行：

```powershell
git init -b main
git add -A
git status --short
git commit -m "Initial commit: AI 坦克大战 + Double DQN 自博弈训练"
```

提交前用 `git status --short` 核对：`prefs.json`、`__pycache__/`、`err.log`、`AI坦克大战.lnk` 不得出现在待提交列表。

### 3. 创建远程仓库并完成认证

主路径（推荐）：

```powershell
winget install --id GitHub.cli -e --accept-source-agreements --accept-package-agreements
gh auth login --hostname github.com --git-protocol https --web
gh repo create GF77777/AI-Tank-Battle --public --source=. --remote=origin --push
```

`gh auth login --web` 会给出一次性验证码并在浏览器打开授权页，由用户在浏览器完成登录。新开终端后 `gh` 才会进入 PATH，执行前需刷新环境变量。

备选路径（`gh` 安装或登录失败时）：

1. 用户在 <https://github.com/new> 手动创建 `AI-Tank-Battle`，可见性选公共，**不要**勾选 README、gitignore、许可证。
2. 本地执行：

```powershell
git remote add origin https://github.com/GF77777/AI-Tank-Battle.git
git push -u origin main
```

3. 推送时按提示输入 GitHub 用户名 `GF77777`，密码处粘贴 Personal Access Token（在 GitHub Settings → Developer settings → Personal access tokens 生成，勾选 `public_repo`）。

若 `gh repo view GF77777/AI-Tank-Battle` 显示仓库已存在，则跳过 `gh repo create`，改用：

```powershell
git remote add origin https://github.com/GF77777/AI-Tank-Battle.git
git push -u origin main
```

### 4. 推送后验证

- `git remote -v` 指向 `https://github.com/GF77777/AI-Tank-Battle.git`。
- `git ls-files | Measure-Object -Line` 统计提交文件数，应包含 `main.py`、`README.md`、`models/dqn_tank.pth`、`.screenshots/` 图片、`.trae/documents/` 计划。
- `git ls-files | Select-String "prefs.json|err.log|__pycache__|\.lnk"` 结果为空。
- `gh repo view GF77777/AI-Tank-Battle --web`（或手动打开）确认 README 正常渲染、`models/train_curve.png` 可显示。
- 仓库总大小约 5MB，无单文件超过 50MB。

## Assumptions & Decisions

- 仓库名 `AI-Tank-Battle`，可见性公共，默认分支 `main`。
- 排除范围仅限个人配置、缓存、错误日志和本机快捷方式；用户已选择公开全部模型、截图、日志和内部计划文档。
- **隐私提醒**：公共仓库会公开 `playtest/sessions.csv` 中的对局昵称与本地试玩记录，以及 `.trae/documents/` 中的开发计划。如不希望公开，可在推送前删除相应文件，或改为私有仓库。
- 不修改 `README.md` 内容，不添加 LICENSE（本次未要求），不改写 Git 历史，不使用强制推送。
- 若 `winget` 安装 `gh` 失败，自动切换到 PAT 备选路径，不反复重试同一命令。

## Verification

1. `git status` 工作区干净，`main` 分支存在首次提交。
2. `git remote -v` 与 `git branch -vv` 显示已跟踪 `origin/main`。
3. 提交文件清单不含 `prefs.json`、`err.log`、`__pycache__/`、`*.lnk`。
4. 浏览器打开仓库页面，README、截图目录与模型文件均存在且可下载。
5. `gh repo view GF77777/AI-Tank-Battle --json visibility,defaultBranchRef` 返回 `PUBLIC` 与 `main`（使用 gh 路径时）。
