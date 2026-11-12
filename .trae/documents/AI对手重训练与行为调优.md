# AI 对手重训练与行为调优（温和版）

## 一、Summary

按用户三条目标重训 DQN 对手：**会到处走**、**往安全区（非毒圈）靠**、**对玩家攻击频率/敏感度不要太大**。
用户已确认：难度=**温和**、训练起点=**从头重新训练**、对局规则辅助 `_foe_guide`=**全部保留**。

实现分四步：①补充状态特征与奖励塑形 → ②对局侧"温和化"参数（开火间隔/瞄准/射程门控）→ ③从头训练新模型 → ④用可量化指标验收后替换 `models/dqn_tank.pth`。

> 关键发现（现状问题）：当前 `models/train_log.csv` 跑到 3000 局时 ε 仍为 **0.669**，因为 ε 衰减 2,000,000 决策步而实际只走了约 45 万步。也就是说现有模型基本是"半随机"，这也是评估胜率在 0–55% 剧烈抖动的主因。本次必须把 ε 衰减改成按实际步数收敛（见 4.1）。

## 二、Current State Analysis

| 关注点 | 现状 | 位置 |
| --- | --- | --- |
| 训练奖励 | 只有 `击杀 +500 / 死亡 -500 / 每步 -1`，无移动、无圈内/圈外、无开火成本 | [settings.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/settings.py#L144-L149)、[env.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/env.py#L178-L184) |
| 状态向量 | 382 维；元信息只有「毒圈半径比例、收缩倒计时」，**没有"自己离安全区边缘多远"** | [env.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/env.py#L120-L127) |
| 移动奖励 | 无；`VS_R_STEP=-1` 只鼓励"尽快结束"，不鼓励走动 | settings.py L147 |
| 躲毒圈 | 模型只能从半径/倒计时间接推断；对局靠 `_foe_guide` 规则兜底（出界/将出界→朝中心） | [core.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/core.py#L1345-L1358) |
| 攻击强度 | AI 每 21 帧（0.35s）可开火；开火时自动转向最近目标，**子弹全程追踪**（`Bullet.target` 每帧转向）；规则门控只要求"在射程内" | [core.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/core.py#L1245-L1258)、[entities.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/entities.py#L117-L128) |
| 蓄力技 | AI 冷却好且玩家在范围内即释放（穿甲 8 格=接近全图） | [core.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/core.py#L1389-L1428) |
| 训练配置 | `--eps-decay 2000000`、`--eps-end 0.10`；3000 局后 ε≈0.67，策略仍是大量随机 | [train.py](file:///c:/Users/CGF/Desktop/AI坦克大战/train.py#L29-L30) |
| 现有模型 | `models/dqn_tank.pth`（3000 局，未收敛）；`models/legacy/` 已有备份习惯 | models/ |

## 三、Proposed Changes

### 3.1 奖励塑形（`game/settings.py` + `game/env.py`）

在 `settings.py` 奖励段新增常量（原 `VS_R_STEP` 从 -1.0 调整为 -0.2）：

```python
VS_R_STEP = -0.2        # 每决策步微罚（原 -1.0 过重，逼 AI 抢死）
VS_R_MOVE = 0.2         # 本决策内位移 >= 3px：鼓励到处走
VS_R_IDLE = -0.2        # 本决策几乎没动：反蹲点
VS_R_ZONE_OUT = -2.0    # 决策时中心格在安全区外
VS_R_ZONE_EDGE = -0.5   # 在安全区边界 1 格内（提前撤离，兼顾"别贴毒圈"）
VS_R_SHOT = -1.0        # 每发子弹/范围技：抑制无意义扫射
VS_R_HIT = 4.0          # 每次有效命中（打掉 1 格血）
```

`env.VersusEnv.step()` 中按"本决策的增量"结算，而不是累计值：

- 位移：`reset()` 记录 `self._prev_xy = (player.x, player.y)`；每步 `moved = hypot(dx, dy)`；`moved >= 3` 给 `VS_R_MOVE`，否则给 `VS_R_IDLE`。
- 安全区：`game._in_zone(game.player)` 为 False → `VS_R_ZONE_OUT`；否则计算 `cheb`（中心 Chebyshev 距离）与 `zone_radius`，`zone_radius - cheb <= 1` 时给 `VS_R_ZONE_EDGE`（`zone_radius > 0` 才判定）。
- 开火/命中：新增坦克计数器（见 3.2），`dshot = player.shots_fired - self._shots0`、`dhit = player.hits_landed - self._hits0`，奖励 `dshot * VS_R_SHOT + dhit * VS_R_HIT`，并在每步后更新基线。
- 击杀/死亡/终局逻辑保持不变；`info` 增加 `shots`、`hits` 便于日志排查。

### 3.2 开火/命中计数（`game/entities.py` + `game/core.py`）

- `Tank.__init__`（entities.py L18-30）新增 `self.shots_fired = 0`、`self.hits_landed = 0`。
- 子弹：`Tank.make_bullet()`（L56-65）末尾 `self.shots_fired += 1`（普弹/穿甲/二连发补发全部覆盖）。
- 范围技：`Game._fan_fire()` 与 `Game._shockwave()` 里 `p.shots_fired += 1`。
- 命中：`Game._versus_bullet_hits()` 中打出伤害的两个分支（打玩家 / 打 AI）各执行 `b.owner.hits_landed += 1`；`Game._blast_damage()` 每次对 `t` 造成伤害时 `attacker.hits_landed += 1`。
- 计数只用于训练奖励与验收统计，不参与任何战斗规则。

### 3.3 状态向量加入"离安全区多远"（`game/env.py`）

- `STATE_DIM` 382 → **384**；元信息由 4 维扩到 6 维：
  - `v[_IDX_META+4] = (zone_radius - cheb) / ZONE_INITIAL_RADIUS`（>0 圈内、<0 圈外，直接给网络"还剩几格安全余量"）
  - `v[_IDX_META+5] = cheb / (MAP_ROWS // 2)`（自身离场地中心的比例）
- `cheb` 用与 `Game._in_zone` 完全相同的算法（中心格 + Chebyshev），保证训练与对局一致。
- 同步更新 `env.py` 顶部与 `build_foe_state` 的维度注释、`_IDX_META` 之后的下标链条（`_IDX_META = _IDX_ITEMS + S.MAX_ITEMS * 4` 不变，`STATE_DIM = _IDX_META + 6`）。
- `train.py` / `evaluate.py` 都从 `STATE_DIM` 取维度，无需改；从头训练，不存在旧权重迁移问题。

### 3.4 对局侧"温和化"参数（`game/settings.py` + `game/core.py`）

新增常量：

```python
AI_FIRE_COOLDOWN_SCALE = 1.35   # AI 冷却与蓄力技冷却倍率（21帧 -> 28帧，约 0.47s）
AI_FIRE_RANGE_RATIO = 0.8       # 只在目标进入 80% 射程内才扣扳机（留反应/走位空间）
AI_BULLET_HOMING = False        # AI 子弹直飞，玩家子弹保留追踪（降低"必中"压迫感）
```

- `Game._spawn_versus_foes()`：AI 生成后把 `base_fire_cooldown`、`fire_cooldown_max`、`charge_cooldown` 乘以 `AI_FIRE_COOLDOWN_SCALE`（只影响 AI，玩家数值不变）。
- `Game._foe_fire_bullet()`（L1260）：入口处 `if not S.AI_BULLET_HOMING: target = None`，一处覆盖普弹/二连发补发/穿甲。
- `Game._foe_guide()` 的火力门控（L1371-1375）改为 `near_px > rng * S.AI_FIRE_RANGE_RATIO` 就不开火；其余两条（躲圈撤离、趋向中心）**保持不变**（用户要求保留全部辅助）。
- `Game._foe_try_skill()`：触发距离乘以 `AI_FIRE_RANGE_RATIO`（穿甲 8 格→6.4 格；扇形/冲击波同理），避免远距离隔图点人。

> 说明：3.4 是"不重训也立刻生效"的行为参数；配合 3.1 的奖励塑形，训练出的策略本身也会更倾向于少空放、先占安全位。

### 3.5 训练配置（`train.py`）

- 默认值调整为与新方案匹配（从零训练约 5000 局 ≈ 70 万决策步）：
  - `--eps-decay` 默认 `2_000_000` → `250_000`
  - `--eps-end` 默认 `0.10` → `0.05`
- 其余超参不动（`--batch-size 128`、`--lr 5e-4`、`--gamma 0.99`、`--sync 500`、`--learn-every 4`）。
- 不改动 `evaluate.py`（继续用自博弈 ε=0 评估）。

### 3.6 训练与安装流程

1. 备份旧模型与旧日志：
   - `models/dqn_tank.pth` → `models/legacy/dqn_tank_before_mild.pth`
   - `models/train_log.csv` → `models/legacy/train_log_before_mild.csv`，`models/eval_log.csv` → `models/legacy/eval_log_before_mild.csv`（让新训练写一份干净的日志）
2. 从头训练（后台运行，不阻塞）：
   ```
   python train.py --episodes 5000 --eps-decay 250000 --eps-end 0.05 \
       --save-every 250 --log-every 100 --seed 0 --out models/dqn_tank_v2.pth
   ```
3. 训练中每 ~500 局看一次 `models/train_log.csv` 尾部与 `[EVAL]` 行；若 2000 局后平均击杀仍为 0 且胜率为 0，先停下排查 ε/奖励量级，不要盲跑到 5000。
4. 训练完成 → 跑 3.7 的行为验收脚本；达标后 `Copy-Item models/dqn_tank_v2.pth models/dqn_tank.pth`（保留 v2 原文件便于回滚）。

### 3.7 行为验收（临时脚本，用完删除）

用 `play_ai.py` 同款接线（`Game` + `dqn_agent` + `agent.act(obs, 0.0)`）跑 10 局纯 AI 自博弈，统计：

- **到处走**：每局累计移动格数、访问过的不同格子数。
- **安全区**：所有 AI 处于圈外的决策步占比。
- **攻击强度**：AI 每局开火次数、每分钟开火次数、对玩家造成的掉血次数、首个敌人接战时间。

同一脚本先用备份的旧模型跑一遍作为基线，输出「旧/新」对照表。判定标准（温和版）：

| 指标 | 目标 |
| --- | --- |
| AI 圈外决策步占比 | ≤ 5% |
| AI 每局平均开火 | ≤ 12 发（≈0.3 发/秒） |
| AI 对玩家造成掉血 | ≤ 3 次/局 |
| 每局访问不同格子数 | ≥ 20（旧模型基线对比应有提升） |

未达标时的处置顺序（写死在计划里，避免执行时纠结）：先调 `VS_R_SHOT` / `AI_FIRE_COOLDOWN_SCALE`（±0.2 / ±0.1）并重跑 500 局小规模训练验证；仍不达标再调 `VS_R_MOVE` / `VS_R_ZONE_OUT` 量级。

## 四、Assumptions & Decisions

1. **保留全部 `_foe_guide`**：躲圈、只在射程内开火、趋向中心都保留；"温和"通过射程比例门控 + 冷却倍率 + 子弹不追踪实现，不改规则结构。
2. **AI 子弹不追踪、玩家保留追踪**：这是降低"敏感度"最直接的手感改动；同时训练中 AI 一侧也用直飞，保持训练/对局一致。
3. **训练从零开始**：用户已确认；因此可以安全地扩维到 384，不必做旧权重迁移。
4. **训练规模 5000 局**：与现有 3000 局同量级、但 ε 能真正收敛到 0.05；若中途指标明显异常，按 3.6 第 3 步提前止损。
5. **不改玩家侧数值**（移速、冷却、弹匣、追踪），只动 AI 与奖励函数。
6. **训练日志重置**：旧日志移到 `models/legacy/`，不删除；`plot_curve.py` 后续只画新日志曲线。

## 五、Verification

1. `python -m py_compile game/core.py game/env.py game/settings.py game/entities.py train.py` 无语法错误。
2. 无头冒烟：`VersusEnv().reset()` / `step()` 正常返回 `STATE_DIM=384` 的状态；确认 `shots_fired/hits_landed` 随射击/命中递增。
3. 训练日志：ε 在约 25 万步后到 0.05；`[EVAL]` 胜率与击杀随局数上升（不要求很高，但不能长期全 0）。
4. 3.7 行为对照表达到"温和版"阈值。
5. 手动快速验证（可选，需用户在场）：`python play_ai.py --model models/dqn_tank_v2.pth` 观察 AI 是否走动、是否主动进圈、开火是否克制。
6. 安装新模型后进入游戏「对战模式」打一局，确认无报错、AI 行为符合预期、旧模型可从 `models/legacy/` 回滚。
