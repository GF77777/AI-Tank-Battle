# 把 DQN 真正训出来：路线图与实施计划

## 1. 概要（Summary）

**MVP 状态判定：已完成。** 需求文档第 6 节"必须有"清单全部达成：移动/射击、地形与碰撞、3 条命 + 基地 1 血、刷怪与胜负、开始/进行/胜利/失败四态界面、完整关卡；此外还额外交付了 DQN 训练管线。当前唯一明显短板是 **AI 还很笨**：`models/train_log.csv` 只有 70 局记录（ε 仍 ≈0.99，基本是随机探索），胜率 0%、平均击杀 0~2。

本轮方向（用户已确认）：**把 AI 真正训出来**。具体做三件事：

1. 新增**独立评估脚本**（贪心策略 ε=0 跑 N 局，给出胜率/击杀/得分），提供训练前后可比的客观指标；
2. 增强 `train.py`：随机种子、学习频率、训练中途贪心评估并把评估曲线落盘；
3. 跑**完整训练（2000 局）**，按评估结果做一轮超参微调，最后产出训练曲线图并验证 AI 实际变强。

不改游戏规则、不改状态向量维度（248）、不改动作空间（10），因此不影响现有人类玩法与 `play_ai.py`。

## 2. 现状分析（Current State）

* [train.py](file:///c:/Users/CJP/Desktop/AI坦克大战/train.py#L56-L93)：默认 2000 局，但只跑过 3 次小规模冒烟（50 + 10 + 10 局），日志里 episode 编号多次从 1 重新开始，ε 最低只到 0.9878，AI 实际等价于随机策略。
* [dqn.py](file:///c:/Users/CJP/Desktop/AI坦克大战/ai/dqn.py#L45-L104)：Double DQN + 100k 回放 + batch 64 + γ=0.99 + lr=1e-3 + Huber，算法本身合理，无需改动。
* [env.py](file:///c:/Users/CJP/Desktop/AI坦克大战/game/env.py#L20-L80)：248 维状态、10 动作、4 帧决策、奖励（击杀 +100 / 被击中 -100 / 失败 -500 / 胜利 +500 / 每步 -0.1）均正常，冒烟 1000 步无异常。
* **缺评估手段**：现在只能靠训练日志里的"探索期胜率"看效果，ε 高时该指标失真；没有独立的贪心评估，无法判断模型是否真的学会了。
* **缺训练曲线**：CSV 只能看数字，没有可视化；本机 **未安装 matplotlib**（已确认 site-packages 无 matplotlib），不引入新依赖，用已有的 pygame 画图。
* 训练速度参考：50 局冒烟在数分钟内完成，2000 局预计 30~90 分钟（CPU），因此要支持后台跑 + 定期 checkpoint。
* 旧日志是多次运行追加的，episode 编号有重复，画曲线时必须**按行序**而不是按 episode 值作图。

## 3. 变更内容（Proposed Changes）

### 3.1 新建 [evaluate.py](file:///c:/Users/CJP/Desktop/AI坦克大战/evaluate.py) — 独立贪心评估脚本

* 结构：
  * 文件顶部 `os.environ.setdefault("SDL_VIDEODRIVER", "dummy")`（必须在导入 pygame 之前）；
  * `parse_args()`：`--model`（默认 `models/dqn_tank.pth`）、`--episodes`（默认 20）、`--seed`（默认 123，保证多次评估可比）、`--out`（默认 `models/eval_result.csv`，写每局明细：`episode,reward,kills,win,steps,score`）；
  * `evaluate(agent, episodes, seed=None) -> dict`：内部新建独立 `TankEnv()`，每局 `reset()` 后用 `agent.act(state, 0.0)` 跑完，统计返回
    `{"win_rate", "avg_kills", "avg_reward", "avg_steps", "avg_score"}`；
  * `main()`：加载模型（不存在时 `SystemExit` 提示先训练）、打印汇总、写 CSV。
* 可被 `train.py` 复用（避免重复实现评估逻辑）。

### 3.2 修改 [train.py](file:///c:/Users/CJP/Desktop/AI坦克大战/train.py) — 训练过程可观测、可复现、可调速

新增参数（保持现有参数与 `train_log.csv` 格式不变）：

| 参数 | 默认 | 作用 |
|---|---|---|
| `--seed` | 0 | 统一 random / numpy / torch 种子 |
| `--learn-every` | 1 | 每 k 个决策步做一次梯度更新（提速用） |
| `--eval-every` | 100 | 每 N 局做一次贪心评估；0 关闭 |
| `--eval-episodes` | 10 | 每次评估跑几局 |

实现要点：

* 每局 `episode,reward,kills,win,epsilon,steps` 仍写入 `models/train_log.csv`（追加，格式不变）；
* 新增 `models/eval_log.csv`（表头 `train_episode,eval_win_rate,eval_avg_kills,eval_avg_reward,eval_avg_steps`），每次评估追加一行并打印 `[EVAL] ep=... 胜率=... 平均击杀=... 平均奖励=...`；
* 评估使用**独立** `TankEnv()` 实例、`agent.act(state, 0.0)`、只前向不学习、不写回放池，避免污染训练数据；
* `--resume` 已有，配合 `--eps-start` 可做二次微调（例如 `--resume models/dqn_tank.pth --eps-start 0.3`）。

### 3.3 新建 [plot_curve.py](file:///c:/Users/CJP/Desktop/AI坦克大战/plot_curve.py) — 训练曲线（无新依赖）

* 读取 `models/train_log.csv`（按**行序**作图，兼容多次运行追加）与可选的 `models/eval_log.csv`；
* 用 pygame 画 960×640 的 PNG（`SDL_VIDEODRIVER=dummy`）：
  * 上panel：每局奖励（细线）+ 窗口均值（20 局滑动，粗线），左轴；
  * 下panel：评估胜率（0~100%）折线 + 平均击杀折线（右轴标注）；
  * 复用 `game/core.py` 的 `get_font()` 渲染中文标题/图例；
* 输出 `models/train_curve.png`，不依赖 matplotlib（`requirements.txt` 不变）。

### 3.4 不改动的文件（明确边界）

* `game/env.py`、`game/settings.py`：奖励权重、状态/动作空间保持原样（调参只走 CLI，不改默认值）。
* `ai/dqn.py`：算法与网络结构保持原样。
* `game/*`、`main.py`、`play_ai.py`：游戏与观战逻辑不动。

## 4. 训练与调参执行方案（Training Playbook）

1. **基线评估**：`python evaluate.py --episodes 20 --seed 123` → 记录基线（预期胜率 0%、平均击杀 ≈0~1，写入报告）。
2. **管线冒烟**：`python train.py --episodes 100 --learn-every 2 --eval-every 50 --eval-episodes 5` → 确认 `eval_log.csv` 正常生成、无报错、模型保存。
3. **正式训练**（后台运行，每 200 局自动 checkpoint）：
   `python train.py --episodes 2000 --learn-every 2 --eval-every 100 --eval-episodes 10 --save-every 200`
   * 让 ε 在约 50 万决策步内从 1.0 衰减到 0.05（默认 `--eps-decay 500000`）；
   * 训练期间定期查看 `train_log.csv` / `eval_log.csv` 末几行。
4. **终评**：`python evaluate.py --episodes 20 --seed 123` → 与基线同种子对比。
5. **验收门槛**：贪心评估 **平均击杀 ≥ 3 且至少赢 1 局（胜率 ≥ 5%）**。
6. **未达标的兜底（按顺序尝试，最多两轮）**：
   * 追加训练：`python train.py --episodes 2000 --resume models/dqn_tank.pth --eps-start 0.3 --eps-decay 300000 --learn-every 2 --eval-every 100 --save-every 200`，再评估；
   * 若仍只会"原地不动/乱走"：把奖励微调为 `R_STEP=-0.05`、`R_KILL=150`（改 `settings.py` 两行常量）后从头再训 2000 局；
   * 每一步都保留模型历史（`--out models/dqn_tank_v2.pth`），便于对比择优。
7. **可视化交付**：`python plot_curve.py` 生成 `models/train_curve.png`。

## 5. 关键假设与决策（Assumptions & Decisions）

1. MVP 判定标准采用需求文档第 6 节"必须有"：全部完成 → MVP 完成；"应该有"（多敌型/道具/多关卡）本轮不做。
2. 本轮只做"把 AI 训出来"，不扩展游戏内容、不加音效、不打包 exe。
3. 不引入 matplotlib 等新依赖，曲线图用 pygame 自绘。
4. 评估统一用固定种子（默认 123）与贪心策略，保证训练前后可对比；训练本身仍保留随机性。
5. 训练长期跑在 CPU 上（本机无 CUDA 依赖），`--learn-every 2` 作为提速默认值只影响训练命令，不改代码默认。
6. 旧 `train_log.csv` 继续追加、不清空；曲线按行序绘制以兼容重复 episode 编号。

## 6. 验证方案（Verification）

| 验证项 | 方法 | 通过标准 |
|---|---|---|
| 评估脚本可用 | `python evaluate.py --episodes 10` | 正常输出胜率/击杀/奖励/步数，生成 `eval_result.csv` |
| 训练可观测 | 100 局冒烟训练 | `train_log.csv` 追加、`eval_log.csv` 每 50 局一行、[EVAL] 打印正常 |
| 可复现 | 同种子跑两次评估 | 指标完全一致 |
| 可调速 | 对比 `--learn-every 1/2` 的 100 局耗时 | learn-every=2 明显更快且仍能学习 |
| 正式训练 | 2000 局后台跑 + 日志监控 | 无异常中断、ε 平滑降到 0.05、checkpoint 每 200 局生成 |
| AI 变强 | 终评 20 局 vs 基线同种子 | 平均击杀 ≥ 3、胜率 ≥ 5%（至少 1 胜） |
| 曲线图 | `python plot_curve.py` | 生成 `models/train_curve.png`，奖励趋势与评估胜率清晰可读 |
| 观战回归 | `play_ai.py` headless 跑一局 | 加载新模型正常、击杀数 > 0（明显优于基线） |
| 人类玩法回归 | 开局 → 移动射击 → 胜负流程 | 与修复前一致，无回归 |
