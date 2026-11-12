# 坦克数值重定 + AI 随机坦克与技能计划

## Summary

按用户手绘图把三款坦克的「平A / 技能」统一为格数制，并让对战局 AI 对手随机使用三款坦克、通过规则触发技能（不改动 DQN 模型与 10 动作空间）。

## 现状

- 三款坦克定义在 [game/settings.py](c:/Users/CGF/Desktop/AI坦克大战/game/settings.py) L62-78 `TANK_TYPES`：scout 平A 半图 41 帧 / dash 3 格；standard 平A 全图 / 穿甲弹全图；heavy fan 半径 104px / shockwave 共用 fan_radius。
- AI 对手在 [game/core.py](c:/Users/CGF/Desktop/AI坦克大战/game/core.py) L237 `PlayerTank(fx, fy, "standard")` 固定型号；`_versus_foe_fire` L887 只发普通弹（硬编码 `S.PLAYER_MAX_BULLETS`）；AI 无技能路径。
- 玩家技能：`start_charge/_charge_release/_dash/_shockwave/_fan_fire/_blast_damage`（core.py L577-731），全部硬绑 `self.player`。
- 训练/评估 env（game/env.py）恒 standard；观测 382 维、动作 10，不含坦克类型与技能。

## 手绘数值表 → 具体参数

| 坦克 | 平A（格→px→帧） | 技能 |
|---|---|---|
| 重 heavy | 5 格 = 120px → `fan_radius=120` | shockwave **r=2 格 = 48px** → 新字段 `shock_radius=48`（不再共用 fan_radius） |
| 中 standard | 5 格 = 120px → `bullet_frames=24`（24×5=120px） | 穿甲弹 **8 格 = 192px** → 新字段 `piercing_frames=38`（38×5=190px），不再全图 |
| 轻 scout | 4 格 = 96px → `bullet_frames=19`（95px） | dash **4 格** → `dash_tiles=4` |

`fan_half_angle` 保持 30° 不变。TANK_TYPES 注释同步改写。

## 改动

### 1. game/settings.py — 数值
- scout：`bullet_frames: 19`、`dash_tiles: 4`
- standard：`bullet_frames: 24`（去掉 None）、新增 `piercing_frames: 38`
- heavy：`fan_radius: 120`、新增 `shock_radius: 48`
- 注释按新数值重写（轻：4 格射程 4 格冲锋；中：5 格射程 8 格穿甲；重：5 格扇面 2 格冲击波）

### 2. game/entities.py — 字段
- `PlayerTank.__init__`：新增 `self.piercing_frames = cfg.get("piercing_frames")`、`self.shock_radius = cfg.get("shock_radius", cfg.get("fan_radius", 0))`、`self.burst_pending = 0`（AI 二连发待发数）
- `make_bullet` 支持传 frames 覆盖（穿甲弹用 `piercing_frames`）；若已有等价参数则复用

### 3. game/core.py — 技能参数化 + AI 技能 + 随机型号
1. **玩家技能函数参数化**：`_fan_fire`、`_dash`、`_shockwave`、`_blast_damage` 的目标从 `self.player` 改为参数 `tank`（调用处传 `self.player`，行为不变）
2. **`_versus_foe_fire` 按型号适配**：
   - 弹上限改读 `foe.max_bullets`（不再硬编码 `S.PLAYER_MAX_BULLETS`）
   - `fire_mode=="burst"`：立即发 1 发 + `foe.burst_pending=1`；`_update_tanks` 循环里处理 `burst_pending`（每 6 帧补发，受弹上限约束）
   - `fire_mode=="fan"`：不发弹，直接 `_blast_damage(foe, ...)`（半径 `fan_radius`）+ `fan_flash` 视效（复用现有渲染，把渲染目标参数化或为 foe 单开一条 flash 字段）
