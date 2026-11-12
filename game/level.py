"""对战竞技场地图定义与加载。'.'=空 B=砖墙 S=钢板 R=河流 F=森林。

3 张 17x17 四向旋转对称（C4）预设图，每局随机抽一张。布局参考手绘草图：
折角回廊 / 十字阵 / 放射阵；拐角口布草丛做遮挡点。
无外墙设计：最外圈为空地，坦克/子弹由代码边界拦截；出生角即正四角。
统一设计原则（围绕毒圈收缩 + 视野迷雾）：
- 出生角 (0,0)/(0,16)/(16,0)/(16,16) 为空地，(0,8) 系钢板掩体打断同行同列直线；
- 中心开阔（毒圈终点决斗场）；
- C4 对称：grid[r][c] == grid[c][16-r]，load 时自动校验。
"""

import random

from . import settings as S

_CHAR_TO_TILE = {
    ".": S.EMPTY,
    "B": S.BRICK,
    "S": S.STEEL,
    "R": S.RIVER,
    "F": S.FOREST,
}

# MAP_1「折角回廊」：折角钢墙 + 边中点凸出，拐角口草丛。
MAP_1 = [
    "........S........",
    "....F............",
    "..BB..FF.FF..BB..",
    "..B..SSF.FSS..B..",
    "....SF.....FS..F.",
    "...SF...F...FS...",
    "..FS.........SF..",
    "..FF...F.F...FF..",
    "S....F..B..F....S",
    "..FF...F.F...FF..",
    "..FS.........SF..",
    "...SF...F...FS...",
    ".F..SF.....FS....",
    "..B..SSF.FSS..B..",
    "..BB..FF.FF..BB..",
    "............F....",
    "........S........",
]

# MAP_2「十字阵」：断开式中心十字砖 + 四角散布草丛。
MAP_2 = [
    "........S........",
    "............F....",
    "..BB..FF.FF..BB..",
    "..B.F..F.F..F.B..",
    ".F.F.........F...",
    "........B........",
    "..F...F.B.F...F..",
    "..FF.........FF..",
    "S....BB...BB....S",
    "..FF.........FF..",
    "..F...F.B.F...F..",
    "........B........",
    "...F.........F.F.",
    "..B.F..F.F..F.B..",
    "..BB..FF.FF..BB..",
    "....F............",
    "........S........",
]

# MAP_3「放射阵」：中心砖 + 轴向/斜向放射砖 + 草丛散布。
MAP_3 = [
    "........S........",
    "....F.......F....",
    "..BB.........BB..",
    "..B...........B..",
    ".F.............F.",
    ".....B..B..B.....",
    ".................",
    ".......F.F.......",
    "S....B..B..B....S",
    ".......F.F.......",
    ".................",
    ".....B..B..B.....",
    ".F.............F.",
    "..B...........B..",
    "..BB.........BB..",
    "....F.......F....",
    "........S........",
]

VERSUS_MAPS = [MAP_1, MAP_2, MAP_3]


def _assert_c4_symmetry(template):
    """校验 90° 旋转对称与出生角空地，防手滑改图破坏公平性。"""
    n = S.MAP_ROWS
    for r in range(n):
        for c in range(n):
            assert template[r][c] == template[c][n - 1 - r], f"不对称: ({r},{c})"
    for r, c in [(0, 0), (0, n - 1), (n - 1, 0), (n - 1, n - 1)]:
        assert template[r][c] == ".", f"出生角({r},{c})非空地"


def generate_spawns(grid, n):
    """在地图空地上随机选 n 个互不相邻的出生位（Chebyshev 距离 ≥3）。

    选不足时依次降距 2、1 重试兜底。返回 [(col, row), ...]，长度 n。
    """
    candidates = [(c, r) for r in range(S.MAP_ROWS) for c in range(S.MAP_COLS)
                  if grid[r][c] == S.EMPTY]
    for min_dist in (3, 2, 1):
        pool = candidates[:]
        random.shuffle(pool)
        picked = []
        for pt in pool:
            if all(max(abs(pt[0] - p[0]), abs(pt[1] - p[1])) >= min_dist
                   for p in picked):
                picked.append(pt)
                if len(picked) == n:
                    return picked
    # 极端兜底：空地不足 n 块时直接取前 n 块（实际地图不会发生）
    return candidates[:n]


def load_versus_map(index=0):
    """加载对战竞技场为 grid[row][col]（无基地）。

    index: 0/None=随机抽一张；1-3=指定 VERSUS_MAPS[index-1]。
    """
    template = random.choice(VERSUS_MAPS) if not index else VERSUS_MAPS[index - 1]
    assert len(template) == S.MAP_ROWS, "versus map row count mismatch"
    _assert_c4_symmetry(template)
    grid = []
    for r, row in enumerate(template):
        assert len(row) == S.MAP_COLS, f"versus map row {r} width mismatch"
        grid.append([_CHAR_TO_TILE[ch] for ch in row])
    return grid
