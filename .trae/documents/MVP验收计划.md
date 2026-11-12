# MVP 验收计划

## 目标

回答「项目现在是否已构成最小 MVP」：按验收清单逐项无头验证，发现的小问题顺手修复，最终输出一份结论报告（MVP验收报告.md）。

## 现状分析（Phase 1 已确认）

**游戏链路完整**（game/core.py）：
- 状态机齐全：`STATE_START`（标题/菜单/仓库/出战配置/人数配置 L125）→ `STATE_PLAYING`（L201）→ `STATE_PAUSED`（L239）→ `STATE_WIN/STATE_LOSE`（L876）
- 战斗要素：移动 `move_tank` L379、开火 `player_fire` L418、道具、毒圈、战争迷雾（`_render_field` L948 内 in_view 过滤）、淘汰判定 `_check_win` L870
- 渲染：HUD L917、开始界面 L1119、暂停 L1253、结算覆盖层 L1094

**AI 链路闭环**：
- env.py `VersusEnv`（382 维状态 / 10 动作 / 奖励）+ ai/dqn.py Double DQN（在线/目标网、回放、宽容加载）
- train.py 训练入口、evaluate.py 评估、play_ai.py 观战
- **已有训练产物**：models/dqn_tank.pth（543KB，今日 0:08 更新，train_log.csv 显示 5000 局已完成）

**支撑件**：requirements.txt（pygame/torch/numpy）、game/audio.py（音效）、README.md（运行说明）

**结论预判**：已具备 MVP 形态，验收重点是「跑起来不崩 + 胜负可达 + AI 有基本智能」。

## 验收清单与验证步骤

全程 `SDL_VIDEODRIVER=dummy` 无头执行，脚本均通过 stdin 传入、不落盘。

### 1. 启动与菜单（只读验证）
- `python main.py` 无头 5 秒不崩（err.log 无 Traceback）
- 模拟按键事件遍历：标题界面 ↑↓ 移动光标、A/D 切换坦克与人数（2/3/4）、Enter 进入对战

### 2. 对战主链路
- 开局：人数配置 2/3/4 → foes 数量 1/2/3、出生点按 SPAWNS_BY_COUNT 落位
- 战斗推进：step 600 帧无异常；毒圈按 6s+8s 节奏收缩；道具定时刷新
- 胜负判定：
  - 直接清空 `versus_foes`（全灭）→ 下一帧进 `STATE_WIN`
  - 清空玩家血量 → `STATE_LOSE`
  - 结算界面按 Enter 能重开（状态回 PLAYING）

### 3. AI 基本智能（不追求胜率，只证非随机）
- 加载 models/dqn_tank.pth，`evaluate.py --episodes 5 --seed 1` 跑通出日志
- 放宽标准：5 局内有 AI 间互相击杀或学习者命中得分即算「有行为」；胜率数据照实记录

### 4. 训练链路冒烟
- `train.py --episodes 3`（临时小跑）确认能启动训练循环、写日志、存模型；不覆盖现有 dqn_tank.pth（先备份到 models/legacy/ 或用临时输出名）

### 5. 文档一致性
- README 玩法说明与 settings.py 当前常量核对（人数、毒圈、视野），不一致处一行级修正

## 修复原则

- 验收中发现的崩溃/卡死/明显逻辑错误：直接修
- 手感、平衡、美观类问题：只记录进报告「已知不足」，不修
- 不新增任何 MVP 外功能

## 产出

1. 修复（若有）：就地小改，附验证
2. **MVP验收报告.md**（项目根目录）：验收清单逐项打勾、关键数据（模型局数/评估表现）、已知不足与下一步建议
3. 聊天内给出最终结论：是 / 否已达 MVP
