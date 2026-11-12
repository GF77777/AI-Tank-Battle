"""代码绘制像素精灵：字符串像素矩阵 -> pygame.Surface，零外部素材，FC 复古风。

可选贴皮：assets/tanks/{scout|standard|heavy|enemy}.png（28x28、朝上、透明底）
存在时优先使用，缺失回退代码矩阵。"""

import os

import pygame

from . import settings as S

_SKIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "tanks")
_TILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "tiles")


# ---------------- 像素矩阵（14x14 坦克 / 16x16 地形 / 14x14 特效） ----------------

# 坦克（朝上），8 通道：B=车身主色 D=暗部描边 H=高光 A=装饰 T=履带 W=负重轮亮纹 L=炮管 .=透明
# 轻骑：窄车身（履带 x2-3/x10-11）+ 细炮管 + 炮塔科技蓝条（A 行）
_TANK_SCOUT = [
    "......LL......",
    "......LL......",
    "....DDDDDD....",
    "..TTDHHHHDTT..",
    "..WTDAAAADTW..",
    "..TWDBHHBDWT..",
    "..WTDBBBBDWT..",
    "..TWDBBBBDWT..",
    "..WTDBBBBDWT..",
    "..TWDBBBBDWT..",
    "..TTDBBBBDTT..",
    "....DDDDDD....",
    ".....D..D.....",
    "..............",
]

# 标准：同骨架，车体中部红条纹（A 行 r7）+ 车尾天线（r13 x1）
_TANK_STANDARD = [
    "......LL......",
    "......LL......",
    "....DDDDDD....",
    "..TTDHHHHDTT..",
    "..WTDBHHBDWT..",
    "..TWDBBBBDWT..",
    "..WTDBBBBDWT..",
    "..TWDAAAADWT..",
    "..WTDBBBBDWT..",
    "..TWDBBBBDWT..",
    "..TTDBBBBDTT..",
    "....DDDDDD....",
    ".....D..D.....",
    ".L............",
]

# 重装：加宽车身（履带 x1-2/x11-12，车身 8 宽）+ 炮口制退器 + 铆钉点阵（A 散布）
_TANK_HEAVY = [
    ".....LLLL.....",
    "......LL......",
    "......LL......",
    ".TTDDDDDDDDTT.",
    ".WTDHHHHHHDTW.",
    ".TWDBABBABDWT.",
    ".WTDBBBBBBDTW.",
    ".TWDBABBABDWT.",
    ".WTDBBBBBBDTW.",
    ".TWDBBBBBBDWT.",
    "..TTDDDDDDTT..",
    "....DDDDDD....",
    "....D....D....",
    "..............",
]

for _t in (_TANK_SCOUT, _TANK_STANDARD, _TANK_HEAVY):
    assert len(_t) == 14 and all(len(r) == 14 for r in _t), "tank sprite must be 14x14"

# 砖墙（16x16），H=砖面上缘高光，B=砖面，m=砖缝
_BRICK = [
    "mmmmmmmmmmmmmmmm",
    "mHHHmHHHmHHHmHHH",
    "mBBBmBBBmBBBmBBB",
    "mmmmmmmmmmmmmmmm",
    "mHmHHHmHHHmHHHmH",
    "mBmBBBmBBBmBBBmB",
    "mmmmmmmmmmmmmmmm",
    "mHHHmHHHmHHHmHHH",
    "mBBBmBBBmBBBmBBB",
    "mmmmmmmmmmmmmmmm",
    "mHmHHHmHHHmHHHmH",
    "mBmBBBmBBBmBBBmB",
    "mmmmmmmmmmmmmmmm",
    "mHHHmHHHmHHHmHHH",
    "mBBBmBBBmBBBmBBB",
    "mmmmmmmmmmmmmmmm",
]

