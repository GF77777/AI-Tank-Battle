# 按线框图重排游戏 UI（深色像素风，仅布局）

## Summary
按用户手绘线框图重排 4 个界面的布局，**只改 `game/core.py`**，保持深色像素风，不新增名字/头像/金币等功能数据，输入逻辑（键盘导航、`mode_index` 语义、A/D 调整）不变。

线框 → 现有元素映射（无对应物的不做）：
- 名字输入/头像/金币 → 不做（用户确认仅布局）
- 主菜单中央 "< 卡片 >" → 现有坦克选择行升级为卡片
- 主菜单 4 按钮 → 对战模式 / 训练曲线 / 坦克仓库 / 设置
- 主菜单顶栏右侧"金币"位 → 现有"人数 ◀N▶"配置
- 设置页"操作说明/改键位" → 不存在，保留 音乐/音效/返回
- 结算页排名表 → 用现有数据派生：存活者按 hp 降序在前、淘汰者在后；行 = 名次 + 标识（你/A/B/C）+ 状态
- 对局右下圆形钮 → 蓄力/冷却状态圆环（数据：`charging/charge_frames/charge_frames_max/fire_cooldown/charge_skill`）
- 对局左中"地图"框 → 安全区（毒圈）信息卡，顶栏右端 ZONE 文本挪入

## Current State（已读代码确认）
- `_render_start`（core.py:1608）：标题居中 + 模式列表（`_menu_button`）+ 配置行（`_render_config_tank`/`_render_config_count` 行式 ◀▶）。
- `_render_settings`（core.py:1667）：音乐/音效/返回 3 行；`settings_from=="pause"` 时才加面板遮罩。
- `_render_end`（core.py:~1800-1828）：居中纯文本（胜负/原因/分数/用时/击杀 + 闪烁 Enter 提示），无卡片无按钮。
- `_render_hud`（core.py:1336）：左=剩余敌数 icon+数字；中=分数；右=生命格+弹匣点（y34）；右端=ZONE 倒计时文本。
- `_render_overlays`（core.py:1305）：公告 HUD 下方居中（黑底胶囊，最多2条）；击杀播报右上角（最近3条）。
- 蓄力条：玩家头顶（core.py:1463-1467 附近，`self.charging/charge_frames`）。
- 文案：`T(key)` + `_TEXTS` 表（core.py:38-93，中英双语文案，CJK 字体存在时用中文）。
- 鼠标命中区 `self._hits` 由各 render 写入（车库已有先例）；本次不改 handle_event。

## Proposed Changes（全部在 `game/core.py`）

### 0. `_TEXTS` 新增键（中英）
- `"hud_left"`：剩余 / LEFT
- `"zone_card"`：安全区 / SAFE ZONE
- `"skill_name_piercing"`：穿甲 / APG；`"skill_name_dash"`：疾冲 / DASH；`"skill_name_shockwave"`：冲击波 / SHOCK
- `"end_rank"`：排名 / RANK；`"end_you"`：你 / YOU；`"end_alive"`：存活 / ALIVE；`"end_dead"`：淘汰 / OUT
- `"end_again"`：再来一局(Enter) / AGAIN(ENTER)；`"end_back"`：返回(Esc) / BACK(ESC)

### 1. 主菜单 `_render_start` 重排（线框：顶栏 + 中央卡片 + 按钮列）
- 顶栏 y=10..38：左 = 16px 坦克 icon（复用 `_icon`）+ "AI 坦克大战"(18px)；右 = "人数 ◀ N ▶"（`_render_config_count` 的渲染逻辑搬到顶栏右侧，`mode_index==ROW_NUM` 时高亮）。
- 原大标题(40px)与 tagline 删除（游戏名进顶栏）；`start_notice` 分支与 garage/settings 子视图分支保持不变。
- 中央坦克卡片（面板约 `(108, 64, 200, 150)`）：`<` `>` 三角 + 64px 坦克大图 + 型号名（使用中标注）——视觉复用车库样式；此即 `ROW_TANK_CONFIG` 焦点态（选中时面板描边黄）。`_render_config_tank` 原行式渲染删除，命中区 `self._hits` 按新坐标写入（左/右箭头各 24x24、卡片整体）。
- 按钮列（4 个 `_menu_button`，y 从约 240 起，行高 32）：对战模式 / 训练曲线 / 坦克仓库 / 设置（settings 入口按钮补齐顶栏下布局；`mode_index` 顺序与 handle_event 现有语义保持一致，仅坐标变化）。
- 底部 `hint_controls`/`hint_ai` 提示行保留（y≈424/446 不动）。

