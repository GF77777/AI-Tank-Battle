# 平A改圆圈锁定 + 追踪弹

## Summary
把平A从"4方向直线弹"升级为"以坦克为中心的锁定圈 + 追踪弹"：
1. 射程提示从上一版的直线/扇形虚线改为**以玩家为中心的虚线圆圈**（锁定到目标时变红）。
2. 开火时圈内最近可视敌人被锁定，**子弹发射后持续转向追踪目标**；圈内无目标则照常沿车头直线发射。
3. 玩家与 AI 同规则（对称锁定）。

## Current State（已探索确认）
- 自动瞄准半成品已存在：`player_fire`（core.py:579-597）与 `_versus_foe_fire`（core.py:806-819）都会先 `_auto_target`（core.py:853-865：射程圆内最近可视活敌，排除无敌期）再 `set_direction` 4方向转头；但子弹仍沿 4 方向直线飞（对角打不中）。
- `Bullet`（entities.py:95-121）：只有 4 方向 `direction`，`update()` 沿 DIR_VECTORS 直线飞，`frames_left` 限射程。
- 锁定圈半径已有现成口径：`_auto_target` 用 `fan_radius`（heavy=60）或 `bullet_frames*5`（scout=70 / standard=95）。
- 兼容性：
  - 击退与命中走 `b.direction`（core.py:1153/1156）→ 保持 `b.direction` 实时更新为速度主导轴即可兼容。
  - 撞墙 `_bullet_vs_tiles`（core.py:1161）是 rect 判定 → 对角飞天然兼容。
  - RL 状态向量子弹位 `S.DIR_VECTORS[b.direction]`（env.py:93）→ direction 主导轴近似即可，**STATE_DIM=382 不变**，模型输入兼容；但动力学变化，**模型建议重训**。
- 射程虚线现状：`_render_range_hint`（core.py:1540-1588，直线/扇形）→ 本次重写为圆圈。

## Proposed Changes

### 1. `game/settings.py`：新增追踪转角常量
```python
BULLET_HOMING_TURN = 0.10    # 追踪弹每帧最大转角（弧度，≈5.7°），越大拐得越急
```

### 2. `game/entities.py`：Bullet 矢量化 + 追踪
- `Bullet.__init__(..., target=None)`：新增 `self.target = target`；`self.vx, self.vy` = 初始朝向单位向量（浮点）。
- `Bullet.update()` 重写移动部分：
  - 若 `target` 非 None 且 `target.alive`：用 `atan2` 求期望角与当前速度角的差，按 `±S.BULLET_HOMING_TURN` clamp 后旋转 `(vx, vy)`；目标死亡则保持当前矢量直飞。
  - `self.x += vx * S.BULLET_SPEED`、`self.y += vy * S.BULLET_SPEED`。
  - 每帧把 `self.direction` 更新为速度主导轴 4 方向（|vx|≥|vy| 取左右，否则上下）——供击退方向与 RL 状态复用。
  - `frames_left` 递减消亡、出界消亡逻辑不变。
- `Tank.make_bullet(self, piercing=False, max_frames=None, target=None)`：透传 `target` 给 Bullet。

### 3. `game/core.py`：开火链路挂锁（玩家与 AI 同规则）
- `_fire_bullet` 与 `_foe_fire_bullet` 均加 `target=None` 参数，透传 `make_bullet`。
- `player_fire`（core.py:579）：`_auto_target` 结果同时用于转头（保留，视觉朝向）和挂锁；三条分支全部透传：
  - 穿甲蓄力技：也传 target（锁圈按平A圈，弹射程仍 piercing_frames）。
  - burst 首发 / single：传 target。
- burst 第二发补出（core.py:484 玩家；AI 补发约 core.py:801 附近）：补发瞬间重新 `_auto_target` 挂锁（目标可能已移动/死亡）。
- `_versus_foe_fire`（core.py:806）：同样把 `_auto_target(foe)` 传给 `_foe_fire_bullet`。
- fan（重装）：机制不变（扇形已借转头自动对准最近目标，等于圈内锁定）。
- 无目标：`target=None`，子弹沿车头矢量直飞（=现状）。

### 4. `game/core.py`：`_render_range_hint` 重写为虚线圆圈
- 圆心 = 玩家中心（含 oy 偏移）；半径 = `fan_radius`（heavy）或 `bullet_frames * S.BULLET_SPEED`（其余）。
- 画法：48 段圆周，隔段画 1px 短线（虚线效果），画在全屏 SRCALPHA surface 再 blit（沿用现有套路）。
- 颜色：未锁定半透明白 `(255,255,255,160)`；渲染时每帧调 `_auto_target(self.player)`，非 None 则红 `(255,90,70,180)`（锁定反馈）。
- 删除旧的直线/扇形虚线逻辑；调用点（core.py:1462）不变。

## Assumptions & Decisions
- 锁定建立后持续跟踪直到目标死亡，不因进草/出视野断锁（简单起见）。
- 追踪只挂"开火瞬间最近目标"，不中途中途换目标。
- 蓄力穿甲弹同样追踪（复用同一 target）；疾冲/冲击波技能不变。
- 重装平A 仍是扇形冲击（圆圈=扇形半径=锁人圈），不改为全向（全向是其蓄力技）。
- RL：`STATE_DIM` 不变、env.py 不改；动力学已变，`models/dqn_tank.pth` 需重训（train.py），计划中只提示不重训。

## Verification
1. 无头冒烟脚本（放 workspace 外或临时文件，跑完即删）：
   - 截图验证：三款坦克虚线圆圈半径正确（70/95/60）、锁定变红。
   - 追踪验证：把敌人摆在玩家对角（45° 方向、圈内），开火后逐帧 `update()`，断言若干帧内敌人 `hp` 下降（旧逻辑下对角直线弹必 miss）。
   - 无目标验证：清空敌人开火，子弹沿车头直线飞且 `frames_left` 到 0 消亡。
   - AI 对称验证：foe 开火后其子弹带 target。
2. `python main.py` 人工试玩：圆圈随坦克移动、锁人变红、子弹拐弯命中。