# 钢板（16x16），D=暗边，L=亮面，o=铆钉
_STEEL = [
    "DDDDDDDDDDDDDDDD",
    "DhhhhhhhhhhhhhhD",
    "DLoLLLLLLLLLLoLD",
    "DLLLLLLLLLLLLLLD",
    "DLLLLLDDDDLLLLLD",
    "DLLLLLDDDDLLLLLD",
    "DLLLLLLLLLLLLLLD",
    "DLLLLLLLLLLLLLLD",
    "DLLLLLLLLLLLLLLD",
    "DLLLLLLLLLLLLLLD",
    "DLLLLLDDDDLLLLLD",
    "DLLLLLDDDDLLLLLD",
    "DLLLLLLLLLLLLLLD",
    "DLoLLLLLLLLLLoLD",
    "DLLLLLLLLLLLLLLD",
    "DDDDDDDDDDDDDDDD",
]

# 河流（16x16 双帧），W=水色，w=波纹，D=深水点；B 帧波纹相位右移 2px
_RIVER = [
    "WWWWWWWWWWWWWWWW",
    "WWWwwWWWWWwwWWWW",
    "WWwwWWWWWwwWWWWW",
    "WwwWWWWWwwWWWWWW",
    "WWWWWWWWWWWWWWWW",
    "WWWWDWWWWWDWWWWW",
    "WWWWwwWWWWWwwWWW",
    "WWWwwWWWWWwwWWWW",
    "WWwwWWWWWwwWWWWW",
    "WWWWWWWWWWWWWWWW",
    "WDWWWWWWWDWWWWWW",
    "WWwwWWWWWwwWWWWW",
    "WwwWWWWWwwWWWWWW",
    "WWWWWWWWWWWWWWWW",
    "WWWWWDWWWDWWWWWW",
    "WWWWWWWWWWWWWWWW",
]
_RIVER_B = [
    "WWWWWWWWWWWWWWWW",
    "WWWWWwwWWWWwwWWW",
    "WWWWwwWWWWWwwWWW",
    "WWWwwWWWWWwwWWWW",
    "WWWWWWWWWWWWWWWW",
    "WWDWWWWWDWWWWWWW",
    "WWWWWWwwWWWWWwwW",
    "WWWWWwwWWWWwwWWW",
    "WWWWwwWWWWWwwWWW",
    "WWWWWWWWWWWWWWWW",
    "WWWWWDWWWWWDWWWW",
    "WWWWwwWWWWWwwWWW",
    "WWWwwWWWWWwwWWWW",
    "WWWWWWWWWWWWWWWW",
    "WDWWWDWWWWWWWWWW",
    "WWWWWWWWWWWWWWWW",
]

# 森林（16x16），G=深绿底，g=浅绿树冠簇，d=暗缝（渲染时半透明覆盖在坦克上层）
_FOREST = [
    "GGGGGGGGGGGGGGGG",
    "GGGggGGGGGggGGGG",
    "GGggggGGGggggGGG",
    "GGgdggGGGggdggGG",
    "GGGggGGGGGgggGGG",
    "GGGGGGGdGGGGGGGG",
    "GGGGGGGGGGgGGGGG",
    "GggGGGGGGGgggGGG",
    "GgggGGGGGGggggGG",
    "GggdGGGdGGggdgGG",
    "GGgGGGGGGGGggGGG",
    "GGGGGGGGGGGGGGGG",
    "GGGGGggGGGGGggGG",
    "GGGGggggGGGggggG",
    "GGGGggdgGGGggdgg",
    "GGGGGggGGGGGggGG",
]

# 基地老鹰（16x16），K=金色，k=暗金描边
_BASE = [
    "................",
    "......kk........",
    ".....kKKk.......",
    "....kKKKKk......",
    "...kK.KKKK.Kk...",
    "..kKKK.KK.KKKk..",
    "..kKKKKKKKKKKk..",
    "...kKKKKKKKk....",
    "....kKKKKKk.....",
    ".....kK..Kk.....",
    "....kKK..KKk....",
    "...kKK....KKk...",
    "..kKKK....KKKk..",
    "..kKKKKKKKKKKk..",
    "................",
    "................",
]