### 2. 设置页 `_render_settings`
- 统一加 `_panel` 卡片（标题页进入时也加，与暂停进入一致），标题"设置"居中于卡片顶部。
- 3 行（音乐/音效/返回）保持行式布局与现有交互，仅垂直居中到卡片内。

### 3. 结算页 `_render_end` 重排（线框：左战绩卡 + 中排名表 + 底部按钮）
- 先 `_render_overlay` 压暗战场（现有惯例）。
- 左卡片（约 `(24, 120, 170, 150)`，`T("end_again")` 用面板）：标题=胜负（win/lose）+ 失败原因；内容=分数、击杀、用时（现有数据，逐行 16px）。
- 中卡片"排名"（约 `(206, 120, 186, 170)`）：表头 名次/标识/状态；行 = `self.player`（标识"你"，黄）+ `versus_foes`（tag A/B/C，红）；排序：存活在前按 hp 降序，淘汰在后按原 tag 序；最多 4 行。
- 底部两个按钮框（居中横排）：`再来一局(Enter)`、`返回(Esc)` 描边按钮样式；输入逻辑不变（仅视觉，不写新按键处理）。

### 4. 对局 HUD（`_render_hud` + `_render_overlays` + 新 `_render_skill_ring`）
- 顶栏：左侧 icon+数字前加"剩余"标签；中间分数不动；生命格/弹匣点不动；**右端 ZONE 文本移除**。
- 左中安全区卡（约 `(6, HUD_HEIGHT+8, 92, 44)` 半透明面板）：`安全区` + `ZONE Xs`（或 ZONE MAX），红色倒计时文本。
- `_render_overlays`：公告从"HUD 下方居中"改为**右上角框**（最多 2 条，右对齐 x=SCREEN_WIDTH-8，y=HUD_HEIGHT+6 起，黑底胶囊改右对齐）；击杀播报挪到公告之下（y 顺延）。
- 新增 `_render_skill_ring(screen)`，在 `_render_field` 末尾调用（玩家存活时）：
  - 位置：右下角圆心 `(S.SCREEN_WIDTH-30, S.SCREEN_HEIGHT-30)`，半径 16。
  - 圆环进度（`pygame.draw.arc` 或分段线）：蓄力中=`charge_frames/charge_frames_max` 黄色弧，满变红；非蓄力且 `fire_cooldown>0`=冷却比例灰弧；否则满环绿（可蓄力）。
  - 中心 12px 文字 = 技能缩写（按 `charge_skill` 取 `skill_name_*`）。

## Assumptions & Decisions
- 不做：名字输入、头像、金币、真排行榜数据、小地图、操作说明页、改键位页、结算页按钮的鼠标点击。
- 排名表为结算时刻状态派生（存活>淘汰，存活间按 hp），不引入死亡顺序记录。
- 头顶蓄力条保留（战斗中跟手），右下圆环是全局技能状态指示。
- 键盘导航/车库/暂停页不动。

## Verification
无头冒烟脚本（跑完即删）：SDL dummy 下分别渲染
1. 标题页（主菜单新布局）、设置子视图、车库子视图（确认未破坏）截图；
2. 构造 STATE_LOSE 结算页截图（含排名表 4 行）；
3. 对局页截图：公告+击杀播报塞入数据、蓄力中状态，确认 HUD 新布局与右下圆环；
逐张目检后 `python main.py` 人工过一遍 4 个界面。
