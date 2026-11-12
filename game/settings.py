"""全局常量配置：尺寸、颜色、速度、规则参数、RL 奖励参数。"""

# ---------- 屏幕与网格 ----------
TILE_SIZE = 24                     # 每格像素
MAP_COLS = 17
MAP_ROWS = 17
HUD_HEIGHT = 48                    # 顶部 HUD 栏高度
SCREEN_WIDTH = TILE_SIZE * MAP_COLS            # 416
SCREEN_HEIGHT = TILE_SIZE * MAP_ROWS + HUD_HEIGHT  # 464
FPS = 60

# ---------- 窗口显示 ----------
SCALE = 2                                        # 逻辑分辨率 -> 窗口的整数放大倍数
CAMERA_ZOOM = 1.5                                # 玩家战场局部放大倍率（不影响世界坐标）
WINDOW_WIDTH = SCREEN_WIDTH * SCALE              # 832
WINDOW_HEIGHT = SCREEN_HEIGHT * SCALE            # 928

# ---------- 颜色 ----------
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (120, 120, 120)
LIGHT_GRAY = (176, 176, 176)   # 菜单未选中项（GRAY 压面板底色上对比度不足）
DARK_GRAY = (60, 60, 60)
RED = (220, 50, 40)
YELLOW = (240, 200, 60)
GREEN = (80, 200, 80)
HUD_BG = (24, 24, 32)
MENU_BG = (24, 32, 43)         # 首页、子页与菜单遮罩的统一墨蓝灰底色
PANEL_BG = (10, 10, 14)        # 界面面板底色（半透明叠加时用）
PANEL_BORDER = (72, 72, 84)    # 面板/卡片统一描边

# ---------- 地形编码 ----------
EMPTY = 0
BRICK = 1     # 砖墙：可被子弹打掉，挡坦克与子弹
STEEL = 2     # 钢板：不可破坏，挡坦克与子弹
RIVER = 3     # 河流：挡坦克，子弹可飞越
FOREST = 4    # 森林：不挡坦克/子弹，遮挡视线（最后渲染）
BASE = 5      # 基地：1 点血，被打中即失败

# 坦克不可通行的地形（基地也视为阻挡）
TANK_BLOCK = (BRICK, STEEL, RIVER, BASE)
# 子弹不可飞越的地形（森林不挡子弹；基地单独判定）
BULLET_BLOCK = (BRICK, STEEL)

# ---------- 方向 ----------
UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3
DIR_VECTORS = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}

# ---------- 键位 ----------
# 默认键位（pygame 常量名字符串，避免 settings 依赖 pygame）；可在设置页修改
DEFAULT_KEYBINDS = {"up": "K_UP", "down": "K_DOWN", "left": "K_LEFT",
                    "right": "K_RIGHT", "fire": "K_j", "skill": "K_k"}
KEYBIND_ORDER = ("up", "down", "left", "right", "fire", "skill")
# 固定方向别名：WASD 始终可用（不与自定义键冲突时），改键不影响
DIR_ALIAS_KEYS = {"K_w": UP, "K_s": DOWN, "K_a": LEFT, "K_d": RIGHT}

# ---------- 坦克/子弹（单位：像素/帧，计时单位：帧） ----------
TANK_SIZE = 21
PLAYER_SPEED = 2.0
BULLET_SPEED = 5.0
BULLET_SIZE = 6
BULLET_HOMING_TURN = 0.10    # 追踪弹每帧最大转角（弧度，≈5.7°），越大拐得越急

# 表现层特效上限：不进入 RL 观测，也不参与碰撞
FX_MAX_PARTICLES = 240
FX_MAX_AFTERIMAGES = 12
FX_TRAIL_INTERVAL = 2

# 弹匣换弹：打空自动换弹（换弹期间不能射击），玩家与 AI 同规则
MAG_SIZES = {"scout": 3, "standard": 4, "heavy": 2}        # 弹匣容量（按型号）
RELOAD_FRAMES = {"scout": 60, "standard": 90, "heavy": 120}  # 换弹时长（帧，1s/1.5s/2s）

