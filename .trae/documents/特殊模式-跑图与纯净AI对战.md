# 新增特殊模式：跑图练习（固定靶）+ 纯净版 AI 对战

## Summary
主菜单按钮列从 4 个扩到 6 个，新增两个模式，只改 `game/core.py`（+ 少量 settings/文案）：
1. **跑图练习**（`MODE_ROAM`）：地图只有玩家 + 4 个静止靶子坦克；无毒圈/无道具/无 AI；靶子全灭后自动重建，Esc→暂停→返回标题。用于练手（含追踪弹）。
2. **AI 对战·纯净版**（`MODE_PURE`）：复用 DQN AI 对手与"杀光 AI 获胜"规则，但**关闭毒圈、道具、空投**，纯拼枪。

## Current State（已读代码确认）
- 模式常量（core.py:24-26）：`MODE_VERSUS=0, MODE_CURVE=1, MODE_GARAGE=2, ROW_TANK_CONFIG=3, ROW_NUM_CONFIG=4, ROW_SETTINGS=5, ROW_COUNT=6`；标题 6 行 W/S 循环（`% ROW_COUNT`）。
- 开局：`_reset_battle`（core.py:183，固定生成 AI foes+毒圈+道具计时）；`_start_versus`（core.py:221，懒加载 DQN 模型，缺失时 `start_notice="versus"`）。
- 每帧 `update`（core.py:476-528）：`_update_items()`、`_update_zone()` 无条件调用；`_check_win`（core.py:1277）全灭 AI→胜；玩家死→`_end(False)`。
- 重开硬编码：暂停菜单 `pause_index==1` → `_start_versus`（core.py:360）；结算 Enter → `_start_versus`（core.py:368）。
- 击杀掉落：`_damage_foe` 内有 `_drop_item` 掉落（需按模式门禁）。
- 按钮列：`_menu_button(screen, text, y, selected)`，当前 `MODE_Y0=232`、行距 32；鼠标 `_on_click` 用 `(MODE_VERSUS, MODE_CURVE, MODE_GARAGE, ROW_SETTINGS)` 元组逐个 rect 判定。
- 跑图伤害可行性：`_damage_foe` 需要 `foe.lives/foe.tag`（上次的疾冲 crash 已确认）；玩家追踪弹经 `_auto_target` 锁定 `versus_foes` 内目标——靶子放进去即可被锁定/击中。

## Proposed Changes

### 1. 常量与文案
- core.py:24-26 重排常量（W/S 顺序=视觉从上到下）：
  `MODE_VERSUS=0, MODE_PURE=1, MODE_ROAM=2, MODE_CURVE=3, MODE_GARAGE=4, ROW_TANK_CONFIG=5, ROW_NUM_CONFIG=6, ROW_SETTINGS=7, ROW_COUNT=8`。
  （实现时先 grep `MODE_CURVE|MODE_GARAGE|ROW_TANK_CONFIG|ROW_NUM_CONFIG|ROW_SETTINGS` 在 env.py/train.py 等文件有无数字字面值依赖，有则同步。）
- `_TEXTS` 新增：
  - `"mode_pure"`：`("AI 对战", "VS AI")`；`"mode_roam"`：`("跑图练习", "FREE ROAM")`
  - `"roam_reset"`：`("靶子已全部重建", "TARGETS RESET")`
- `MODE_Y0` 232→**222**（6 按钮：222..382，避开底部分隔线 424）。

### 2. 模式状态字段
- `__init__`：`self.battle_mode = "versus"`；`_reset_battle` 首行重置为 `"versus"`（训练/评估路径行为不变）。

### 3. 两个入口函数（core.py，紧邻 `_start_versus`）
- `_ensure_agent(self) -> bool`：从 `_start_versus` 抽出 DQN 懒加载逻辑，模型缺失时置 `start_notice="versus"` 返回 False。
- `_start_pure(self)`：
  ```python
  if not self._ensure_agent():
      return
  self._reset_battle()
  self.battle_mode = "pure"        # 纯拼枪：无毒圈/道具/空投
  if self.playtest is not None:
      self.playtest.start_session()
  self.state = STATE_PLAYING
  ```
  `_start_versus` 改为调用 `_ensure_agent` 复用（行为不变）。
