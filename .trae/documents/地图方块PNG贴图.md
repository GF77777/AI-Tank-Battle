# 地图方块 PNG 贴图计划

## Summary
将四张 64×64 透明 PNG 接入现有地形渲染：棕色箱子替换砖墙、灰色箱子替换钢板，绿色与棕色树木按固定规则混合替换森林。仅改变视觉，不新增地形编码，不改变地图布局、碰撞、破坏、森林遮挡或 AI 输入。

## Current State Analysis
- [sprites.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/sprites.py#L489-L531) 在 `Sprites.__init__()` 中用代码矩阵生成地形，再缩放到 24×24；已有坦克 PNG 加载与缺失回退模式可复用。
- [core.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/core.py#L1992-L2017) 通过 `sprites.tiles` 绘制砖墙/钢板，通过单一 `sprites.forest` 绘制所有森林格；森林遮挡顺序已经正确处理。
- [level.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/level.py#L16-L87) 的三张地图只保存 `B/S/R/F` 等地形语义，无需为换贴图修改。
- 四张素材均已确认是 64×64、带透明通道的 PNG；现有 1.5 倍摄像机与 2 倍窗口缩放会自动应用于新贴图。

## Proposed Changes
### 1. 将素材纳入项目资源
目标目录：`assets/tiles/`
- 复制 `C:\Users\CGF\Desktop\crate_17.png` → `assets/tiles/crate_17.png`，用于 `S.BRICK`。
- 复制 `C:\Users\CGF\Desktop\crate_01.png` → `assets/tiles/crate_01.png`，用于 `S.STEEL`。
- 复制 `C:\Users\CGF\Desktop\treeGreen_large.png` → `assets/tiles/treeGreen_large.png`，作为绿色森林。
- 复制 `C:\Users\CGF\Desktop\treeBrown_large.png` → `assets/tiles/treeBrown_large.png`，作为棕色森林。
- 保留原上传文件，不修改源素材。

### 2. 增加地形 PNG 加载与回退
文件：[sprites.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/sprites.py#L452-L523)
- 新增 `_TILE_DIR`，指向项目内 `assets/tiles`。
- 参照 `_load_skin()` 增加地形加载函数：文件存在时加载 alpha；有显示表面时调用 `convert_alpha()`；用最近邻 `pygame.transform.scale` 从 64×64 缩到 `S.TILE_SIZE=24`；文件缺失时返回 `None`。
- 在 `Sprites.__init__()` 中让砖墙、钢板优先使用对应 PNG，缺失时回退到原有 `_BRICK/_STEEL` 矩阵。
- 保留 `self.forest` 作为绿色森林 Surface，新增 `self.forest_brown`；两者优先使用 PNG，缺失时分别回退到原森林矩阵或绿色森林。
- 保持透明边缘和 `set_alpha(255)` 的现有森林遮挡方式，不把透明 PNG 转为不透明方块。
- 河流、基地、地面、道具和坦克资源不变。

### 3. 在森林绘制时固定混合两种树木
文件：[core.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/core.py#L1992-L1997)
- 仅修改 `draw_forest()` 的贴图选择。
- 使用确定性格坐标哈希 `(r * 31 + c * 17) % 4`：结果 0、1 使用 `forest_brown`，结果 2、3 使用 `forest`。
- 因此绿棕约为 1:1，同一格子跨帧稳定、不闪烁；不增加随机状态，不影响地图 C4 对称的游戏规则。
- 保留玩家位于森林内/外时不同的绘制顺序，以及战争迷雾、小地图和摄像机逻辑。

### 4. 明确不改动的文件与行为
- 不修改 `settings.py` 的地形编码和阻挡规则。
- 不修改 `level.py` 的三张地图模板。
- 不修改 `entities.py`、`env.py`、训练/评估链路及 384 维状态输入。
- 小地图继续使用简化色块，不在 4px 格子中叠加 PNG。

## Assumptions & Decisions
- 用户已确认森林采用绿棕混合，而非单一颜色或按地图区分。
- 贴图只替换现有地形外观，不增加箱子、枯树等新碰撞类型。
- 保留缺图回退，避免资源路径问题导致游戏无法启动。

## Verification
1. 运行 `python -m py_compile game/sprites.py game/core.py`。
2. 无头加载 `Sprites`：确认四种资源均为 24×24、透明角像素仍透明，绿/棕森林为不同 Surface。
3. 分别加载三张预设地图并渲染：确认砖墙/钢板/森林使用新贴图，绿棕混合且同一帧重复渲染结果一致。
4. 检查森林内/外的坦克遮挡、砖墙被子弹破坏、钢板不可破坏，确认渲染前后 `game.grid` 完全不变。
5. 保存中央视野与边缘视野截图进行视觉检查，确认 1.5 倍摄像机下贴图清晰、对齐格子、透明边缘正常。
6. 运行 RL 环境冒烟测试，确认 `STATE_DIM=384` 与一步 `reset/step` 正常。