3. **AI 规则触发技能** `_foe_try_skill(foe)`（在 `_decide_foe` 尾部调用；AI 无蓄力帧，冷却好且条件满足即释放，释放后 `fire_cooldown = charge_cooldown` 与玩家一致）：
   - standard（穿甲弹）：最近对手距离 ≤ 8 格（192px）→ 发穿甲弹（`piercing_frames` 射程）
   - scout（dash）：最近对手距离 ≤ 4 格（96px）且在前方约 60° 内 → 冲锋
   - heavy（shockwave）：最近对手距离 ≤ 2 格（48px）→ 全向冲击波
   - 对手集合：`[self.player] + 其它 foes`（与 AI 攻击目标一致）
4. **随机型号**：`_spawn_versus_foes` 改 `tank = S.DEFAULT_TANK if self.foe_agent is not None else random.choice(S.TANK_ORDER)`（训练注入 foe_agent 时恒 standard；评估走 dqn_agent——为可控，加 `S.AI_RANDOM_TANK = True` 开关，env.py __init__ 显式置 False，玩家局读开关）
5. foe 渲染确认：foe 精灵若已按 `foe.tank_type` 取表则零改动；若有硬编码 standard 的取表处一并参数化

### 4. game/env.py — 开关
- `__init__`：`S.AI_RANDOM_TANK = False`（训练/评估恒 standard，保证自博弈对手分布稳定）

### 5. 去掉旧反派坦克（用户补充）
- 删除贴皮文件 `assets/tanks/rusher.png`、`assets/tanks/enemy.png`（rusher 已无代码引用；enemy 为旧反派外观）
- [game/sprites.py](c:/Users/CGF/Desktop/AI坦克大战/game/sprites.py) L523：移除 `enemy_tank` 及 `_TANK_ENEMY`/`_PAL_ENEMY` 矩阵与加载逻辑
- [game/core.py](c:/Users/CGF/Desktop/AI坦克大战/game/core.py) L1247：AI 对手渲染改 `sprites.player_tanks[e.tank_type][e.direction]`（随机型号后按型号显示）
- core.py L1117 HUD 图标：改用 `sprites.player_tanks["standard"][S.UP]`
- 全项目 grep 确认无残留 `enemy_tank`/`rusher` 引用

### 6. README.md — 一行同步
- 坦克参数表（射程/技能格数）+ AI 对手随机型号可用技能一句

## 假设与决策

- 手绘图数字解读为**范围/距离（格）**：重平A=扇面半径、重技能=冲击波半径 r=2；中平A=弹射程、中技能=穿甲弹射程 8；轻平A=弹射程、轻技能=冲锋距离
- AI 技能走**规则触发**而非动作空间扩维：不动 10 动作模型与 382 维观测，已训模型无需重训；观测也不加入坦克类型（保持 382 维）
- AI 技能瞬时释放（无蓄力帧）：AI 不模拟按键，冷却机制与玩家一致（共用 fire_cooldown 字段）
- 数值改变弹道行为（standard 弹全图→5 格等），已训模型表现可能波动——验证项含复测，若明显退化再议重训

## 验证

1. **数值单测**：三型号 cfg 读出的 bullet_frames/piercing_frames/fan_radius/shock_radius/dash_tiles 与上表一致
2. **平A 射程**：standard 弹飞 24 帧后消亡（120px 处）；scout 弹 19 帧；heavy fan 判定半径 120px
3. **玩家技能**：heavy 冲击波作用半径 48px；standard 穿甲弹 38 帧消亡；scout 冲锋 4 格（96px）
4. **AI 随机型号**：玩家局起 5 次，foes tank_type 集合 ⊆ TANK_ORDER 且出现非 standard；env 训练局恒全 standard
5. **AI 技能**：构造 heavy AI + 敌人贴脸 2 格 → 触发 shockwave 且 fire_cooldown=42；scout AI 条件不满足时不触发
6. **旧反派清理**：全项目无 `enemy_tank`/`rusher` 引用；main.py 无头跑不报 KeyError
7. **回归**：env 冒烟 200 步 dim=382 不变；`main.py` 无头 5s 不崩