# 空地地面（16x16），x=近黑底，n=稀疏噪点（只为去掉死黑，不抢实体视觉）
_GROUND = [
    "xxxxxxxxxxxxxxxx",
    "xxxxxxxxxxxxxxxx",
    "xxxnxxxxxxxxxxxx",
    "xxxxxxxxxxnxxxxx",
    "xxxxxxxxxxxxxxxx",
    "xxnxxxxxxnxxxxxx",
    "xxxxxxxxxxxxxxxx",
    "xxxxxxnxxxxxxxxx",
    "xxxxxxxxxxxxxxxx",
    "xnxxxxxxxxxxnxxx",
    "xxxxxxxxxxxxxxxx",
    "xxxxxnxxxxxxxxxx",
    "xxxxxxxxxxxxxxxx",
    "xxxxxxxxxxxxnxxx",
    "xxnxxxxxxxxxxxxx",
    "xxxxxxxxxxxxxxxx",
]

# 基地被毁后的废墟（16x16），R=暗红
_BASE_DEAD = [
    "................",
    "..R....R.....R..",
    "...R..R.R...R...",
    "....RR...R.R....",
    ".....R.RR.R.....",
    "..R..RRR..R..R..",
    "...RRRRRRR.R....",
    "....RR.RRRR.....",
    "..R.RRRR.RR..R..",
    "....RR..RRR.R...",
    ".....R...RR.....",
    "..R....R....R...",
    "................",
    "................",
    "................",
    "................",
]

# 子弹（3x3），W=白，O=橙心
_BULLET = [
    "WWW",
    "WOW",
    "WWW",
]

# 枪口火焰（朝上）：白芯 + 暖黄外缘，旋转生成四方向
_MUZZLE = [
    "..Y.",
    ".YWY",
    "YWWY",
    ".YY.",
]
_MUZZLE_PIERCING = [
    "..Y..",
    ".YWY.",
    "YWWWY",
    ".YWY.",
    "..Y..",
]

# 爆炸 3 帧（16x16）：O=橙，Y=黄，W=白热，R=暗红余烬
_EXPLOSION_1 = [
    "................",
    "................",
    "......O..O......",
    "......OO........",
    "..O..OOOO..O....",
    "....OOOOOO......",
    "....OOOOOO......",
    "..O.OOOOOO.O....",
    ".....OOOO.......",
    "......O.........",
    "................",
    "................",
    "................",
    "................",
]
_EXPLOSION_2 = [
    "....O....O......",
    "..O..O..O..O....",
    "...OOOOOOOO.....",
    ".OOOOOYYOOOOO...",
    "..OOOYYYYOOO....",
    ".OOOYYYYYYOO....",
    "..OOYYWYYOO.....",
    ".OOOYYYYYYOO....",
    "..OOOYYYYOOO....",
    ".OOOOOYYOOOOO...",
    "...OOOOOOOO.....",
    "..O..O..O..O....",
    "....O....O......",
    "................",
]
_EXPLOSION_3 = [
    "................",
    "..R...R....R....",
    "...R......R.....",
    "......RR........",
    "..R..RRRR..R....",
    "....RRRRRR......",
    "....RRRRR.......",
    "....RRRRR..R....",
    "..R...RRR.......",
    "....R.R...R.....",
    "...R.....R......",
    "................",
    "................",
    "................",
]


def _make_surface(pattern, palette, scale):
    """按像素矩阵生成 Surface（逐行校验长度，防止手误）。"""
    width = len(pattern[0])
    for row in pattern:
        assert len(row) == width, f"sprite row length mismatch: {row!r}"
    surf = pygame.Surface((width * scale, len(pattern) * scale), pygame.SRCALPHA)
    for y, row in enumerate(pattern):
        for x, ch in enumerate(row):
            color = palette.get(ch)
            if color is not None:
                pygame.draw.rect(surf, color, (x * scale, y * scale, scale, scale))
    return surf