PLAYER_FIRE_COOLDOWN = 21          # 0.35s * 60fps
PLAYER_MAX_BULLETS = 2               # 场上玩家子弹上限

# 技能：K 键瞬发，与普通开火冷却分开
PLAYER_SKILL_COOLDOWN = 42       # 穿甲/冲击波冷却（0.7s）

# ---------- 玩家坦克型号（开局前选择；训练/评估固定 standard） ----------
# fire_mode: single=单发 / burst=按键一次自动二连发 / fan=扇形冲击（无实体弹）
# bullet_frames: 普通弹射程帧数（1 帧=5px，1 格=24px）；piercing_frames: 穿甲弹射程帧数
# 弹匣换弹见上方 MAG_SIZES/RELOAD_FRAMES（burst 一次扳机耗 1 发弹匣）
TANK_TYPES = {
    # 轻骑：二连发，射程 2.5 格；K 疾冲 2 格穿钢板，可存 2 次
    "scout":    {"speed": 2.6, "fire_cooldown": 21, "max_bullets": 2,
                 "attack_damage": 20, "skill_damage": 0,
                 "skill_cooldown": 42,
                 "fire_mode": "burst", "burst_gap": 6, "bullet_frames": 12,
                 "skill": "dash", "dash_tiles": 2, "dash_charges": 2},
    # 标准：单发射程 3.5 格；K 穿甲弹射程 8 格，沿车头直飞
    "standard": {"speed": PLAYER_SPEED, "fire_cooldown": PLAYER_FIRE_COOLDOWN,
                 "max_bullets": PLAYER_MAX_BULLETS,
                 "attack_damage": 34, "skill_damage": 50,
                 "skill_cooldown": PLAYER_SKILL_COOLDOWN,
                 "fire_mode": "single", "bullet_frames": 17,
                 "piercing_frames": 38},
    # 重装：扇形冲击半径 2 格；K 全向冲击波，半径相同
    "heavy":    {"speed": 1.6, "fire_cooldown": 26, "max_bullets": 3,
                 "attack_damage": 40, "skill_damage": 60,
                 "skill_cooldown": 42,
                 "fire_mode": "fan", "fan_radius": 48, "fan_half_angle": 30,
                 "shock_radius": 48,
                 "skill": "shockwave"},
}
TANK_ORDER = ["scout", "standard", "heavy"]   # 选择界面顺序
DEFAULT_TANK = "standard"
AI_RANDOM_TANK = True              # 玩家对战局 AI 对手随机三款坦克（训练/评估在 env.py 里置 False）
FOE_GUIDE = True                   # 玩家局 AI 策略引导：见人才开火/躲毒圈/趋向中心（训练自博弈不受影响）
RESPAWN_INVINCIBLE = 120           # 复活无敌 2 秒
ALIGN_GRID = 4                     # 转向时对齐网格的步长（保证能穿过单格通道）

# ---------- 计分 ----------
SCORE_KILL = 100

# ---------- 对战模式（竞技场大混战，无基地） ----------
VERSUS_LIVES = 1                             # 每方 1 条命（血尽即淘汰，无复活）
VERSUS_HP = 100                              # 整数 HP；100 点下数值同时对应百分比
HIT_INVINCIBLE = 30                          # 受击后 0.5s 无敌，防止一轮子弹连续扣血
HIT_KNOCKBACK = 4                            # 受击沿子弹飞行方向击退像素（被地形/坦克挡住则不动）
# 乱斗人数：2-10，设置页调整；玩家恒 1 席，其余 AI 补位
NUM_COMBATANTS = 4                 # 默认 4 人
NUM_COMBATANTS_MIN = 2
NUM_COMBATANTS_MAX = 10

# 出生位：不再硬编码，由 level.generate_spawns 在空地上随机选互不相邻的点

