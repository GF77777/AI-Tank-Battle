# 标题界面 UI 重排计划（+ 统一暂停/结算面板语言）

## 1. 背景与问题

用户提供的标题界面真机截图暴露 5 个问题（全部位于 `game/core.py` 渲染层）：

| # | 问题 | 根因（代码位置） |
|---|---|---|
| 1 | 标题界面顶部仍显示 HUD（敌人 10 / 分数 0 / ×3 / 1-1），是"游戏进行中"的噪音信息 | `render()` L596 无条件调 `_render_hud()` |
| 2 | 未选中菜单项（S.GRAY 120,120,120）压在河流/砖墙贴图上几乎不可读 | `_render_start` L751-755：面板 alpha=160 不够 + 灰色太暗 |
| 3 | 底部署名 y=440 在面板（56~386）之外，压在出生点星形/基地上 | `_render_start` L769-770 |
| 4 | 菜单 x=120 左对齐、行高 28，三项宽度不一，视觉松散无"按钮感" | 同上 L755 |
| 5 | 两条提示（y=330 / y=358）与菜单区间距不均，整体垂直节奏乱 | 同上 L765-768 |

## 2. 决策（已与用户确认）

- **范围**：标题界面重排为主；暂停/结算统一同一套面板语言（面板位置、按钮选中条、间距节奏）。
- **菜单风格**：按钮选中条——选中项整条高亮底条 + 黄字 + `> ` 前缀，未选中亮灰；行高 36。
- 不改动任何输入逻辑、状态机、文案 key（`_TEXTS` 不变），纯渲染层调整。
- START 状态隐藏 HUD（标题界面不需要局内数据；结算/暂停保留 HUD 压暗在遮罩下，维持"局内"语境）。

## 3. 改动清单

### 3.1 `game/settings.py` — 新增 1 个颜色常量

```python
LIGHT_GRAY = (176, 176, 176)   # 菜单未选中项（GRAY 太暗，压面板上不可读）
```

### 3.2 `game/core.py` — `render()`（约 L596）

```python
if self.state != STATE_START:
    self._render_hud(screen)
```

### 3.3 `game/core.py` — 新增按钮条工具方法（供标题/暂停复用）

```python
def _menu_button(self, screen, text, y, selected, width=240):
    """按钮式菜单项：选中给底条+黄字+光标，未选中亮灰。返回占用的矩形。"""
    x = (S.SCREEN_WIDTH - width) // 2
    rect = pygame.Rect(x, y, width, 30)
    if selected:
        bar = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        bar.fill((240, 200, 60, 28))            # 黄 11% 透明度底条
        screen.blit(bar, rect.topleft)
        pygame.draw.rect(screen, S.YELLOW, rect, 1)
    img = get_font(20).render(("> " if selected else "") + text, True,
                              S.YELLOW if selected else S.LIGHT_GRAY)
    screen.blit(img, (x + 16, y + (30 - img.get_height()) // 2))
```

（实现时微调：未选中项缩进对齐选中项文字起点，即加 16+前缀宽度偏移。）

### 3.4 `game/core.py` — `_render_start()` 重排

面板改为 `(24, 72, 368, 340)`（y 72~412），footer 收进面板：

```
y= 92   AI 坦克大战               40号 黄 居中
y=150   复古像素坦克大战            14号 灰
y=168   守住基地，击败你训练出来的 AI  14号 灰
y=208   ┌─ 按钮条 240×30 ─┐  闯关模式      ← 行高 36
y=244   │  观战 A I       │
y=280   └─ 训练曲线       ─┘
y=336   上下键 选择   Enter 确认   14号 白
y=364   方向键/WASD 移动 空格射击 Esc 暂停  12号 灰
y=392   Pygame · PyTorch · Double DQN     12号 灰（收进面板）
```

- `start_notice`（观战 AI / 训练曲线提示页）：两行文字居中 y=224 / 256，`hint_back` 用同一 y=336 位置，布局不跳。
- 所有数值在 headless 截图自验时可微调（对齐 8px 网格）。

### 3.5 `game/core.py` — `_render_pause()` 统一

- 面板改 `(24, 140, 368, 260)`（与标题面板同 x/w）。
- 3 个菜单项改用 `_menu_button(..., width=200)`，行高 36，起始 y=224。
- 标题 28 号 y=166；提示 y=362 面板内底部。

### 3.6 `game/core.py` — `_render_end()` 统一

- 仅面板改 `(24, 110, 368, 214)`（同 x/w），内部文字布局不动（结算无菜单，星级行属 M5 不在本次范围）。

### 3.7 `docs/UI设计规范.md` 同步

- 2.2 调色板表新增 `S.LIGHT_GRAY` 一行。
- 第 4 章标题界面布局图与元素表按 3.4 重写（含按钮条规格：240×30、黄 11% 底条 + 1px 黄框、文字 x+16）。
- 第 5 章暂停界面面板坐标更新为 (24,140,368,260)。
- 版本头加 v1.2 变更记录。

### 3.8 `README.md` — 无需改动

本次纯视觉重排，操作与玩法不变。

## 4. 不做（范围控制）

- 不加标题装饰图标/动画/Logo 精灵（保持零外部素材 + 最小改动）。
- 不实现星级结算（M5 内容）。
- 不动 HUD 局内布局、蓄力条、战场渲染。

## 5. 验证

1. **headless 截图自验**（临时脚本，`SDL_VIDEODRIVER=dummy`，输出到临时目录后删除）：
   - START 态渲染 1 帧 → 存 PNG 用 Read 查看：HUD 已隐藏、按钮条、footer 在面板内、文字不溢出。
   - 模拟 `K_DOWN` 切换选中项 → 确认选中条移动、三项宽度一致。
   - `start_notice=MODE_WATCH` 分支 → 提示页布局正常。
   - PAUSED / WIN / LOSE 三态各渲 1 帧 → 面板位置统一、无文字溢出。
2. **回归**：`python evaluate.py --episodes 3 --seed 1` 输出与基线一致（纯渲染改动应逐位不变）。
3. **真机确认**：用户运行 `python main.py` 查看标题/暂停/结算实际效果。