# 调色板
_PAL_PLAYER = {"B": (212, 178, 110), "D": (120, 95, 50), "H": (245, 225, 170),
               "A": (200, 60, 50), "T": (70, 58, 40), "W": (140, 115, 70),
               "L": (60, 50, 35)}                          # 标准：沙漠黄 + 红条纹
_PAL_PLAYER_SCOUT = {"B": (64, 80, 106), "D": (26, 34, 46), "H": (150, 200, 235),
                     "A": (70, 180, 255), "T": (32, 38, 50), "W": (78, 94, 118),
                     "L": (30, 38, 50)}                     # 轻骑：蓝黑 + 科技蓝条
_PAL_PLAYER_HEAVY = {"B": (110, 118, 88), "D": (55, 60, 42), "H": (170, 178, 140),
                     "A": (70, 74, 55), "T": (45, 48, 38), "W": (95, 100, 75),
                     "L": (40, 44, 32)}                     # 重装：军绿 + 铆钉
_PAL_BRICK = {"B": (176, 74, 40), "H": (210, 110, 60), "m": (80, 36, 20)}
_PAL_STEEL = {"D": (70, 70, 80), "L": (170, 175, 185), "o": (40, 40, 48),
              "h": (200, 205, 215)}
_PAL_RIVER = {"W": (40, 90, 200), "w": (120, 170, 240), "D": (24, 60, 150)}
_PAL_FOREST = {"G": (16, 110, 32), "g": (52, 170, 60), "d": (8, 70, 20)}
_PAL_BASE = {"K": (230, 200, 110), "k": (120, 90, 40)}
_PAL_BASE_DEAD = {"R": (110, 40, 30)}
_PAL_GROUND = {"x": (14, 14, 18), "n": (22, 22, 28)}   # 空地：近黑底 + 稀疏噪点
_PAL_BULLET = {"W": (240, 240, 240), "O": (250, 160, 60)}
_PAL_BULLET_PIERCE = {"W": (250, 220, 90), "O": (255, 255, 255)}   # 穿甲弹：亮黄
_PAL_EXP_1 = {"O": (240, 140, 40)}
_PAL_EXP_2 = {"O": (240, 140, 40), "Y": (250, 220, 90), "W": (255, 255, 255)}
_PAL_EXP_3 = {"R": (140, 60, 40)}
_PAL_MUZZLE = {"Y": (250, 220, 90), "W": (255, 255, 255)}

# 战斗粒子共用的少量 FC 调色
FX_BRICK = (176, 74, 40)
FX_BRICK_LIGHT = (210, 110, 60)
FX_STEEL = (190, 195, 205)
FX_DASH = (70, 180, 255)
FX_ZONE = (220, 50, 40)

# ---------------- 对战道具（16x16） ----------------

# 加血：白底红十字
_ITEM_HEAL = [
    "................",
    "..WWWWWWWWWWWW..",
    "..WWWWWWWWWWWW..",
    "..WWWWRRRRWWWW..",
    "..WWWWRRRRWWWW..",
    "..WWRRRRRRRRWW..",
    "..WWRRRRRRRRWW..",
    "..WWWWRRRRWWWW..",
    "..WWWWRRRRWWWW..",
    "..WWWWRRRRWWWW..",
    "..WWWWWWWWWWWW..",
    "..WWWWWWWWWWWW..",
    "................",
    "................",
    "................",
    "................",
]

# 火力：黄星 + 橙焰尾
_ITEM_FIRE = [
    "................",
    ".......YY.......",
    ".......YY.......",
    "...Y...YY...Y...",
    "....YY.YY.YY....",
    "....YYYYYYYY....",
    "..YYYYYYYYYYYY..",
    "....YYYYYYYY....",
    "....YYYOOYYY....",
    "...YYYOOOOYY....",
    "...YY..OO..YY...",
    "........OO......",
    "........OO......",
    "................",
    "................",
    "................",
]

