# 平A自动攻击 + 弹匣换弹机制 计划

## Summary

两项坦克机制改造，玩家与 AI 完全对称生效：

1. **平A自动攻击**：按下平A时，若射程内存在可视敌人（6 格迷雾 + 草地单向隐身同规则），车头自动转向最近目标并开火；无目标则照常朝原车头方向开火。
2. **弹匣换弹**：弹匣制（标准 4 发 / 轻骑 3 发 / 重装 2 发），打空自动换弹（轻 1s / 标 1.5s / 重 2s），换弹期间不能射击；HUD 显示弹匣点与换弹进度。

不改动 DQN 观测维度（保持 382 维），现有模型无需重训（自博弈同样获得自动瞄准，对称增强）。
顺带修复：[core.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/core.py) 末尾重复定义的旧版 `_versus_foe_fire`（L1054-1063，Python 后定义覆盖前者，导致 AI 随机型号的开火分流失效）。

## 现状分析

- 玩家开火链：[main.py](file:///c:/Users/CGF/Desktop/AI坦克大战/main.py#L51-L54) 空格按下 `start_charge()` → 松开 `release_fire()` → 未蓄满走 `player_fire()`（[core.py L577](file:///c:/Users/CGF/Desktop/AI坦克大战/game/core.py#L577)）→ `_fire_bullet`（L592）/ `_fan_fire`（L609）。
- AI 开火链：`_versus_foe_update`（L754）每帧 `fire=True` 时调 `_versus_foe_fire`（L786，型号分流版）；burst 补发在 L777-782；技能触发 `_foe_try_skill`（L885）。
- 可见性规则：`_foe_visible`（L814）= 6 格视野圆 + 草地单向隐身，与玩家迷雾一致；`in_forest`（L1134）判草。
- 冷却/弹上限：`Tank.can_fire` / `make_bullet`（[entities.py L50-62](file:///c:/Users/CGF/Desktop/AI坦克大战/game/entities.py#L50)）；场上子弹上限 `max_bullets` 与新弹匣是两层独立限制。
- HUD：`_render_hud`（L1278），血条位于 x=286、y=18（12px 高），HUD 总高 48，血条下方 y=34 空闲可放弹匣点。
- **Bug**：L1054-1063 存在第二个 `_versus_foe_fire` 定义（旧版统一 `make_bullet()` 无射程/型号分流），类体顺序执行导致其覆盖 L786 的新版——AI 随机型号后 fan/burst/射程全部失效。必须删除。

## 改动方案

### 1. game/settings.py — 弹匣参数

`TANK_TYPES` 各型号新增字段：

| 型号 | mag_size | reload_frames（60fps） |
|------|----------|------------------------|
| scout | 3 | 60（1s） |
| standard | 4 | 90（1.5s） |
| heavy | 2 | 120（2s） |

注释同步更新（轻骑二连发一次扳机耗 1 发弹匣）。

### 2. game/entities.py — PlayerTank 弹匣字段

`PlayerTank.__init__` 新增：

```python
self.mag_size = cfg["mag_size"]        # 弹匣容量
self.mag = self.mag_size               # 当前余量
self.reload_timer = 0                  # >0 = 换弹中
```

`Tank.tick_timers`（L44）追加：换弹倒数，归零时 `self.mag = self.mag_size`（玩家/AI 共用基类，自动补满）。

### 3. game/core.py — 核心改动

**(a) Bug 修复**：删除 L1054-1063 旧版 `_versus_foe_fire`（连同随之失去唯一调用点的 `Tank.can_fire`，删除前 grep 确认无其他引用）。

**(b) 可见性通用化**：`_foe_visible`（L814）改名 `_tank_visible`（逻辑不变，玩家/AI 通用）；更新 `_foe_guide` 内调用点。

**(c) 新增自动瞄准辅助**：

```python
def _auto_target(self, tank):
    """射程内最近可视敌人（排除无敌期目标），无则 None。
    射程：fan=fan_radius；其余=bullet_frames*5。"""
def _aim_direction(self, tank, target):
    """朝目标的 4 方向（|dx|>=|dy| 取水平，与 _foe_step_to_center 同主轴规则）。"""
```

**(d) 开火入口自动转向**：
- `player_fire`：入口处 `t = self._auto_target(self.player)`，非 None 则 `self.player.set_direction(self._aim_direction(...))` 后走原分流。
- `_versus_foe_fire`（保留 L786 版）：同样入口转向。

**(e) 弹匣消耗与换弹门禁**：`_fire_bullet` / `_foe_fire_bullet` 签名加 `ignore_reload=False, consume_ammo=True`：
- 开头：`not ignore_reload and reload_timer > 0` → return False（换弹中禁射）
- 成功出弹且 `consume_ammo` → `mag -= 1`；`mag <= 0` → `reload_timer = reload_frames`（打空自动换弹）
- 三处调用适配：
  - 普攻（玩家 `_fire_bullet` 默认 / AI `_foe_fire_bullet` 默认）：检查 + 扣弹
  - 蓄力穿甲技（玩家 `player_fire(piercing=True)` / AI `_foe_try_skill` piercing 分支）：`consume_ammo=False`（走独立冷却，不耗弹匣；换弹中仍被门禁挡）
  - burst 补发（玩家 L484 / AI L782）：`ignore_reload=True, consume_ammo=False`（扳机时已确认有弹，补发属同一轮）
- `_fan_fire`：开头加换弹门禁；冷却检查通过后扣 1 发弹匣、打空触发换弹。
- `start_charge`：开头加 `reload_timer > 0 → return`（换弹中禁止蓄力）。
- `_foe_try_skill`：piercing/shockwave 分支前加换弹门禁；**dash 分支不加**（毒圈逃生优先级最高，dash 本身不耗弹）。

**(f) HUD（_render_hud）**：血条下方 y=34 画弹匣点——`mag_size` 个 8x5px 点（有弹黄色 / 已耗暗灰）；换弹中改为进度条（同位置按 `1 - reload_timer/reload_frames` 比例填充黄色），直观显示换弹进度。

### 4. README.md — 机制说明同步

对战玩法段落补充：平A自动瞄准规则、三型号弹匣/换弹时长。

## 设计决策与假设

1. **自动转向而非弹道修正**（用户选定）：车头实际转向目标，下一帧移动输入会覆盖车头——炮弹已按目标方向射出，不影响手感。
2. **蓄力技不消耗弹匣**：dash/shockwave/穿甲弹走独立蓄力冷却，与平A弹药解耦；换弹中禁止蓄力（含蓄力技）。
3. **burst 一次扳机 = 1 发弹匣**：二连发第二发为补发，不重复扣弹、不被换弹打断（`ignore_reload=True`）。
4. **STATE_DIM 保持 382 不变**：不把弹匣余量加入观测，避免维度变更导致旧模型作废；AI 换弹中开火动作自然无效。自博弈训练链路（env.py 注入 foe_agent）同样生效自动瞄准+换弹，训练-部署行为一致；现有模型不重训（对称机制，双方均受影响）。
5. **自动瞄准排除无敌期目标**：与 `_foe_guide` 开火门控口径一致（`invincible <= 0`），避免浪费弹匣触发换弹。
6. **AI dash 换弹中可用**：毒圈逃生优先，dash 非射击行为。

## 验证步骤（SDL_VIDEODRIVER=dummy 无头脚本）

1. 三型号 `mag_size`/`reload_frames` 断言（3/60、4/90、2/120）。
2. standard 连射 4 发：第 4 发后 `reload_timer == 90`、`mag == 0`；第 5 发普攻无效；推进 90 帧 `mag == 4`。
3. 换弹中 `start_charge` 无效；`player_fire` 无效。
4. burst：scout 扳机 1 次仅扣 1 发弹匣；mag=1 时扳机后补发照常出弹且不触发二次消耗。
5. fan：heavy 释放 1 次扣 1 发；打空后 `_fan_fire` 无效直至换弹完成。
6. 自动瞄准：standard 右侧 3 格内置敌 → `player_fire` 后车头 RIGHT、子弹 direction RIGHT；敌在射程外（6 格）→ 车头不变；目标藏草且自身草外 → 不转向。
7. AI 对称：随机型号 foe 开火后车头朝最近可视目标；打空自动换弹；换弹中普攻/穿甲/冲击波被挡、dash 逃生可用。
8. `grep -c "def _versus_foe_fire"` == 1；旧版死代码已删。
9. `VersusEnv` 冒烟 200 决策步，`STATE_DIM == 382` 不崩。
10. 训练局回归：FakeAgent 注入 60 帧不崩。
11. `main.py` 无头冒烟 PASS。