- `_start_roam(self)`：
  ```python
  self._reset_battle()
  self.battle_mode = "roam"
  self.versus_foes.clear(); self.enemies.clear()
  self._spawn_roam_dummies()       # 4 个静止靶
  self.state = STATE_PLAYING       # 无需 DQN 模型
  ```
- `_spawn_roam_dummies(self)`：在 `(8,8) (14,8) (8,2) (14,2)` 4 格放 `PlayerTank(standard)`；`kind="dummy"`、`tag="T1".."T4"`、`lives=1`、`hp=S.VERSUS_HP`、无敌 0、朝向 DOWN、加入 `versus_foes`+`enemies`（被击中/锁定/排名表复用现有路径）。

### 4. update() 按模式门禁（core.py:516-528 区域）
- AI 循环 `for foe in self.enemies: ... _versus_foe_update(foe)`：`battle_mode == "roam"` 时跳过 `_versus_foe_update`（靶子静止，仍 `tick_timers`）。
- `self._update_items(); self._update_zone()`：包进 `if self.battle_mode == "versus":`。
- `_check_win`：开头加 `if self.battle_mode == "roam": return`（跑图无胜负）。
- 跑图靶子重建：roam 且 `versus_foes` 全灭时 → `add_announce(T("roam_reset"), S.GREEN)` + `_spawn_roam_dummies()`。
- `_damage_foe` 掉落门禁：`_drop_item` 仅 `battle_mode == "versus"` 时执行。

### 5. 菜单与输入接线
- `_render_start` 按钮列：`("mode_versus","mode_pure","mode_roam","mode_curve","mode_garage","mode_settings")` 对应 `(MODE_VERSUS, MODE_PURE, MODE_ROAM, MODE_CURVE, MODE_GARAGE, ROW_SETTINGS)`，6 行。
- `_on_click` 根视图 `idxs` 元组同步为同序 6 项。
- `_confirm` 新增分支：`MODE_PURE → _start_pure()`；`MODE_ROAM → _start_roam()`（注意 `else` 分支当前把 MODE_CURVE 兜底为 start_notice，调整 elif 顺序保持该行为）。
- 新增 `_restart_battle(self)`：`{"versus": self._start_versus, "pure": self._start_pure, "roam": self._start_roam}[self.battle_mode]()`；替换暂停菜单重开（core.py:360）与结算 Enter（core.py:368）两处 `_start_versus` 硬编码。

### 6. HUD/渲染适配
- 安全区卡 `_render_zone_card`：仅 `battle_mode == "versus"` 时绘制（纯净/跑图无毒圈）。
- 其余 HUD（剩余数=跑图时显示靶子存活数、血条、弹匣、技能环、锁定圈）全模式通用，不改。
- 结算页排名表：纯净版复用（versus_foes 有 lives/tag）；跑图不进结算。

## Assumptions & Decisions
- 纯净版 AI 仍由 DQN 驱动；模型文件缺失时与对战模式同样提示（复用 `start_notice="versus"` 文案）。
- 跑图玩家不会死（无伤害源），Esc→暂停菜单→返回标题；不提供计分/计时。
- 靶子被击毁进击杀播报（"你 淘汰了 T1"），不掉道具。
- 训练脚本（train.py/env.py/evaluate.py）不改：`battle_mode` 默认 "versus"，训练行为不变。

## Verification
无头冒烟脚本（跑完即删）+ 截图目检：
1. 菜单：6 按钮渲染截图；`_confirm` 在 MODE_PURE/MODE_ROAM 上分别进入对局。
2. 跑图：`versus_foes` 4 个靶、无 AI 移动（连跑 60 帧靶位不变）；击毁全部靶 → 公告 + 自动重建；`zone_timer` 不变、无道具生成。
3. 纯净版：`zone_timer` 60 帧不变、`items` 恒空；全灭 AI → `STATE_WIN`；玩家死 → `STATE_LOSE`。
4. 重开：各模式暂停后 `pause_index=1` 确认，`battle_mode` 保持。
5. `python main.py` 人工过一遍两个新模式。
