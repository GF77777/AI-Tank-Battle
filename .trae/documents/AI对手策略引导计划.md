# AI 对手策略优化计划（规则引导层）

## Summary

保留 DQN 决策（10 动作、模型不重训），在玩家对战局的 AI 决策执行前加一层**规则引导**，实现用户四点需求：看见人再开火、躲毒圈、放技能、趋向中心。训练自博弈链路不受影响。

## 现状

- AI 决策：[game/core.py](c:/Users/CGF/Desktop/AI坦克大战/game/core.py) `_versus_foe_update` L763-767 —— 每 FRAME_SKIP 帧用 `_build_foe_state`（382 维）+ `agent.act(obs, eps)` → `_decode_vs_action` → `(direction, fire)`，L768-771 执行移动/开火。
- 毒圈：`self.zone_radius`（Chebyshev）、`_in_zone(tank)` L925 已有；草地判定 `grid[r][c] == S.FOREST` L1058；视野半径 `S.VIEW_RADIUS_TILES=6.0`。
- AI 技能：`_foe_try_skill` 已实现（standard 8 格穿甲 / scout 4 格冲锋 / heavy 2 格冲击波）。
- 问题：AI 的 fire 是 DQN 原始输出（乱开火浪费弹上限+暴露位置）；毒圈外不会主动回撤；无全局中心趋近。

## 改动

### 1. game/core.py — 引导层

**a. `_foe_visible(self, foe, target)`（新 helper）**：几何可见性 = 中心距 ≤ `S.VIEW_RADIUS_TILES * S.TILE_SIZE`（144px）且（目标格非 FOREST，或自身与目标同在 FOREST）——与玩家战争迷雾+草地单向隐身同规则。

**b. `_foe_step_to_center(self, foe)`（新 helper）**：取坦克中心格，`dy=8-row, dx=8-col`；候选方向按 |dy|/|dx| 大者优先，选第一个「目标格在界内且非砖/钢」的方向；全被挡返回 None。

**c. `_foe_guide(self, foe, direction, fire)`（核心）**，在 L768 执行前调用（仅玩家局：`self.foe_agent is None` 时）：
1. **躲毒圈（最高优先）**：`not self._in_zone(foe)` 或 cheb 距离 ≥ zone_radius（下一圈将出界，提前撤，zone_radius>0 时）→ `direction = _foe_step_to_center(foe)`（None 则保持原方向）
2. **开火门控**：`fire` 为 True 时遍历对手，若无任何 `_foe_visible` 目标在**自身射程**内（single/burst = `bullet_frames*5`px、fan = `fan_radius`px）→ `fire=False`
3. **中心趋近**：毒圈内安全、最近可见敌人 > 4 格（未接战）、cheb 距离 > 5、且 direction 会使中心距离增大 → `direction = _foe_step_to_center(foe)`

### 2. game/core.py — dash 逃生补充

`_foe_try_skill` 的 scout 分支加一条：出界（`not _in_zone(foe)`）且朝向大致对准中心时也触发 dash（快速撤离），优先于攻击性触发。

### 3. game/settings.py — 开关

`FOE_GUIDE = True`（玩家局 AI 策略引导；训练侧用 foe_agent 判断不受此开关影响，双保险）。

## 假设与决策

- **方案 B（规则引导 + DQN 执行）而非改 reward 重训**：四点行为立即精确生效、零训练成本；DQN 仍负责接战机动
- 训练自博弈（env 注入 foe_agent）**不加引导**，保持学习分布纯净；模型与 382 维观测零改动
- 「看见」采用与玩家一致的迷雾/草地规则，保证 AI 不开"透视枪"
- 躲毒圈预测按下一圈半径提前一格撤（zone_radius-1 出界即撤），避免边缘抖动

## 验证

1. **躲毒圈**：foe 置于 cheb 距离 = zone_radius 处 → 引导后 direction 朝中心，move 后 cheb 距离减 1
2. **开火门控**：敌人 200px 外 fire=True → 引导后 False；敌人 60px 内 → True；敌人躲草、自身草外 → False
3. **中心趋近**：cheb=7、无可见敌、DQN 给向外方向 → 引导后向内
4. **技能保留**：heavy 贴脸仍触发冲击波；scout 出界时向内 dash
5. **训练不受影响**：env 冒烟 200 步 dim=382；`foe_agent is not None` 时引导被跳过
6. `main.py` 无头 5s 不崩