# ---------- 道具（定时随机刷 + 击杀掉落 双通道） ----------
ITEM_SPAWN_INTERVAL = 600        # 定时刷：每 10s（60fps）在随机空格刷 1 个
ITEM_MAX_TIMED = 2               # 定时通道场上最多同时 2 个
ITEM_MAX_DROP = 1                # 击杀掉落通道场上最多 1 个（新掉落顶掉旧掉落）
ITEM_TTL = 900                   # 道具存活 15s，到 0 消失
ITEM_BLINK_TTL = 180             # 最后 3s 闪烁提示即将消失
ITEM_TYPES = ("heal", "fire", "shield", "mine")      # 定时刷池（各 25%）
ITEM_DROP_TYPES = ("heal", "fire", "shield")         # 击杀掉落池（无地雷，各 1/3）
HEAL_HP = 34                   # 加血道具回复 34 HP
MINE_DAMAGE = 34               # 地雷造成 34 伤害
FIRE_COOLDOWN_SCALE = 0.7        # 火力道具：开火冷却 ×0.7
FIRE_MAX_STACKS = 2              # 火力最多叠 2 层
FIRE_COOLDOWN_MIN = 8            # 开火冷却下限（帧）
SHIELD_FRAMES = 300              # 护盾：无敌 5s（复用 invincible 字段）
MAX_ITEMS = 3                    # 场上道具总数上限（2 定时 + 1 掉落），也是状态向量道具槽数

# ---------- 毒圈收缩（逐圈推进：强制遭遇战） ----------
ZONE_GRACE_FRAMES = 360          # 开局安全期 6s
ZONE_SHRINK_INTERVAL = 180       # 之后每 3s 缩 1 圈（一层一层过渡，8 圈共 24s）
ZONE_INITIAL_RADIUS = 8          # Chebyshev 距离，8=全图 17x17 安全
ZONE_TICK_FRAMES = 90            # 圈外每 1.5s 扣血一次（无视无敌/护盾）
ZONE_DAMAGE = 34                 # 毒圈每跳造成 34 伤害

# ---------- 视野（战争迷雾） ----------
VIEW_RADIUS_TILES = 6.0          # 固定圆形视野半径（格），按坦克中心像素距离判定

# ---------- 对战自博弈奖励（1 命制重构：击杀即淘汰，无胜负叠加项） ----------
VS_R_KILL = 500.0      # 淘汰一个对手
VS_R_DEATH = -500.0    # 自己被淘汰（终局）
VS_R_STEP = -0.2       # 每决策步微罚（原 -1.0 过重，会逼 AI 抢死）
VS_R_MOVE = 0.2        # 本决策内位移 >= 3px：鼓励到处走
VS_R_IDLE = -0.2       # 本决策几乎没动：反蹲点
VS_R_ZONE_OUT = -2.0   # 决策时中心格在安全区外
VS_R_ZONE_EDGE = -0.5  # 在安全区边界 <=1 格内（提前撤离，别贴毒圈）
VS_R_SHOT = -1.0       # 每发子弹/范围技：抑制无意义扫射
VS_R_HIT = 4.0         # 每次有效命中（按次数计，不按伤害量缩放）
MAX_DECISION_STEPS = 3000          # 单局决策步上限，超时强制结束
FRAME_SKIP = 4                     # 每 4 帧一次决策

# ---------- AI 温和化（玩家对局手感；训练自博弈同样生效） ----------
AI_FIRE_COOLDOWN_SCALE = 1.35   # AI 开火/技能冷却倍率（21 帧 -> 28 帧，约 0.47s）
AI_FIRE_RANGE_RATIO = 0.8       # 目标进入 80% 射程内才开火/放技能，留反应与走位空间
AI_BULLET_HOMING = False        # AI 子弹直飞；玩家子弹保留追踪

# ---------- 货币：零件（对局胜利获得，后续用于购买坦克） ----------
PARTS_WIN = 30                  # 胜利基础奖励
PARTS_PER_KILL = 10             # 每击杀额外奖励

# ---------- RL 动作空间 ----------
# 0=不动 1~4=上/下/左/右 5~8=移动+射击 9=原地射击
N_ACTIONS = 10