# 护盾：蓝盾 + 浅蓝芯
_ITEM_SHIELD = [
    "................",
    "..BBBBBBBBBBBB..",
    "..BBBBBBBBBBBB..",
    "..BBWWWWWWWWBB..",
    "..BBWWWWWWWWBB..",
    "..BBWWWWWWWWBB..",
    "..BBWWWWWWWWBB..",
    "..BBBWWWWWWBBB..",
    "..BBBWWWWWWBBB..",
    "..BBBBWWWWBBBB..",
    "..BBBBBWWBBBBB..",
    "..BBBBBBWBBBBB..",
    "..BBBBBBBBBBBB..",
    "................",
    "................",
    "................",
]

# 地雷：深灰圆盘 + 红点引信
_ITEM_MINE = [
    "................",
    ".....DDDDDD.....",
    "...DDDDDDDDDD...",
    "..DDDDDDDDDDDD..",
    "..DDDddddddDDD..",
    "..DDddddddddDD..",
    "..DDdddRRdddDD..",
    "..DDdddRRdddDD..",
    "..DDddddddddDD..",
    "..DDDddddddDDD..",
    "..DDDDDDDDDDDD..",
    "...DDDDDDDDDD...",
    ".....DDDDDD.....",
    "................",
    "................",
    "................",
]

# 零件余额：16x16 像素装甲，透明铆钉孔与加强筋
_PARTS_ICON = [
    "................",
    "...YYYYYYYYYY...",
    "...YYYYYYYYYY...",
    "...YYYYYYYYYY...",
    ".YYY..YYYY..YYY.",
    ".YYY..YYYY..YYY.",
    ".YYYYYY..YYYYYY.",
    ".YYYYYY..YYYYYY.",
    ".YYYYYY..YYYYYY.",
    ".YYY..Y..Y..YYY.",
    ".YYY..Y..Y..YYY.",
    ".YYYYYY..YYYYYY.",
    ".....YYYYYY.....",
    ".....YYYYYY.....",
    ".....YYYYYY.....",
    "................",
]

_PAL_ITEM_HEAL = {"W": (240, 240, 240), "R": (220, 50, 40)}
_PAL_ITEM_FIRE = {"Y": (250, 220, 90), "O": (240, 140, 40)}
_PAL_ITEM_SHIELD = {"B": (52, 138, 245), "W": (168, 216, 255)}
_PAL_ITEM_MINE = {"D": (70, 70, 80), "d": (40, 40, 48), "R": (220, 50, 40)}
_PAL_PARTS = {"Y": S.YELLOW}


def _make_pickup_icon(kind):
    """道具图标：12x12 矢量绘制后放大 2 倍，保持像素块风格。"""
    surf = pygame.Surface((12, 12), pygame.SRCALPHA)
    if kind == "shield":
        pygame.draw.polygon(surf, (52, 138, 245), [(6, 0), (11, 2), (11, 7), (6, 11), (1, 7), (1, 2)])
        pygame.draw.polygon(surf, (168, 216, 255), [(6, 2), (9, 3), (9, 7), (6, 9), (3, 7), (3, 3)])
    elif kind == "power":
        pygame.draw.polygon(surf, (250, 205, 60), [(6, 0), (9, 5), (7, 5), (8, 12), (3, 6), (5, 6)])
        pygame.draw.polygon(surf, (255, 245, 180), [(6, 2), (7, 5), (6, 6), (5, 5)])
    else:  # clear
        pygame.draw.polygon(surf, (238, 84, 60),
                            [(6, 0), (8, 4), (12, 6), (8, 8), (6, 12), (4, 8), (0, 6), (4, 4)])
        pygame.draw.circle(surf, (255, 220, 200), (6, 6), 2)
    return pygame.transform.scale(surf, (24, 24))


def _load_skin(name):
    """加载原始朝上贴皮；战斗与营地预览再分别按需要缩放。"""
    path = os.path.join(_SKIN_DIR, f"{name}.png")
    if not os.path.isfile(path):
        return None
    img = pygame.image.load(path)
    if pygame.display.get_surface() is not None:
        img = img.convert_alpha()
    return img


def _direction_set(up):
    """由朝上精灵旋转生成四方向表。"""
    return {
        S.UP: up,
        S.RIGHT: pygame.transform.rotate(up, -90),
        S.DOWN: pygame.transform.rotate(up, 180),
        S.LEFT: pygame.transform.rotate(up, 90),
    }


def _tank_set_from_surface(up):
    """由朝上 surface 旋转生成四方向坦克精灵表（先确保尺寸 = TANK_SIZE）。"""
    return _direction_set(_fit(up, S.TANK_SIZE))


def _tank_set(palette, template):
    """由朝上模板生成四方向坦克精灵表。"""
    return _tank_set_from_surface(_make_surface(template, palette, 2))


def _fit(surf, size):
    """生成后缩放到目标尺寸（地形 32->24，坦克 28->21 等），尺寸已匹配则原样返回。"""
    return surf if surf.get_size() == (size, size) else pygame.transform.scale(surf, (size, size))


def _load_tile(filename):
    """加载 assets/tiles 中的透明 PNG，最近邻缩到一格；缺图时回退代码矩阵。"""
    path = os.path.join(_TILE_DIR, filename)
    if not os.path.isfile(path):
        return None
    img = pygame.image.load(path)
    if pygame.display.get_surface() is not None:
        img = img.convert_alpha()
    return _fit(img, S.TILE_SIZE)


class Sprites:
    """精灵资源单例：pygame.init() 之后通过 get() 获取。"""

    def __init__(self):
        # 原图供营地清晰预览；战斗精灵仍统一适配到 TANK_SIZE。
        self.garage_tanks = {}
        self.player_tanks = {}
        for name, palette, template in (
            ("scout", _PAL_PLAYER_SCOUT, _TANK_SCOUT),
            ("standard", _PAL_PLAYER, _TANK_STANDARD),
            ("heavy", _PAL_PLAYER_HEAVY, _TANK_HEAVY),
        ):
            source = _load_skin(name)
            if source is None:
                source = _make_surface(template, palette, 2)
            self.garage_tanks[name] = source
            self.player_tanks[name] = _tank_set_from_surface(source)
        self.player_tank = self.player_tanks["standard"]   # 兼容引用（HUD 图标等默认标准）
        self.pickup_icons = {
            "shield": _make_pickup_icon("shield"),
            "power": _make_pickup_icon("power"),
            "clear": _make_pickup_icon("clear"),
        }
        self.parts_icon = _make_surface(_PARTS_ICON, _PAL_PARTS, 1)
        # 对战道具 16x16 -> 24x24（与 Item.SIZE 一致）
        self.items = {
            "heal": _fit(_make_surface(_ITEM_HEAL, _PAL_ITEM_HEAL, 1), S.TILE_SIZE),
            "fire": _fit(_make_surface(_ITEM_FIRE, _PAL_ITEM_FIRE, 1), S.TILE_SIZE),
            "shield": _fit(_make_surface(_ITEM_SHIELD, _PAL_ITEM_SHIELD, 1), S.TILE_SIZE),
            "mine": _fit(_make_surface(_ITEM_MINE, _PAL_ITEM_MINE, 1), S.TILE_SIZE),
        }
        # 地形：优先使用透明 PNG（64x64 -> 24x24），缺图回退代码矩阵
        brick = _load_tile("crate_17.png")
        steel = _load_tile("crate_01.png")
        forest_green = _load_tile("treeGreen_large.png")
        forest_brown = _load_tile("treeBrown_large.png")
        self.tiles = {
            S.BRICK: brick if brick is not None else _fit(_make_surface(_BRICK, _PAL_BRICK, 2), S.TILE_SIZE),
            S.STEEL: steel if steel is not None else _fit(_make_surface(_STEEL, _PAL_STEEL, 2), S.TILE_SIZE),
            S.RIVER: _fit(_make_surface(_RIVER, _PAL_RIVER, 2), S.TILE_SIZE),
            S.BASE: _fit(_make_surface(_BASE, _PAL_BASE, 2), S.TILE_SIZE),
        }
        self.forest = forest_green if forest_green is not None else _fit(
            _make_surface(_FOREST, _PAL_FOREST, 2), S.TILE_SIZE)
        self.forest_brown = forest_brown if forest_brown is not None else self.forest
        # 草丛整体压暗约 18%，保留贴图透明边缘与进草草环的亮度。
        forests = (self.forest,) if self.forest_brown is self.forest else (self.forest, self.forest_brown)
        for forest in forests:
            shade = pygame.Surface(forest.get_size(), pygame.SRCALPHA)
            shade.fill((210, 210, 210, 255))
            forest.blit(shade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            forest.set_alpha(255)
        self.base_dead = _fit(_make_surface(_BASE_DEAD, _PAL_BASE_DEAD, 2), S.TILE_SIZE)
        self.river_b = _fit(_make_surface(_RIVER_B, _PAL_RIVER, 2), S.TILE_SIZE)   # 河流第二帧（波纹错相）
        # 三张地图各自的空地地板：预拼整张地图，渲染时每帧 1 次 blit
        ground_fallback = _fit(_make_surface(_GROUND, _PAL_GROUND, 2), S.TILE_SIZE)
        self.grounds = []
        for floor_name in ("floor_map1.png", "floor_map2.png", "floor_map3.png"):
            floor_tile = _load_tile(floor_name)
            if floor_tile is None:
                floor_tile = ground_fallback
            ground = pygame.Surface((S.MAP_COLS * S.TILE_SIZE,
                                     S.MAP_ROWS * S.TILE_SIZE))
            for _r in range(S.MAP_ROWS):
                for _c in range(S.MAP_COLS):
                    ground.blit(floor_tile, (_c * S.TILE_SIZE, _r * S.TILE_SIZE))
            self.grounds.append(ground)
        self.ground = self.grounds[0]  # 兼容原引用

        self.bullet = _make_surface(_BULLET, _PAL_BULLET, 2)       # 6x6
        self.bullet_piercing = pygame.transform.scale(
            _make_surface(_BULLET, _PAL_BULLET_PIERCE, 2), (8, 8))  # 穿甲弹 8x8
        # 无敌护盾环：29x29、四档透明度，只让环体呼吸，不遮挡坦克。
        self.invincible_frames = []
        for alpha in (90, 135, 195, 135):
            frame = pygame.Surface((29, 29), pygame.SRCALPHA)
            pygame.draw.circle(frame, (*FX_DASH, alpha), (14, 14), 13, 1)
            highlight = (168, 216, 255, min(255, alpha + 45))
            for point in ((14, 1), (27, 14), (14, 27), (1, 14)):
                frame.set_at(point, highlight)
            self.invincible_frames.append(frame)
        self.muzzle = _direction_set(_make_surface(_MUZZLE, _PAL_MUZZLE, 2))          # 8x8
        self.muzzle_piercing = _direction_set(
            _make_surface(_MUZZLE_PIERCING, _PAL_MUZZLE, 2))                          # 10x10
        explosion_frames = (
            _make_surface(_EXPLOSION_1, _PAL_EXP_1, 2),
            _make_surface(_EXPLOSION_2, _PAL_EXP_2, 2),
            _make_surface(_EXPLOSION_3, _PAL_EXP_3, 2),
        )
        self.explosions = [_fit(frame, 14) for frame in explosion_frames]       # 普通命中 14x14
        self.kill_explosions = [_fit(frame, 30) for frame in explosion_frames]  # 淘汰 30x30


_INSTANCE = None


def get():
    """获取精灵单例（需要 pygame 已初始化）。"""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = Sprites()
    return _INSTANCE
