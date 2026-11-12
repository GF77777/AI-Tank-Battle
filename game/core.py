"""Game 核心：状态机（开始/进行/暂停/胜利/失败）、输入、碰撞、对战逻辑、渲染。"""

import math
import os
import queue
import random
import threading

import pygame

from . import settings as S
from . import prefs
from . import avatars
from . import ime
from .audio import Audio
from .entities import Afterimage, Explosion, Item, PixelParticle, PlayerTank, tile_to_px
from .level import load_versus_map, generate_spawns
from .playtest import PlaytestLogger
from .sprites import (
    FX_BRICK, FX_BRICK_LIGHT, FX_DASH, FX_STEEL, FX_ZONE,
    get as get_sprites,
)

STATE_START = "start"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_WIN = "win"
STATE_LOSE = "lose"

# 标题界面的模式：0=AI 对战(纯净) 1=对战模式(毒圈道具) 2=跑图练习 3=坦克仓库
MODE_PURE, MODE_VERSUS, MODE_ROAM, MODE_GARAGE = 0, 1, 2, 3
ROW_SETTINGS = 4             # 标题根视图：设置
ROW_MAP_CONFIG = 5           # 标题根视图：出战配置-地图卡片（A/D 调整）
ROW_COUNT = 6                # 标题根视图可选行总数

# ---- 页面骨架（全部子页共用，渲染与鼠标命中共用）----
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 24, 104, 368, 312   # 统一子页面板：104..416
PANEL = (PANEL_X, PANEL_Y, PANEL_W, PANEL_H)
TITLE_Y = PANEL_Y + 12                   # 116 标题基线
TITLE_LINE_Y = PANEL_Y + 44              # 148 标题下分隔线
LIST_Y0 = PANEL_Y + 56                   # 160 列表首行
ROW_H = 30                               # 行可点高度
ROW_PITCH = 36                           # 行距
HINT_Y = PANEL_Y + 288                   # 392 底部提示
MENU_X, MENU_W = 88, 240                 # 列表行 x/宽

# ---- 主菜单 ----
CARD_TANK = (108, 60, 200, 152)          # 中央地图卡片
MODE_Y0, MODE_PITCH = 226, 34            # 按钮列首行 / 行距（5 行止于 392）
FOOTER_LINE_Y, FOOTER_HINT_Y, FOOTER_AI_Y = 404, 414, 434

# ---- 暂停菜单 ----
PAUSE_PANEL = (88, 132, 240, 248)
PAUSE_TITLE_Y, PAUSE_Y0, PAUSE_PITCH = 146, 192, 34
PAUSE_W = 200                            # 按钮宽（面板内 20 边距居中）
PAUSE_HINT_Y = 336

# ---- 结算页 ----
END_CARD_A = (24, 92, 368, 92)           # 战绩横条
END_CARD_B = (24, 192, 368, 176)         # 排名表
END_BTN_Y, END_BTN_W, END_BTN_H, END_BTN_GAP = 380, 150, 32, 16

# 名片页整体上移12px；输入框由渲染与输入法定位共用
PROFILE_DY = -12
PROFILE_BOX = (S.SCREEN_WIDTH // 2 - 110, 256 + PROFILE_DY, 220, 32)

# 界面文案（中文优先，无中文字体时回退英文）
_TEXTS = {
    "title": ("AI 坦克大战", "AI TANK BATTLE"),
    "tagline": ("复古像素坦克大战 · 击败你训练的 AI",
                "Retro pixel tanks · Beat the AI you trained"),
    "sec_mode": ("模 式", "MODE"),
    "sec_config": ("出 战 配 置", "LOADOUT"),
    "mode_settings": ("设 置", "SETTINGS"),
    "cfg_music": ("音 乐", "MUSIC"),
    "cfg_sfx": ("音 效", "SFX"),
    "cfg_master_volume": ("总 音 量", "MASTER"),
    "cfg_sfx_volume": ("音效音量", "SFX VOLUME"),
    "cfg_players": ("人 数", "PLAYERS"),
    "cfg_enemy_names": ("对手名字", "FOE NAMES"),
    "cfg_keys": ("键 位", "KEYS"),
    "cfg_back": ("返 回", "BACK"),
    "set_on": ("开", "ON"),
    "set_off": ("关", "OFF"),
    "hint_settings": ("点击或 A/D 调整 · Esc 返回",
                      "Click or A/D adjust · ESC back"),
    "profile_title": ("名 片", "PROFILE"),
    "parts": ("零件", "PARTS"),
    "profile_no_avatar": ("无头像", "NO AVATAR"),
    "hint_profile": ("输入名字 · 点头像换头像 · Enter 确认 · Esc 取消",
                      "Type name · click avatar · ENTER ok · ESC cancel"),
    "hint_profile_view": ("点击名字改名 · 点头像换头像 · Esc 返回",
                          "Click name to edit · click avatar to change · ESC back"),
    "profile_import": ("导入头像", "IMPORT IMAGE"),
    "keybind_title": ("键 位", "KEY BINDING"),
    "hint_keybind": ("W/S 选择 · Enter 改键 · Esc 返回",
                     "W/S select · ENTER rebind · ESC back"),
    "keybind_wait": ("按任意键…", "PRESS A KEY..."),
    "keybind_reset": ("恢复默认", "RESET DEFAULTS"),
    "keybind_up": ("上", "UP"),
    "keybind_down": ("下", "DOWN"),
    "keybind_left": ("左", "LEFT"),
    "keybind_right": ("右", "RIGHT"),
    "keybind_fire": ("普攻", "ATTACK"),
    "keybind_skill": ("技能", "SKILL"),
    "hint_controls": ("W/S 选择 · A/D 调整 · Enter 确认",
                      "W/S select · A/D adjust · ENTER confirm"),
    "hint_ai": ("AI 策略：Double DQN 模型", "AI POLICY: DOUBLE DQN"),
    "mode_versus": ("排 位", "RANKED"),
    "mode_pure": ("对 战", "BATTLE"),
    "mode_roam": ("自 定 义", "CUSTOM"),
    "map_0": ("随 机", "RANDOM"),
    "map_1": ("折角回廊", "CORRIDOR"),
    "map_2": ("十字阵", "CROSS"),
    "map_3": ("放射阵", "RADIAL"),
    "roam_reset": ("靶子已全部重建", "TARGETS RESET"),
    "mode_garage": ("坦 克 营 地", "TANK CAMP"),
    "hint_garage": ("A/D 预览 · Enter/点击选用 · Esc 返回",
                    "A/D preview · ENTER/CLICK select · ESC back"),
    "in_use": ("使用中", "IN USE"),
    "garage_owned": ("已拥有", "OWNED"),
    "garage_choose": ("Enter 选用", "ENTER SELECT"),
    "garage_speed": ("速度", "SPEED"),
    "garage_rate": ("射速", "RATE"),
    "garage_skill_cd": ("技冷", "SKILL CD"),
    "garage_mag": ("弹量", "MAG"),
    "tank_scout": ("轻 骑", "SCOUT"),
    "tank_standard": ("标 准", "STANDARD"),
    "tank_heavy": ("重 装", "HEAVY"),
    "tank_desc_scout": ("普攻20%·二连发，疾冲无伤",
                        "ATK 20% · burst; dash deals no damage"),
    "tank_desc_standard": ("普攻34%·均衡配置，穿甲50%",
                           "ATK 34% · piercing 50%"),
    "tank_desc_heavy": ("普攻40%·扇形清场，冲击波60%",
                        "ATK 40% · shockwave 60%"),
    "hint_back": ("Enter 返回", "ENTER to go back"),
    "versus_1": ("未找到 models/dqn_tank.pth", "models/dqn_tank.pth not found"),
    "versus_2": ("请先运行 python train.py 训练", "Run python train.py first"),
    "agent_loading_1": ("AI 模型加载中…", "LOADING AI MODEL..."),
    "agent_loading_2": ("完成后自动进入", "Starts automatically when ready"),
    "hint_agent_loading": ("Esc 取消进入 · 后台继续加载", "ESC cancel · loading continues"),
    "agent_failed_1": ("AI 模型加载失败", "FAILED TO LOAD AI MODEL"),
    "agent_failed_2": ("请检查模型文件或重新训练", "Check the model file or retrain"),
    "footer": ("Pygame · PyTorch · Double DQN", "Pygame · PyTorch · Double DQN"),
    "pause": ("暂 停", "PAUSED"),
    "resume": ("继续", "RESUME"),
    "restart": ("重新开始", "RESTART"),
    "back_title": ("返回首页", "HOME"),
    "hint_pause": ("上下键 选择    Enter 确认",
                   "UP/DOWN select, ENTER confirm"),
    "hint_start": ("按 Enter 开始", "Press ENTER to start"),
    "hint_restart": ("按 Enter 重新开始", "Press ENTER to restart"),
    "win": ("胜 利 ！", "VICTORY!"),
    "lose": ("游戏结束", "GAME OVER"),
    "cause_life": ("原因：坦克被击毁", "TANK DESTROYED"),
    "score": ("分数", "SCORE"),
    "time": ("用时", "TIME"),
    "kills": ("击杀", "KILLS"),
    "hud_left":       ("剩余", "LEFT"),
    "hud_hp":         ("生命", "HP"),
    "zone_card":      ("安全区", "SAFE ZONE"),
    "skill_name_piercing":  ("穿甲", "APG"),
    "skill_name_dash":      ("疾冲", "DASH"),
    "skill_name_shockwave": ("冲击波", "SHOCK"),
    "end_rank":   ("排名", "RANK"),
    "end_you":    ("你", "YOU"),
    "end_alive":  ("存活", "ALIVE"),
    "end_dead":   ("淘汰", "OUT"),
    "end_again":  ("再来一局(Enter)", "AGAIN (ENTER)"),
    "end_back":   ("返回(Esc)", "BACK (ESC)"),
}

_font_cache = {}
_cjk_ok = None

# 直接用绝对路径加载系统字体，绕过 pygame.font.match_font 的注册表枚举（
# 本机字体注册表有非法整数值，match_font 会抛 TypeError 导致游戏无法启动）。
_FONT_CANDIDATES = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyh.ttc"),     # 微软雅黑
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simhei.ttf"),   # 黑体
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simsun.ttc"),   # 宋体
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simkai.ttf"),   # 楷体
]
_FONT_PATH = None     # 懒加载：第一次 get_font 时确定可用字体路径


def _detect_cjk_font():
    global _cjk_ok
    if _cjk_ok is None:
        _cjk_ok = any(os.path.exists(p) for p in _FONT_CANDIDATES)
    return _cjk_ok


def get_font(size):
    if size not in _font_cache:
        global _FONT_PATH
        if _FONT_PATH is None:
            for p in _FONT_CANDIDATES:
                try:
                    if os.path.exists(p):
                        _FONT_PATH = p
                        break
                except OSError:
                    continue
        try:
            _font_cache[size] = (pygame.font.Font(_FONT_PATH, size)
                                 if _FONT_PATH else pygame.font.Font(None, size))
        except Exception:
            _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]


def T(key):
    zh, en = _TEXTS[key]
    return zh if _detect_cjk_font() else en


def _clipboard_text():
    """读取剪贴板中的文本（名片改名的备用输入，失败返回空串）。"""
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        data = pygame.scrap.get(pygame.SCRAP_TEXT)
    except Exception:
        return ""
    if not data:
        return ""
    try:
        text = data.decode("utf-8", "ignore")
    except Exception:
        return ""
    return "".join(ch for ch in text if ch.isprintable())


def _pick_image_file():
    """弹出系统选图框（tkinter）；取消或不可用返回空串。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return ""
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title=T("profile_import"),
            filetypes=[("图片", "*.png *.jpg *.jpeg"), ("所有文件", "*.*")])
    except Exception:
        path = ""
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
    return path or ""


def _agent_preload_worker(path, result_queue):
    """后台只加载推理模型；结果由主线程统一安装。"""
    try:
        if not os.path.exists(path):
            result_queue.put(("missing",))
            return
        from ai.dqn import DQNAgent
        from .env import STATE_DIM, build_foe_state, decode_action  # env 依赖 core，只能延迟导入
        agent = DQNAgent(STATE_DIM, S.N_ACTIONS, buffer_capacity=0)
        agent.load(path)
        result_queue.put(("ready", agent, build_foe_state, decode_action))
    except Exception as exc:
        result_queue.put(("failed", str(exc)))


class Game:
    def __init__(self, log_playtest=False):
        self.state = STATE_START
        self.frame = 0            # 全局帧计数（驱动闪烁动画）
        self.mode_index = MODE_PURE       # 标题界面选中的模式（默认主玩法 AI 对战）
        self.battle_mode = "versus"     # 当局模式：versus(毒圈道具) / pure(纯净AI对战) / roam(跑图练习)
        self.map_index = 0              # 出战地图：0=随机 1-3=指定图（VERSUS_MAPS 下标+1）
        self.pause_index = 0              # 暂停菜单选中项
        self.start_notice = None          # 标题界面弹出提示（"versus"：模型缺失）
        self._icon_cache = {}
        self.audio = Audio()              # 无音频设备时自动静音
        p = prefs.load()
        self.audio.set_music(p["music"])
        self.audio.set_sfx(p["sfx"])
        self.audio.set_master_volume(p["master_volume"])
        self.audio.set_sfx_volume(p["sfx_volume"])
        self.show_enemy_names = p["enemy_names"]  # 对手头顶名字，默认关闭
        self.settings_view = False          # 是否处于设置子视图（标题/暂停共用）
        self.settings_index = 0             # 0音乐 1音效 2总音量 3音效音量 4人数 5名字 6键位 7返回
        self.settings_from = None           # 设置页来源："title" / "pause"
        self._hits = {}                     # 渲染帧写入的动态鼠标命中区
        self._mouse_nav = False             # 最近是否使用鼠标；避免鼠标悬停与键盘选中同时高亮
        self.playtest = PlaytestLogger() if log_playtest else None
        self.tank_type = S.DEFAULT_TANK      # 玩家坦克型号（RL 环境恒为 standard）
        self.garage = False                  # 标题界面是否处于坦克仓库视图
        self.garage_index = 0                # 仓库当前浏览的坦克下标
        self.tank_index = S.TANK_ORDER.index(S.DEFAULT_TANK)
        self.num_combatants = max(S.NUM_COMBATANTS_MIN,
                                  min(p["players"], S.NUM_COMBATANTS_MAX))  # 乱斗人数 2-10
        self.view_radius = S.VIEW_RADIUS_TILES  # 固定视野半径，供迷雾和小地图使用
        self.parts = int(p["parts"])        # 零件余额（胜利获得，后续用于购买坦克）
        self.parts_earned = 0               # 本局赢得零件（结算页展示）
        # 玩家名片：名字持久化；头像从素材池取（prefs 记文件名，缺失时随机抽一个）
        self.player_name = p["name"]
        self.player_avatar = None           # (名字, surface) 或 None（池空）
        self._avatar_dirty = False          # 头像为随机抽取、尚未持久化
        if p["avatar"]:
            self.player_avatar = avatars.by_filename(p["avatar"])
        if self.player_avatar is None:
            picked = avatars.assign(1)
            if picked:
                self.player_avatar = picked[0]
                self._avatar_dirty = True
        self.profile_view = False           # 名片编辑子视图
        self.profile_focus = False          # 名字框是否处于改名态（点击后才可输入）
        self.profile_editing = ""           # 改名输入缓冲（已上屏字符）
        self.profile_composing = ""         # 输入法组合中的内容（拼音/候选）
        self.profile_avatar_index = 0       # 名片页头像池下标（仅显示计数用）
        # 键位：prefs 未记录时回落到 S.DEFAULT_KEYBINDS 里的 pygame 常量名
        self.keybinds = {
            name: p["keys"].get(name) or getattr(pygame, S.DEFAULT_KEYBINDS[name])
            for name in S.KEYBIND_ORDER
        }
        self.dir_keys = {}                  # {pygame 键码: 方向}，由 _rebuild_dir_keys 生成
        self._rebuild_dir_keys()
        self.keybind_view = False           # 键位设置子页
        self.keybind_index = 0              # 0-5=六个动作 6=恢复默认
        self.keybind_waiting = False        # 等待玩家按下新键
        self.dqn_agent = None              # 对战模式共享的 DQN（后台加载，3 个 AI 共用一个实例）
        self.foe_agent = None              # 训练时注入的对手驱动（自博弈，优先于 dqn_agent）
        self.foe_epsilon = 0.0             # 自博弈：对手与学习者共享 ε
        self._build_foe_state = None       # env.build_foe_state（后台加载/训练注入）
        self._decode_vs_action = None      # env.decode_action（后台加载/训练注入）
        self._agent_queue = None           # worker -> 主线程的加载结果队列
        self._agent_thread = None          # 每个 Game 最多启动一个预加载线程
        self._agent_status = "idle"        # idle/loading/ready/missing/failed
        self._pending_ai_mode = None       # 加载期间等待进入的 pure/versus
        self._reset_battle()

    # ---------------- 生命周期 ----------------

    def _reset_battle(self):
        """对战竞技场：3 张对称地图随机抽 1 张，无基地、无刷怪；道具双通道刷新。"""
        self.battle_mode = "versus"    # 默认对战；pure/roam 由各自入口在调用后覆盖
        self.current_map_index = self.map_index or random.randint(1, 3)
        self.grid = load_versus_map(self.current_map_index)
        self.score = 0
        self.kills = 0
        self.parts_earned = 0            # 本局赢得零件（结算页展示，胜利时写入）
        self.burst_left = 0              # 轻骑二连发剩余待出弹数
        self.burst_timer = 0
        self.fan_flash = 0               # 重装扇形闪光剩余帧
        self.lives = S.VERSUS_LIVES      # 玩家与 AI 共用同一生命数（1 命制）
        self.time_frames = 0
        self.lose_reason = None          # "life" 坦克被击毁
        self.items = []                  # 场上道具（Item 列表）
        self.item_timer = S.ITEM_SPAWN_INTERVAL   # 定时刷道具倒数
        self.zone_radius = S.ZONE_INITIAL_RADIUS  # 毒圈：当前安全区半径
        self.zone_timer = S.ZONE_GRACE_FRAMES     # 毒圈：距下次收缩帧数
        self.zone_tick = 0                        # 毒圈：圈外扣血节拍
        self.announcements = []                   # 公告队列：[text, color, ttl]
        self.kill_feed = []                       # 击杀播报：[text, ttl]
        self._zone_warned = False                 # 毒圈收缩前警告已发（每局一次）
        self._spawns = generate_spawns(self.grid, self.num_combatants)   # 互不相邻出生位
        px, py = tile_to_px(*self._spawns[0])
        self.player = PlayerTank(px, py, self.tank_type)
        self.was_in_forest = self.in_forest(self.player)
        self.versus_foes = []
        self.enemies = []
        self._spawn_versus_foes()
        self.bullets = []
        self.explosions = []
        self.frame_events = {"kills": 0, "player_hit": False}
        # 打击反馈：独立视觉随机源，避免影响地图、出生点和道具随机序列
        self.fx_rng = random.Random()
        self.shake = 0                   # 屏幕震动剩余帧
        self.shake_total = 0
        self.shake_max = 0
        self.whiteout = 0                # 全屏白闪剩余帧（保留旧字段，不主动触发）
        self.flashes = []                # 击中闪白 [{"rect": Rect, "timer": 2}]
        self.rings = []                  # 闪光环 [{"x","y","timer","total","r0","r1","w"}]
        self.particles = []              # 尾迹、火花与碎屑共用粒子池
        self.afterimages = []            # 疾冲残影
        self.muzzles = []                # 枪口火焰
        # 出生保护：2s 无敌（双保险之一，另一层是出生角掩体遮挡）
        self.player.invincible = S.RESPAWN_INVINCIBLE
        for foe in self.versus_foes:
            foe.invincible = S.RESPAWN_INVINCIBLE

    def start_agent_preload(self):
        """启动唯一的后台加载线程；普通 Game/RL 环境不会自动调用。"""
        if self.dqn_agent is not None:
            self._agent_status = "ready"
            return
        if self._agent_thread is not None:
            return
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "models", "dqn_tank.pth")
        self._agent_queue = queue.Queue()
        self._agent_status = "loading"
        self._agent_thread = threading.Thread(
            target=_agent_preload_worker,
            args=(path, self._agent_queue),
            name="dqn-agent-preload",
            daemon=True,
        )
        self._agent_thread.start()

    def _poll_agent_preload(self):
        """非阻塞接收加载结果，并在标题页自动进入等待的模式。"""
        if self._agent_queue is None:
            return
        try:
            result = self._agent_queue.get_nowait()
        except queue.Empty:
            return

        if result[0] != "ready":
            self._agent_status = result[0]
            if self._pending_ai_mode is not None:
                self._pending_ai_mode = None
                self.start_notice = "versus" if result[0] == "missing" else "agent_failed"
            return

        _, agent, build_foe_state, decode_action = result
        # 先安装决策钩子，再发布 Agent，保证对局看到完整初始化结果。
        self._build_foe_state = build_foe_state
        self._decode_vs_action = decode_action
        self.dqn_agent = agent
        self._agent_status = "ready"

        pending = self._pending_ai_mode
        self._pending_ai_mode = None
        if pending is not None and self.state == STATE_START:
            self.start_notice = None
            if pending == "pure":
                self._start_pure()
            else:
                self._start_versus()

    def _ensure_agent(self, mode):
        """模型就绪才立即开局，否则显示加载页并记录待进入模式。"""
        if self.dqn_agent is not None:
            self._agent_status = "ready"
            return True
        if self._agent_status in ("missing", "failed"):
            self.start_notice = "versus" if self._agent_status == "missing" else "agent_failed"
            return False
        self._pending_ai_mode = mode
        self.start_notice = "agent_loading"
        self.start_agent_preload()
        return False

    def _start_versus(self):
        """进入对战模式：加载 DQN 模型，重置竞技场（带毒圈/道具/空投）。"""
        if not self._ensure_agent("versus"):
            return
        self._reset_battle()
        if self.playtest is not None:
            self.playtest.start_session()
        self.state = STATE_PLAYING

    def _start_pure(self):
        """纯净版 AI 对战：同对战规则（杀光 AI 获胜），但关闭毒圈/道具/空投。"""
        if not self._ensure_agent("pure"):
            return
        self._reset_battle()
        self.battle_mode = "pure"
        if self.playtest is not None:
            self.playtest.start_session()
        self.state = STATE_PLAYING

    def _start_roam(self):
        """跑图练习：只有玩家 + 4 个静止靶子，无毒圈/道具/AI，靶子全灭自动重建。"""
        self._reset_battle()
        self.battle_mode = "roam"
        self.versus_foes.clear()
        self.enemies.clear()
        self._spawn_roam_dummies()
        self.state = STATE_PLAYING

    def _spawn_roam_dummies(self):
        """生成 4 个静止靶子坦克（kind="dummy"），供练习射击/追踪弹。"""
        # 四个位置在三张地图均为公共空地，避免靶子卡进特殊地块。
        for i, tile in enumerate(((8, 7), (14, 8), (8, 2), (14, 1))):
            fx, fy = tile_to_px(*tile)
            dummy = PlayerTank(fx, fy, "standard")
            dummy.kind = "dummy"
            dummy.tag = f"T{i + 1}"
            dummy.lives = 1
            dummy.hp = dummy.max_hp
            dummy.direction = S.DOWN
            dummy.invincible = 0
            self.versus_foes.append(dummy)
            self.enemies.append(dummy)

    def _restart_battle(self):
        """按当前模式重开一局（暂停菜单/结算页共用入口）。"""
        starters = {"versus": self._start_versus, "pure": self._start_pure,
                    "roam": self._start_roam}
        starters[self.battle_mode]()

    def _spawn_versus_foes(self):
        """创建 DQN 驱动的 AI 对手，放入 versus_foes 与 enemies。

        玩家局按 S.AI_RANDOM_TANK 随机三款坦克；训练（foe_agent 注入）恒 standard。
        复用 PlayerTank 的冷却/弹上限/移动/技能接口；kind="foe" 标识 AI 对手。
        名字/头像解耦：头像从 assets/avatars 随机取，名字从内置名字池随机匹配（每局重抽）；
        头像不够时循环复用，名字保证不重复。
        """
        n_foes = self.num_combatants - 1
        # 名字与头像解耦：头像从 assets/avatars 随机取（文件名不作名字），名字随机抽
        names = avatars.fallback_names(n_foes, exclude=(self.player_name,))
        items = [img for _stem, img in avatars.pool()]
        random.shuffle(items)
        imgs = [items[i % len(items)] for i in range(n_foes)] if items else [None] * n_foes
        # 名片反查表：击杀播报/结算排名按名字取头像（玩家固定 player_avatar）
        self._avatar_by_tag = {self.player_name: (self.player_avatar[1]
                                                  if self.player_avatar else None)}
        for i, spawn in enumerate(self._spawns[1:]):
            fx, fy = tile_to_px(*spawn)
            if self.foe_agent is not None or not S.AI_RANDOM_TANK:
                tank = S.DEFAULT_TANK
            else:
                tank = random.choice(S.TANK_ORDER)
            foe = PlayerTank(fx, fy, tank)
            # 温和化：AI 开火/技能冷却整体放慢（只影响 AI，玩家数值不变）
            foe.base_fire_cooldown = int(foe.base_fire_cooldown * S.AI_FIRE_COOLDOWN_SCALE)
            foe.fire_cooldown_max = foe.base_fire_cooldown
            foe.skill_cooldown_max = int(foe.skill_cooldown_max * S.AI_FIRE_COOLDOWN_SCALE)
            foe.kind = "foe"
            foe.tag, foe.avatar = names[i], imgs[i]
            self._avatar_by_tag[foe.tag] = foe.avatar
            foe.lives = S.VERSUS_LIVES
            foe.hp = foe.max_hp
            foe.spawn = spawn
            foe.direction = S.DOWN if spawn[1] < S.MAP_ROWS // 2 else S.UP   # 朝场地中心
            foe.vs_action = (None, False)        # 当前 DQN 决策 (方向, 开火)
            self.versus_foes.append(foe)
            self.enemies.append(foe)

    def back_to_title(self):
        self._reset_battle()
        self.state = STATE_START
        self.start_notice = None
        self._pending_ai_mode = None

    def _save_profile(self):
        """持久化设置/人数/名片/键位到 prefs.json（各入口共用出口）。"""
        prefs.save({
            "music": self.audio.music_on,
            "sfx": self.audio.sfx_on,
            "master_volume": self.audio.master_volume,
            "sfx_volume": self.audio.sfx_volume,
            "enemy_names": self.show_enemy_names,
            "players": self.num_combatants,
            "parts": self.parts,             # 保留零件余额，避免名片/设置保存时丢失
            "name": self.player_name,
            "avatar": self.player_avatar[0] if self.player_avatar else "",
            "keys": {n: self.keybinds[n] for n in S.KEYBIND_ORDER},
        })
        self._avatar_dirty = False

    def _rebuild_dir_keys(self):
        """重建 {键码: 方向}：自定义移动键 + WASD 固定别名（别名键未被占用时才加）。"""
        self.dir_keys = {}
        for name, direction in (("up", S.UP), ("down", S.DOWN),
                                ("left", S.LEFT), ("right", S.RIGHT)):
            self.dir_keys[self.keybinds[name]] = direction
        for alias, direction in S.DIR_ALIAS_KEYS.items():
            key = getattr(pygame, alias)
            if key not in self.dir_keys:
                self.dir_keys[key] = direction

    def _bind_key(self, action, key):
        """绑定新键：若该键已被其它动作占用，原动作回落默认，保证一键一用。"""
        for other in S.KEYBIND_ORDER:
            if other != action and self.keybinds[other] == key:
                self.keybinds[other] = getattr(pygame, S.DEFAULT_KEYBINDS[other])
        self.keybinds[action] = key
        self._rebuild_dir_keys()
        self._save_profile()

    def _reset_keybinds(self):
        """恢复默认键位。"""
        self.keybinds = {n: getattr(pygame, S.DEFAULT_KEYBINDS[n]) for n in S.KEYBIND_ORDER}
        self._rebuild_dir_keys()
        self._save_profile()

    def _cycle_avatar(self, step):
        """名片页切换头像（池循环）；池空时无操作。"""
        if not avatars.pool():
            return
        cur = self.player_avatar[0] if self.player_avatar else ""
        item = avatars.next_of(cur, step)
        if item:
            self.player_avatar = item
            self._avatar_dirty = False
            self._save_profile()
            self.audio.play("pickup", 0.4)

    def _import_avatar(self):
        """导入本地图片为头像：选图 -> 复制进素材目录 -> 选中并持久化。"""
        path = _pick_image_file()
        if not path:
            return
        item = avatars.import_file(path)
        if item is None:
            return
        self.player_avatar = item
        self._avatar_dirty = False
        self._save_profile()
        self.audio.play("pickup", 0.7)
        if self.profile_focus:              # 选图框夺焦后，改名态才重新挂回输入法
            ime.enable(PROFILE_BOX)

    def _close_profile(self, confirm):
        """关闭名片页：confirm=True 保存改名；恢复 IME 禁用状态。"""
        if confirm:
            name = self.profile_editing.strip()
            self.player_name = name if name else "玩家"
            self._save_profile()
        ime.restore()
        self.profile_view = False
        self.profile_focus = False
        self.profile_composing = ""

    def _keybind_key(self, key):
        """键位子页按键：等待态绑键；否则上下移动 / Enter 进入或恢复默认 / Esc 返回。"""
        if self.keybind_waiting:
            if key == pygame.K_ESCAPE:
                self.keybind_waiting = False           # 取消等待
            elif key not in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._bind_key(S.KEYBIND_ORDER[self.keybind_index], key)
                self.keybind_waiting = False
            return True
        if key == pygame.K_ESCAPE:
            self.keybind_view = False                  # 回设置页
            return True
        if key in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN):
            step = -1 if key in (pygame.K_w, pygame.K_UP) else 1
            self.keybind_index = (self.keybind_index + step) % 7
            return True
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.keybind_index < 6:
                self.keybind_waiting = True            # 等待玩家按键
            else:
                self._reset_keybinds()                 # 第 7 行：恢复默认
            return True
        return True

    def _adjust_players(self, step):
        """设置页人数行：2-10 循环调整并持久化。"""
        rng = S.NUM_COMBATANTS_MAX - S.NUM_COMBATANTS_MIN + 1
        self.num_combatants = (S.NUM_COMBATANTS_MIN
                               + (self.num_combatants - S.NUM_COMBATANTS_MIN + step) % rng)
        self._save_profile()
        self.audio.play("pickup", 0.4)

    # ---------------- 输入 ----------------

    def handle_event(self, event):
        """返回 False 表示退出程序。"""
        if event.type == pygame.QUIT:
            return False

        # 名片页：只有点过名字框（改名态）才接收文字
        if event.type == pygame.TEXTEDITING and self.profile_view and self.profile_focus:
            if not self.profile_composing:
                ime.reposition()         # 组合刚开始：候选窗贴到输入框下方（拖动后不打断）
            self.profile_composing = event.text
            return True
        if event.type == pygame.TEXTINPUT and self.profile_view and self.profile_focus:
            self.profile_editing = (self.profile_editing + event.text)[:10]
            self.profile_composing = ""
            return True

        if event.type == pygame.MOUSEMOTION:
            self._on_mouse_motion(event.pos)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._on_click(event.pos)
        if event.type != pygame.KEYDOWN:
            return True

        self._mouse_nav = False             # 键盘接管光标，清除静止鼠标的悬停态
        key = event.key

        # 名片编辑页：只处理控制键（文字来自 TEXTINPUT，避免重复追加）
        if self.profile_view:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._close_profile(True)
            elif key == pygame.K_ESCAPE:
                self._close_profile(False)      # 取消，不写回
            elif self.profile_focus and key == pygame.K_BACKSPACE:
                if self.profile_composing:
                    self.profile_composing = ""     # 组合中：先取消输入法组合
                else:
                    self.profile_editing = self.profile_editing[:-1]
            elif (self.profile_focus and key == pygame.K_v
                  and (pygame.key.get_mods() & pygame.KMOD_CTRL)):
                # 备用输入方式：Ctrl+V 粘贴中文（输入法候选窗异常时也能改名）
                self.profile_editing = (self.profile_editing + _clipboard_text())[:10]
            return True

        # 键位子页：等待按键时吞下任意键做绑定
        if self.keybind_view:
            return self._keybind_key(key)

        if key == pygame.K_ESCAPE:
            if self.settings_view:
                self._close_settings()        # 设置页 -> 返回来源界面
                return True
            if self.state == STATE_PLAYING:
                self.state = STATE_PAUSED
                self.pause_index = 0
                return True
            if self.state == STATE_PAUSED:
                return True                   # 暂停页 Esc 不退出，需选择“继续”
            if self.state == STATE_START and self.start_notice is not None:
                self.start_notice = None       # 加载中仅取消进入，后台继续缓存
                self._pending_ai_mode = None
                return True
            if self.state == STATE_START and self.garage:
                self.garage = False           # 坦克仓库 -> 退回模式列表
                return True
            return self.state == STATE_START  # 首页 Esc 不退出；结算界面保留原逻辑

        if key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
            step = -1 if key in (pygame.K_LEFT, pygame.K_a) else 1
            if self.settings_view:
                if self.settings_index in (2, 3):
                    self._adjust_volume(self.settings_index, step)  # 音量：A/D 调整 10%
                elif self.settings_index == 4:
                    self._adjust_players(step)               # 人数行：A/D 2-10 调整
                elif self.settings_index in (0, 1, 5):
                    self._toggle_setting(self.settings_index)   # 音乐/音效/名字：A/D 翻转
            elif self.state == STATE_START and self.garage:
                self.garage_index = (self.garage_index + step) % len(S.TANK_ORDER)
            elif (self.state == STATE_START and self.start_notice is None
                  and self.mode_index == ROW_MAP_CONFIG):
                self._adjust_config_row(self.mode_index, step)   # A/D 调整地图卡片
            return True

        if key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s):
            step = -1 if key in (pygame.K_UP, pygame.K_w) else 1
            if self.settings_view:
                self.settings_index = (self.settings_index + step) % 8
            elif self.state == STATE_START and self.garage:
                self.garage_index = (self.garage_index + step) % len(S.TANK_ORDER)
            elif self.state == STATE_START and self.start_notice is None:
                self.mode_index = (self.mode_index + step) % ROW_COUNT
            elif self.state == STATE_PAUSED:
                self.pause_index = (self.pause_index + step) % 4
            return True

        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._confirm()
        return True

    def _confirm(self):
        """Enter 键：按当前界面状态执行确认动作。"""
        if self.settings_view:
            if self.settings_index in (2, 3):
                pass                                           # 音量行只用 A/D 或点击调整
            elif self.settings_index == 4:
                self._adjust_players(1)                        # 人数行 Enter 等价右箭头
            elif self.settings_index == 6:
                self.keybind_view = True                       # 键位子页
                self.keybind_index = 0
                self.keybind_waiting = False
            elif self.settings_index == 7:
                self._close_settings()
            else:
                self._toggle_setting(self.settings_index)      # 音乐/音效/名字行翻转
            return
        if self.state == STATE_START:
            if self.garage:
                # 仓库：Enter 选用当前页坦克（同步配置行光标），留在仓库继续浏览
                self.tank_type = S.TANK_ORDER[self.garage_index]
                self.tank_index = self.garage_index
                self.audio.play("pickup", 0.7)
            elif self.start_notice is not None:
                if self.start_notice != "agent_loading":  # 加载中 Enter 不重复触发
                    self.start_notice = None      # 缺失/失败提示 -> 返回模式列表
                    self._pending_ai_mode = None
            elif self.mode_index == MODE_PURE:
                self._start_pure()                # AI 对战·纯净版（主玩法）
            elif self.mode_index == MODE_VERSUS:
                self._start_versus()              # 对战模式：毒圈收缩 + 道具空投
            elif self.mode_index == MODE_ROAM:
                self._start_roam()                # 跑图练习：固定靶自由练习
            elif self.mode_index == ROW_MAP_CONFIG:
                pass                              # 地图配置行：Enter 无操作（A/D 调整）
            elif self.mode_index == ROW_SETTINGS:
                self.settings_view = True         # 设置页
                self.settings_from = "title"
                self.settings_index = 0
            elif self.mode_index == MODE_GARAGE:
                self.garage = True                # 坦克仓库：从当前选用坦克开始浏览
                self.garage_index = S.TANK_ORDER.index(self.tank_type)
        elif self.state == STATE_PAUSED:
            if self.pause_index == 0:
                self.state = STATE_PLAYING
            elif self.pause_index == 1:
                self._restart_battle()            # 按当前模式重开
            elif self.pause_index == 3:
                self.settings_view = True         # 暂停菜单 -> 设置页
                self.settings_from = "pause"
                self.settings_index = 0
            else:
                self.back_to_title()
        elif self.state in (STATE_WIN, STATE_LOSE):
            self._restart_battle()                # 结算后 Enter 重开一局（保持当前模式）

    # ---------------- 鼠标与设置 ----------------

    def _on_mouse_motion(self, pos):
        """鼠标移动接管当前菜单的选中项，保持与键盘光标一致。"""
        self._mouse_nav = True
        mx, my = pos[0] // S.SCALE, pos[1] // S.SCALE

        def hit(key):
            rect = self._hits.get(key)
            return rect is not None and rect.collidepoint(mx, my)

        if self.profile_view:
            return
        if self.keybind_view:
            if not self.keybind_waiting:      # 等待改键时固定当前行，避免误改其他键位
                for i in range(7):
                    if hit("kb_%d" % i):
                        self.keybind_index = i
                        break
            return
        if self.settings_view:
            for i in range(8):
                if hit("set_%d" % i):
                    self.settings_index = i
                    break
            return

        if self.state == STATE_START:
            if self.garage:
                for i in range(len(S.TANK_ORDER)):
                    if hit("garage_tank_%d" % i):
                        self.garage_index = i
                        break
                return
            if self.start_notice is not None:
                return
            for key, mi in (("btn_pure", MODE_PURE), ("btn_versus", MODE_VERSUS),
                            ("btn_roam", MODE_ROAM), ("btn_garage", MODE_GARAGE),
                            ("btn_settings", ROW_SETTINGS)):
                if hit(key):
                    self.mode_index = mi
                    return
            if any(hit(key) for key in ("cfg_map_left", "cfg_map_right", "cfg_map_card")):
                self.mode_index = ROW_MAP_CONFIG
            return

        if self.state == STATE_PAUSED:
            for i in range(4):
                if hit("pause_%d" % i):
                    self.pause_index = i
                    break

    def _on_click(self, pos):
        """鼠标左键：窗口坐标 -> 逻辑坐标后按当前界面分发（命中区由渲染写入）。"""
        self._mouse_nav = True
        mx, my = pos[0] // S.SCALE, pos[1] // S.SCALE

        def hit(key):
            """命中区判定：渲染帧写入的矩形（布局与点击共用同一份坐标）。"""
            r = self._hits.get(key)
            return r is not None and r.collidepoint(mx, my)

        if self.profile_view:                     # 名片页：点头像/箭头循环换头像
            if hit("profile_import"):             # 选本地图片导入头像
                self._import_avatar()
            elif hit("profile_av_left"):
                self._cycle_avatar(-1)
            elif hit("profile_av_right") or hit("profile_av"):
                self._cycle_avatar(1)
            elif hit("profile_name"):
                # 点名字框才进入改名：聚焦并挂回输入法；再次点击取消聚焦
                self.profile_focus = True
                self.profile_composing = ""
                ime.enable(PROFILE_BOX)
            else:
                self.profile_focus = False        # 点空白处退出改名
                ime.restore()
            return True

        if self.keybind_view:                     # 键位子页：点行选中（动作行直接进入等待）
            for i in range(7):
                if not hit("kb_%d" % i):
                    continue
                if self.keybind_waiting:
                    self.keybind_waiting = False      # 等待按键时点击 = 取消
                    return True
                self.keybind_index = i
                if i < 6:
                    self.keybind_waiting = True
                else:
                    self._reset_keybinds()
                return True
            return True

        if self.settings_view:                    # 标题/暂停共用设置页
            for i in range(8):
                if not hit("set_%d" % i):
                    continue
                self.settings_index = i
                if i in (2, 3):
                    # 音量行：点左半 -10% / 右半 +10%（边界钳制）
                    cx = self._hits["set_%d" % i].centerx
                    self._adjust_volume(i, -1 if mx < cx else 1)
                elif i == 4:
                    # 人数行：点左半 -1 / 右半 +1（2-10 循环）
                    cx = self._hits["set_4"].centerx
                    self._adjust_players(-1 if mx < cx else 1)
                elif i == 6:
                    self.keybind_view = True          # 键位子页
                    self.keybind_index = 0
                    self.keybind_waiting = False
                elif i == 7:
                    self._close_settings()
                else:
                    self._toggle_setting(i)
                return True
            return True

        if self.state == STATE_START:
            if self.garage:
                if hit("garage_back"):
                    self.garage = False
                    return True
                for i in range(len(S.TANK_ORDER)):
                    if hit("garage_tank_%d" % i):
                        self.garage_index = i
                        self._confirm()             # 点底部卡片直接选用
                        return True
                if hit("garage_select"):
                    self._confirm()               # 点左侧预览 = 选用
                return True
            if self.start_notice is not None:
                if self.start_notice != "agent_loading":  # 加载中点击不重复触发
                    self.start_notice = None      # 缺失/失败提示任意点击返回
                    self._pending_ai_mode = None
                return True
            # 根视图：按钮列单击即确认；地图卡片箭头按左右等价 A/D
            for key, mi in (("btn_pure", MODE_PURE), ("btn_versus", MODE_VERSUS),
                            ("btn_roam", MODE_ROAM), ("btn_garage", MODE_GARAGE),
                            ("btn_settings", ROW_SETTINGS)):
                if hit(key):
                    self.mode_index = mi
                    self._confirm()
                    return True
            if hit("cfg_map_left"):
                self.mode_index = ROW_MAP_CONFIG
                self._adjust_config_row(ROW_MAP_CONFIG, -1)
                return True
            if hit("cfg_map_right"):
                self.mode_index = ROW_MAP_CONFIG
                self._adjust_config_row(ROW_MAP_CONFIG, 1)
                return True
            if hit("cfg_map_card"):
                self.mode_index = ROW_MAP_CONFIG
                card = self._hits["cfg_map_card"]
                self._adjust_config_row(ROW_MAP_CONFIG, -1 if mx < card.centerx else 1)
                return True
            if hit("profile"):
                self.profile_view = True            # 点顶栏名片 -> 名片页（默认只展示）
                self.profile_editing = self.player_name
                self.profile_avatar_index = 0
                self.profile_focus = False          # 点名字框后才进入改名
                return True
            return True

        if self.state == STATE_PAUSED:
            for i in range(4):
                if hit("pause_%d" % i):
                    self.pause_index = i
                    self._confirm()
                    return True
            return True

        if self.state in (STATE_WIN, STATE_LOSE):
            if hit("end_again"):                  # 仅按钮可点（避免误触重开）
                self._restart_battle()
            elif hit("end_back"):
                self.back_to_title()
        return True

    def _adjust_config_row(self, row, step):
        """配置行左/右调整：地图卡片换图（随机+3 图循环，等价 A/D）。"""
        if row == ROW_MAP_CONFIG:
            self.map_index = (self.map_index + step) % 4
        self.audio.play("pickup", 0.4)

    def _toggle_setting(self, idx):
        """翻转设置项并持久化：0=音乐 1=音效 5=对手名字。"""
        if idx == 0:
            self.audio.set_music(not self.audio.music_on)
        elif idx == 1:
            self.audio.set_sfx(not self.audio.sfx_on)
        elif idx == 5:
            self.show_enemy_names = not self.show_enemy_names
        else:
            return
        self._save_profile()
        self.audio.play("pickup", 0.5)            # 音效行关闭后此声自然不响

    def _adjust_volume(self, idx, step):
        """总音量/音效音量按 10% 调整，边界钳制并立即保存。"""
        if idx == 2:
            self.audio.set_master_volume(self.audio.master_volume + step * 10)
        elif idx == 3:
            self.audio.set_sfx_volume(self.audio.sfx_volume + step * 10)
        else:
            return
        self._save_profile()
        self.audio.play("pickup", 0.4)

    def _close_settings(self):
        """关闭设置页，返回来源界面。"""
        self.settings_view = False
        self.settings_index = 0
        if self.settings_from == "pause":
            self.pause_index = 3                  # 光标停在暂停菜单的「设置」项
        self.settings_from = None

    # ---------------- 主更新 ----------------

    def update(self, input_dir=None, input_fire=False):
        """推进一帧。input_dir: 方向常量或 None；input_fire: 是否开火。"""
        self._poll_agent_preload()
        self.frame += 1
        if self.state != STATE_PAUSED:
            self._tick_effects()         # 暂停时冻结所有特效计时
        if self.state != STATE_PLAYING:
            return
        self.time_frames += 1
        self.frame_events = {"kills": 0, "player_hit": False}
        # 公告/击杀播报存活期递减
        for a in self.announcements:
            a[2] -= 1
        self.announcements = [a for a in self.announcements if a[2] > 0]
        for k in self.kill_feed:
            k[1] -= 1
        self.kill_feed = [k for k in self.kill_feed if k[1] > 0]

        # 玩家
        self.player.tick_timers()
        # 轻骑二连发：首发后间隔 burst_gap 帧自动补出第二发
        if self.burst_left > 0:
            self.burst_timer -= 1
            if self.burst_timer <= 0:
                self.burst_left -= 1
                self.burst_timer = self.player.burst_gap
                if self.player.alive:
                    # 第二发忽略主冷却与换弹（扳机时已确认有弹），冷却从第二发重新计
                    self._fire_bullet(self.player.bullet_frames,
                                      ignore_cooldown=True, ignore_reload=True,
                                      consume_ammo=False,
                                      target=self._auto_target(self.player))
        if input_dir is not None:
            self.player.set_direction(input_dir)
            self.move_tank(self.player)
        if input_fire:
            self.player_fire()

        # AI 对手（DQN 驱动；1 命制，血尽即淘汰不复活）；跑图模式靶子静止不动
        for foe in self.enemies:
            if foe.alive:
                foe.tick_timers()
                if foe.fan_flash > 0:
                    foe.fan_flash -= 1
                if self.battle_mode != "roam":
                    self._versus_foe_update(foe)

        if self.battle_mode == "versus":        # 毒圈/道具/空投仅对战模式
            self._update_items()
            self._update_zone()
        self._update_bullets()
        now_in_forest = self.in_forest(self.player)
        if self.player.alive and now_in_forest and not self.was_in_forest:
            self.rings.append({"x": self.player.x + S.TANK_SIZE / 2,
                               "y": self.player.y + S.TANK_SIZE / 2,
                               "timer": 18, "total": 18, "r0": 12, "r1": 28,
                               "w": 1, "color": S.GREEN})
        self.was_in_forest = now_in_forest
        self._update_explosions()
        self._check_win()
        # 跑图：靶子全灭后自动重建
        if (self.battle_mode == "roam" and self.versus_foes
                and all(not f.alive for f in self.versus_foes)):
            self.add_announce(T("roam_reset"), S.GREEN)
            self.versus_foes.clear()             # 清掉尸体再重建
            self.enemies.clear()
            self._spawn_roam_dummies()

    def add_announce(self, text, color=None, seconds=2.5):
        """加入一条公告（HUD 下方居中显示）。"""
        self.announcements.append([text, color or S.RED, int(seconds * 60)])

    def add_kill_feed(self, killer, victim):
        """击杀播报：右上角滚动，每条 4s；条目携带双方名字供头像反查。"""
        self.kill_feed.append([f"{killer} 淘汰了 {victim}", 240, killer, victim])

    def _tick_effects(self):
        """统一推进表现层对象；所有对象到寿命立即回收。"""
        if self.shake > 0:
            self.shake -= 1
            if self.shake == 0:
                self.shake_total = self.shake_max = 0
        if self.whiteout > 0:
            self.whiteout -= 1
        if self.fan_flash > 0:
            self.fan_flash -= 1
        for f in self.flashes:
            f["timer"] -= 1
        self.flashes = [f for f in self.flashes if f["timer"] > 0]
        for r in self.rings:
            if r.get("delay", 0) > 0:
                r["delay"] -= 1
            else:
                r["timer"] -= 1
        self.rings = [r for r in self.rings if r["timer"] > 0]
        for m in self.muzzles:
            m["timer"] -= 1
        self.muzzles = [m for m in self.muzzles if m["timer"] > 0]
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if not p.done]
        for a in self.afterimages:
            a.update()
        self.afterimages = [a for a in self.afterimages if not a.done]

    def _add_flash(self, rect):
        """在指定矩形上叠加 2 帧白色闪光。"""
        self.flashes.append({"rect": pygame.Rect(rect), "timer": 2})

    def _effect_visible(self, x, y):
        """特效可见性：排位视野外与草外看草内均隐藏。"""
        if self.battle_mode != "versus" or not self.player.alive:
            return True
        pcx = self.player.x + S.TANK_SIZE / 2
        pcy = self.player.y + S.TANK_SIZE / 2
        if math.hypot(x - pcx, y - pcy) > self.view_radius * S.TILE_SIZE:
            return False
        col, row = int(x // S.TILE_SIZE), int(y // S.TILE_SIZE)
        if 0 <= col < S.MAP_COLS and 0 <= row < S.MAP_ROWS:
            return self.grid[row][col] != S.FOREST or self.in_forest(self.player)
        return True

    def _set_shake(self, frames, amplitude):
        """保留更强的当前震屏，新震屏随剩余帧线性衰减。"""
        if self.shake > 0 and (amplitude < self.shake_max
                               or (amplitude == self.shake_max and frames < self.shake)):
            return
        self.shake = self.shake_total = frames
        self.shake_max = amplitude

    def _emit_particles(self, x, y, count, colors, life=(8, 12), speed=(0.4, 1.4),
                        direction=None, spread=math.pi, sizes=(1, 2), behind=False):
        """发射无碰撞像素粒子，并按上限淘汰最旧对象。"""
        for _ in range(count):
            angle = (self.fx_rng.uniform(0, math.tau) if direction is None
                     else direction + self.fx_rng.uniform(-spread, spread))
            velocity = self.fx_rng.uniform(*speed)
            self.particles.append(PixelParticle(
                x, y, math.cos(angle) * velocity, math.sin(angle) * velocity,
                self.fx_rng.choice(colors), self.fx_rng.randint(*sizes),
                self.fx_rng.randint(*life), behind))
        overflow = len(self.particles) - S.FX_MAX_PARTICLES
        if overflow > 0:
            del self.particles[:overflow]

    def _spawn_muzzle(self, tank, piercing=False):
        """在炮口世界坐标生成短促白黄火焰。"""
        dx, dy = S.DIR_VECTORS[tank.direction]
        self.muzzles.append({
            "x": tank.x + S.TANK_SIZE / 2 + dx * S.TANK_SIZE / 2,
            "y": tank.y + S.TANK_SIZE / 2 + dy * S.TANK_SIZE / 2,
            "direction": tank.direction, "piercing": piercing,
            "timer": 4 if piercing else 3,
        })

    def _spawn_hit_effect(self, tank, lethal, source="bullet", direction=None):
        """区分普通命中、毒圈每跳与淘汰爆燃。"""
        x = tank.x + S.TANK_SIZE / 2
        y = tank.y + S.TANK_SIZE / 2
        self._add_flash(tank.rect)
        if lethal:
            self.explosions.append(Explosion(x, y, "kill"))
            self._emit_particles(x, y, 12, ((255, 210, 90), (240, 140, 40), (180, 60, 35)),
                                 life=(14, 24), speed=(0.5, 2.0))
            if self._effect_visible(x, y):
                self._set_shake(6, 4)
            return
        if source == "zone":
            self._emit_particles(x, y, 8, (FX_ZONE, (255, 100, 60)),
                                 life=(10, 10), speed=(0.7, 1.6))
            return
        self.explosions.append(Explosion(x, y, "hit"))
        angle = None
        if direction is not None:
            dx, dy = S.DIR_VECTORS[direction]
            angle = math.atan2(dy, dx)
        self._emit_particles(x, y, 6, ((255, 255, 255), (250, 220, 90), (240, 140, 40)),
                             life=(8, 12), speed=(0.6, 1.8),
                             direction=angle, spread=0.85)

    def _spawn_tile_effect(self, tile, col, row, x=None, y=None):
        """砖墙掉砖屑，钢板只溅灰白火花。"""
        cx = col * S.TILE_SIZE + S.TILE_SIZE / 2 if x is None else x
        cy = row * S.TILE_SIZE + S.TILE_SIZE / 2 if y is None else y
        if tile == S.BRICK:
            self._emit_particles(cx, cy, 6, (FX_BRICK, FX_BRICK_LIGHT, (110, 45, 28)),
                                 life=(12, 18), speed=(0.4, 1.5))
        elif tile == S.STEEL:
            self._emit_particles(cx, cy, 4, (FX_STEEL, S.WHITE),
                                 life=(6, 10), speed=(0.5, 1.6), sizes=(1, 1))

    def _spawn_absorb(self, tank):
        """无敌吸收：青白小环，不进入扣血与计分链。"""
        self.rings.append({"x": tank.x + S.TANK_SIZE / 2, "y": tank.y + S.TANK_SIZE / 2,
                           "timer": 6, "total": 6, "r0": 8, "r1": 13,
                           "w": 1, "color": (168, 216, 255)})

    def _spawn_pickup_effect(self, tank, kind):
        """按道具类型生成小环与 4 枚像素点。"""
        color = {"heal": S.GREEN, "fire": S.YELLOW, "shield": FX_DASH}[kind]
        x, y = tank.x + S.TANK_SIZE / 2, tank.y + S.TANK_SIZE / 2
        self.rings.append({"x": x, "y": y, "timer": 12, "total": 12,
                           "r0": 6, "r1": 18, "w": 1, "color": color})
        self._emit_particles(x, y, 4, (color, S.WHITE), life=(12, 12), speed=(0.5, 1.1))

    # ---------------- 移动与碰撞 ----------------

    def move_tank(self, tank):
        """按坦克当前朝向移动一格速度，被阻挡返回 False。"""
        if not tank.alive:
            return False
        dx, dy = S.DIR_VECTORS[tank.direction]
        nx = tank.x + dx * tank.speed
        ny = tank.y + dy * tank.speed
        map_px = S.TILE_SIZE * S.MAP_ROWS
        if nx < 0 or ny < 0 or nx > S.SCREEN_WIDTH - S.TANK_SIZE or ny > map_px - S.TANK_SIZE:
            return False
        rect = pygame.Rect(int(nx), int(ny), S.TANK_SIZE, S.TANK_SIZE)
        if self.rect_hits_tiles(rect, S.TANK_BLOCK):
            return False
        if self._rect_hits_tank(rect, exclude=tank):
            return False
        tank.x, tank.y = nx, ny
        return True

    def rect_hits_tiles(self, rect, tile_types):
        c0 = max(rect.left // S.TILE_SIZE, 0)
        c1 = min((rect.right - 1) // S.TILE_SIZE, S.MAP_COLS - 1)
        r0 = max(rect.top // S.TILE_SIZE, 0)
        r1 = min((rect.bottom - 1) // S.TILE_SIZE, S.MAP_ROWS - 1)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if self.grid[r][c] in tile_types:
                    return True
        return False

    def _rect_hits_tank(self, rect, exclude=None):
        if self.player.alive and self.player is not exclude and rect.colliderect(self.player.rect):
            return True
        for e in self.enemies:
            if e.alive and e is not exclude and rect.colliderect(e.rect):
                return True
        return False

    # ---------------- 开火 ----------------

    def player_fire(self, piercing=False):
        """J 普攻：single=单发 / burst=二连发 / fan=扇形冲击，自动瞄准追踪。
        piercing=True 仅供 K 技能调用：穿甲弹沿车头直线，使用独立技能冷却。"""
        if self.state != STATE_PLAYING:
            return
        if piercing:
            if self.player.skill_cooldown > 0 or self.player.reload_timer > 0:
                return
            self._fire_bullet(self.player.piercing_frames, piercing=True,
                              ignore_cooldown=True, consume_ammo=False, target=None)
            return
        target = self._auto_target(self.player)
        if target is not None:
            self.player.set_direction(self._aim_direction(self.player, target))
        mode = self.player.fire_mode
        if mode == "fan":
            self._fan_fire(self.player)
        elif mode == "burst":
            if self._fire_bullet(self.player.bullet_frames, target=target):
                self.burst_left = 1                     # 第二发由 update 间隔补出
                self.burst_timer = self.player.burst_gap
        else:
            self._fire_bullet(self.player.bullet_frames, target=target)

    def _fire_bullet(self, max_frames, piercing=False, ignore_cooldown=False,
                     ignore_reload=False, consume_ammo=True, target=None):
        """发射一发实体弹（弹上限/冷却/换弹检查），成功返回 True。
        ignore_cooldown=True 用于二连发补弹：跳过主冷却检查。
        ignore_reload=True：补发不检查换弹（扳机时已确认有弹）。
        consume_ammo=False：技能等不消耗弹匣的射击（换弹门禁仍生效）。
        target：锁定的追踪目标（None=直线飞）。"""
        active = sum(1 for b in self.bullets if b.alive and b.from_player)
        if not self.player.alive or active >= self.player.max_bullets:
            return False
        if not ignore_cooldown and self.player.fire_cooldown > 0:
            return False
        if not ignore_reload and self.player.reload_timer > 0:
            return False                                # 换弹中禁射
        self.player.fire_cooldown_max = self.player.base_fire_cooldown
        b = self.player.make_bullet(piercing, max_frames, target)
        b.owner = self.player                  # 对战模式按 owner 判定命中与归属
        self.bullets.append(b)
        self._spawn_muzzle(self.player, piercing)
        if consume_ammo:
            self._consume_ammo(self.player)
        self.audio.play("shoot_" + self.player.tank_type, 0.7)
        return True

    def _fan_fire(self, tank=None):
        """扇形冲击：对范围内坦克造成普攻伤害并摧毁砖墙。
        与子弹规则一致：不伤基地；钢板不受损；冲击波无视遮挡。玩家与 AI（重装）共用。
        弹匣：释放 1 次消耗 1 发，打空自动换弹（换弹中禁放）。"""
        p = tank if tank is not None else self.player
        if not p.alive or p.fire_cooldown > 0 or p.reload_timer > 0:
            return
        p.fire_cooldown_max = p.base_fire_cooldown
        p.fire_cooldown = p.fire_cooldown_max
        p.shots_fired += 1
        self._consume_ammo(p)
        self.audio.play("shoot_heavy", 0.7 if p is self.player else 0.3)
        self._spawn_muzzle(p)
        if p is self.player:
            self.fan_flash = 8
        else:
            p.fan_flash = 8

        px = p.x + S.TANK_SIZE / 2
        py = p.y + S.TANK_SIZE / 2
        fx, fy = S.DIR_VECTORS[p.direction]
        cos_limit = math.cos(math.radians(p.fan_half_angle))
        self._blast_damage(p, px, py, fx, fy, p.fan_radius, cos_limit, p.attack_damage)

    def _blast_damage(self, attacker, px, py, fx, fy, radius, cos_limit, damage):
        """范围伤害核心：中心 (px,py)，朝向 (fx,fy)；cos_limit=-1 时为全向（冲击波复用）。
        按 damage 伤害 attacker 之外的活坦克；有效命中走计分/播报链 + 毁砖；
        不伤基地、不毁钢板、无视遮挡。"""
        killer = self.player_name if attacker is self.player else attacker.tag

        def in_blast(cx, cy):
            vx, vy = cx - px, cy - py
            dist = math.hypot(vx, vy)
            if dist > radius:
                return False
            if dist == 0:
                return True
            return (vx * fx + vy * fy) / dist >= cos_limit

        for t in ([self.player] + self.versus_foes if attacker is self.player
                  else [self.player]):
            if not t.alive or t is attacker \
                    or not in_blast(t.x + S.TANK_SIZE / 2, t.y + S.TANK_SIZE / 2):
                continue
            if t.invincible > 0:
                self._spawn_absorb(t)
                continue
            if t is self.player:
                self._on_player_hit(attacker.direction, damage, killer=killer)
            else:
                self._damage_foe(t, attacker is self.player,
                                 attacker.direction, damage, killer=killer)
            attacker.hits_landed += 1
        for r in range(S.MAP_ROWS):
            for c in range(S.MAP_COLS):
                if self.grid[r][c] == S.BRICK and in_blast(c * S.TILE_SIZE + S.TILE_SIZE / 2,
                                                           r * S.TILE_SIZE + S.TILE_SIZE / 2):
                    self.grid[r][c] = S.EMPTY
                    self._add_flash(pygame.Rect(c * S.TILE_SIZE, r * S.TILE_SIZE,
                                                S.TILE_SIZE, S.TILE_SIZE))
                    self._spawn_tile_effect(S.BRICK, c, r)

    def player_skill(self):
        """K 键立即释放型号技能：标准=穿甲弹 / 轻骑=疾冲 / 重装=冲击波。"""
        p = self.player
        if self.state != STATE_PLAYING or not p.alive:
            return
        if p.skill == "dash":
            self._dash(p)
        elif p.skill_cooldown <= 0 and p.reload_timer <= 0:
            if p.skill == "shockwave":
                self._shockwave(p)
            else:
                self.player_fire(piercing=True)

    def _dash(self, tank=None):
        """技能·冲锋疾冲（轻骑）：无伤穿过坦克和钢板、撞碎砖墙，最多前进 dash_tiles 格。
        河/基地/边界挡停；终点在坦克或钢板内时回退到最近安全位置。玩家与 AI 共用。"""
        p = tank if tank is not None else self.player
        if not p.alive or p.dash_charges <= 0:
            return
        dx, dy = S.DIR_VECTORS[p.direction]
        max_dist = p.dash_tiles * S.TILE_SIZE
        map_px = S.TILE_SIZE * S.MAP_ROWS
        moved = 0
        start_x, start_y = p.x, p.y
        last_clear = (p.x, p.y)
        afterimage_path = []
        while moved < max_dist:
            nx = p.x + dx * 4
            ny = p.y + dy * 4
            if nx < 0 or ny < 0 or nx > S.SCREEN_WIDTH - S.TANK_SIZE or ny > map_px - S.TANK_SIZE:
                break
            rect = pygame.Rect(int(nx), int(ny), S.TANK_SIZE, S.TANK_SIZE)
            if self.rect_hits_tiles(rect, (S.RIVER, S.BASE)):
                break
            if (not self.rect_hits_tiles(rect, (S.STEEL,))
                    and not self._rect_hits_tank(rect, exclude=p)):
                last_clear = (nx, ny)   # 可穿越坦克和钢板，但记录无重叠的落点
            # 撞碎覆盖到的砖
            c0 = max(int(nx) // S.TILE_SIZE, 0)
            c1 = min((int(nx) + S.TANK_SIZE - 1) // S.TILE_SIZE, S.MAP_COLS - 1)
            r0 = max(int(ny) // S.TILE_SIZE, 0)
            r1 = min((int(ny) + S.TANK_SIZE - 1) // S.TILE_SIZE, S.MAP_ROWS - 1)
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    if self.grid[r][c] == S.BRICK:
                        self.grid[r][c] = S.EMPTY
                        self._add_flash(pygame.Rect(c * S.TILE_SIZE, r * S.TILE_SIZE,
                                                    S.TILE_SIZE, S.TILE_SIZE))
                        self._spawn_tile_effect(S.BRICK, c, r)
            p.x, p.y = nx, ny
            moved += 4
            if moved % 8 == 0:
                afterimage_path.append((p.x, p.y))
        if (self._rect_hits_tank(p.rect, exclude=p)
                or self.rect_hits_tiles(p.rect, (S.STEEL,))):
            p.x, p.y = last_clear
        if moved > 0:
            p.dash_charges -= 1
            if p.dash_recharge <= 0:
                p.dash_recharge = p.skill_cooldown_max
            self.audio.play("shoot", 0.7)
            sprite = get_sprites().player_tanks[p.tank_type][p.direction]
            for ax, ay in afterimage_path[-6:]:
                self.afterimages.append(Afterimage(sprite, ax, ay, FX_DASH))
            overflow = len(self.afterimages) - S.FX_MAX_AFTERIMAGES
            if overflow > 0:
                del self.afterimages[:overflow]
            self._emit_particles(start_x + S.TANK_SIZE / 2, start_y + S.TANK_SIZE / 2,
                                 4, (FX_DASH, S.LIGHT_GRAY), life=(8, 12),
                                 speed=(0.2, 0.8), behind=True)
            self.rings.append({"x": p.x + S.TANK_SIZE / 2, "y": p.y + S.TANK_SIZE / 2,
                               "timer": 8, "total": 8, "r0": 14, "r1": 26,
                               "w": 2, "color": FX_DASH})

    def _shockwave(self, tank=None):
        """技能·全向冲击波（重装）：360° 范围伤害，半径 shock_radius（2 格），规则同扇形。"""
        p = tank if tank is not None else self.player
        if not p.alive:
            return
        p.skill_cooldown = p.skill_cooldown_max
        p.shots_fired += 1
        self.audio.play("explosion", 0.9 if p is self.player else 0.5)
        px = p.x + S.TANK_SIZE / 2
        py = p.y + S.TANK_SIZE / 2
        if self._effect_visible(px, py):
            self._set_shake(4, 2)
        fx, fy = S.DIR_VECTORS[p.direction]
        self._blast_damage(p, px, py, fx, fy, p.shock_radius, -1.0, p.skill_damage)  # 全向
        self.rings.append({"x": px, "y": py, "timer": 12, "total": 12,
                           "r0": 20, "r1": p.shock_radius, "w": 3, "color": S.YELLOW})
        self.rings.append({"x": px, "y": py, "timer": 9, "total": 9, "delay": 3,
                           "r0": 8, "r1": p.shock_radius - 8, "w": 1,
                           "color": (255, 240, 170)})
        self._emit_particles(px, py, 8, (S.YELLOW, S.WHITE), life=(12, 12),
                             speed=(1.2, 2.2), sizes=(1, 2))

    # ---------------- 对战模式（DQN 驱动的 FFA 对手） ----------------

    def _versus_foe_update(self, foe):
        """每 FRAME_SKIP 帧决策一次，决策间重复执行该动作。

        对手驱动：foe_agent（自博弈训练注入，共享 ε）优先，否则 dqn_agent（ε=0）；
        两者都没有时 foe 原地不动（防御性）。
        """
        agent = self.foe_agent or self.dqn_agent
        if agent is None:
            return
        if self.frame % S.FRAME_SKIP == 0:
            eps = self.foe_epsilon if self.foe_agent is not None else 0.0
            foes = [self.player] + [f for f in self.versus_foes if f is not foe]
            obs = self._build_foe_state(self, foe, foes)
            foe.vs_action = self._decode_vs_action(agent.act(obs, eps))
        direction, fire = foe.vs_action
        if self.foe_agent is None and S.FOE_GUIDE:
            direction, fire = self._foe_guide(foe, direction, fire)
        if direction is not None:
            foe.set_direction(direction)
            self.move_tank(foe)
        if fire:
            self._versus_foe_fire(foe)
        # 轻骑 AI 二连发补发（同玩家 burst_gap 节奏；忽略主冷却与换弹，扳机时已确认有弹）
        if foe.burst_pending > 0:
            foe.burst_timer -= 1
            if foe.burst_timer <= 0:
                foe.burst_pending = 0
                if foe.alive:
                    self._foe_fire_bullet(foe, foe.bullet_frames,
                                          ignore_cooldown=True, ignore_reload=True,
                                          consume_ammo=False,
                                          target=self._auto_target(foe))
        # 规则触发技能（冷却好 + 目标在技能范围内）
        self._foe_try_skill(foe)

    def _versus_foe_fire(self, foe):
        """AI 开火：按型号分流（single=单发 / burst=二连发 / fan=扇形冲击）。
        自动攻击：射程圈内有可视敌人时车头自动转向最近目标，子弹锁定追踪（与玩家同规则）。"""
        target = self._auto_target(foe)
        if target is not None:
            foe.set_direction(self._aim_direction(foe, target))
        if foe.fire_mode == "fan":
            self._fan_fire(foe)
        elif foe.fire_mode == "burst":
            if self._foe_fire_bullet(foe, foe.bullet_frames, target=target):
                foe.burst_pending = 1
                foe.burst_timer = foe.burst_gap
        else:
            self._foe_fire_bullet(foe, foe.bullet_frames, target=target)

    def _foe_fire_bullet(self, foe, max_frames=None, piercing=False, ignore_cooldown=False,
                         ignore_reload=False, consume_ammo=True, target=None):
        """AI 发射一发实体弹（弹上限/冷却/换弹检查，与玩家 _fire_bullet 同规则）。
        target：锁定的追踪目标（None=直线飞）；AI_BULLET_HOMING=False 时一律直飞。"""
        if not S.AI_BULLET_HOMING:
            target = None
        active = sum(1 for b in self.bullets if b.alive and b.owner is foe)
        if not foe.alive or active >= foe.max_bullets:
            return False
        if not ignore_cooldown and foe.fire_cooldown > 0:
            return False
        if not ignore_reload and foe.reload_timer > 0:
            return False                                # 换弹中禁射
        foe.fire_cooldown_max = foe.base_fire_cooldown
        b = foe.make_bullet(piercing, max_frames, target)
        b.from_player = False
        b.owner = foe
        self.bullets.append(b)
        self._spawn_muzzle(foe, piercing)
        if consume_ammo:
            self._consume_ammo(foe)
        self.audio.play("shoot_" + foe.tank_type, 0.3)
        return True

    def _tank_visible(self, seer, target):
        """几何可见性（玩家/AI 通用）：圆形视野 + 草地单向隐身。

        玩家视野半径取设置里的「视野」（4-10 格），AI 固定默认值（不改训练平衡）。
        """
        vx = target.x + S.TANK_SIZE / 2 - (seer.x + S.TANK_SIZE / 2)
        vy = target.y + S.TANK_SIZE / 2 - (seer.y + S.TANK_SIZE / 2)
        radius = self.view_radius if seer is self.player else S.VIEW_RADIUS_TILES
        if math.hypot(vx, vy) > radius * S.TILE_SIZE:
            return False
        if self.in_forest(target) and not self.in_forest(seer):
            return False          # 目标在草里、自身在草外 → 隐身
        return True

    def _auto_target(self, tank):
        """自动攻击目标：射程内最近的可视敌人（排除无敌期目标），无则 None。
        射程：fan=扇形半径；其余=普弹射程（bullet_frames*5）。"""
        rng = tank.fan_radius if tank.fire_mode == "fan" else (tank.bullet_frames or 0) * 5
        best, best_d = None, 1e9
        # 两阵营：AI 只锁定玩家（不与队友互射），玩家锁定全部 AI
        pool = [self.player] + self.versus_foes if tank is self.player else [self.player]
        for t in pool:
            if t is tank or not t.alive or t.invincible > 0:
                continue
            d = math.hypot(t.x + S.TANK_SIZE / 2 - (tank.x + S.TANK_SIZE / 2),
                           t.y + S.TANK_SIZE / 2 - (tank.y + S.TANK_SIZE / 2))
            if d <= rng and d < best_d and self._tank_visible(tank, t):
                best, best_d = t, d
        return best

    def _aim_direction(self, tank, target):
        """朝目标的 4 方向：主轴优先（|dx|>=|dy| 取水平），同 _foe_step_to_center 规则。"""
        dx = target.x - tank.x
        dy = target.y - tank.y
        if abs(dx) >= abs(dy):
            return S.RIGHT if dx > 0 else S.LEFT
        return S.DOWN if dy > 0 else S.UP

    def _consume_ammo(self, tank):
        """消耗 1 发弹匣；打空自动开始换弹（换弹完成由 tick_timers 补满）。"""
        tank.mag -= 1
        if tank.mag <= 0:
            tank.mag = 0
            tank.reload_timer = tank.reload_frames

    def _foe_step_to_center(self, foe):
        """选一个朝地图中心 (8,8) 且可通行的 4 方向（|dy|/|dx| 大者优先）；全被挡返回 None。"""
        cx = min(int((foe.x + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_COLS - 1)
        cy = min(int((foe.y + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_ROWS - 1)
        dy, dx = 8 - cy, 8 - cx
        primary = (S.DOWN if dy > 0 else S.UP) if abs(dy) >= abs(dx) \
            else (S.RIGHT if dx > 0 else S.LEFT)
        secondary = (S.RIGHT if dx > 0 else S.LEFT) if abs(dy) >= abs(dx) \
            else (S.DOWN if dy > 0 else S.UP)
        for d in (primary, secondary):
            ddx, ddy = S.DIR_VECTORS[d]
            nr, nc = cy + ddy, cx + ddx
            if 0 <= nr < S.MAP_ROWS and 0 <= nc < S.MAP_COLS \
                    and self.grid[nr][nc] not in (S.BRICK, S.STEEL):
                return d
        return None

    def _foe_guide(self, foe, direction, fire):
        """玩家局 AI 策略引导（训练自博弈 foe_agent 注入时不走这里）：
        1) 躲毒圈最高优先：出界或下一圈将出界 → 朝中心撤
        2) 开火门控：视野内无目标在自身射程内 → 不开火（不浪费弹/不暴露）
        3) 中心趋远期：圈内安全、未接战、DQN 方向偏离中心 → 拉回中心"""
        cx = min(int((foe.x + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_COLS - 1)
        cy = min(int((foe.y + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_ROWS - 1)
        cheb = max(abs(cy - 8), abs(cx - 8))

        # 1) 躲毒圈：出界，或下一圈半径下将出界（提前一格撤）
        if self.zone_radius > 0 and cheb >= self.zone_radius:
            step = self._foe_step_to_center(foe)
            if step is not None:
                return step, fire

        # 对手可见性/最近可见距离
        foes = [t for t in [self.player] + self.versus_foes
                if t is not foe and t.alive and t.invincible <= 0]
        near_px = None
        for t in foes:
            if self._tank_visible(foe, t):
                d = math.hypot(t.x + S.TANK_SIZE / 2 - (foe.x + S.TANK_SIZE / 2),
                               t.y + S.TANK_SIZE / 2 - (foe.y + S.TANK_SIZE / 2))
                if near_px is None or d < near_px:
                    near_px = d

        # 2) 开火门控：可见目标须进入自身射程的 80%（留反应与走位空间）
        if fire:
            rng = foe.fan_radius if foe.fire_mode == "fan" else foe.bullet_frames * 5
            if near_px is None or near_px > rng * S.AI_FIRE_RANGE_RATIO:
                fire = False

        # 3) 中心趋近：圈内安全、未接战（无可视敌或距离 > 4 格）、cheb > 5 且当前方向增大中心距离
        if direction is not None and (near_px is None or near_px > 4 * S.TILE_SIZE) \
                and cheb > 5 and self.zone_radius > 0 and cheb < self.zone_radius:
            ddx, ddy = S.DIR_VECTORS[direction]
            nc, nr = cx + ddx, cy + ddy
            if 0 <= nr < S.MAP_ROWS and 0 <= nc < S.MAP_COLS \
                    and max(abs(nr - 8), abs(nc - 8)) > cheb:
                step = self._foe_step_to_center(foe)
                if step is not None:
                    direction = step
        return direction, fire

    def _foe_try_skill(self, foe):
        """AI 规则瞬发技能：standard=穿甲 / scout=疾冲 / heavy=冲击波。"""
        skill = foe.skill
        if not foe.alive:
            return
        if skill == "dash":
            if foe.dash_charges <= 0:
                return
        elif foe.skill_cooldown > 0:
            return
        cx = foe.x + S.TANK_SIZE / 2
        cy = foe.y + S.TANK_SIZE / 2
        # 两阵营：AI 的技能只针对玩家
        targets = [t for t in [self.player]
                   if t.alive and t.invincible <= 0]
        if not targets:
            return
        best, best_d = None, 1e9
        for t in targets:
            d = math.hypot(t.x + S.TANK_SIZE / 2 - cx, t.y + S.TANK_SIZE / 2 - cy)
            if d < best_d:
                best, best_d = t, d
        reloading = foe.reload_timer > 0             # 换弹中禁射击型技能（dash 逃生不受限）
        if skill == "piercing":                      # standard：8 格穿甲弹（不耗弹匣）
            if not reloading and best_d <= 8 * S.TILE_SIZE * S.AI_FIRE_RANGE_RATIO:
                self._foe_fire_bullet(foe, foe.piercing_frames, piercing=True,
                                      ignore_cooldown=True, consume_ammo=False)
        elif skill == "dash":                        # scout：2 格内且朝向对准（60° 半角）
            fx, fy = S.DIR_VECTORS[foe.direction]
            if not self._in_zone(foe):               # 毒圈逃生优先：出界且朝向对准中心 → 冲锋撤离
                vx = 8 * S.TILE_SIZE - cx
                vy = 8 * S.TILE_SIZE - cy
                vd = math.hypot(vx, vy)
                if (vx * fx + vy * fy) / max(vd, 1e-6) >= 0.5:
                    self._dash(foe)
                    return
            if best is not None and best_d <= foe.dash_tiles * S.TILE_SIZE * S.AI_FIRE_RANGE_RATIO:
                vx = best.x + S.TANK_SIZE / 2 - cx
                vy = best.y + S.TANK_SIZE / 2 - cy
                if (vx * fx + vy * fy) / max(best_d, 1e-6) >= 0.5:
                    self._dash(foe)
        elif skill == "shockwave":                   # heavy：2 格内贴脸反打
            if not reloading and best_d <= foe.shock_radius * S.AI_FIRE_RANGE_RATIO:
                self._shockwave(foe)

    # ---------------- 道具 ----------------

    def _update_items(self):
        """道具三路推进：定时刷 -> ttl 衰减 -> 坦克触碰结算。"""
        self.item_timer -= 1
        if self.item_timer <= 0:
            self.item_timer = S.ITEM_SPAWN_INTERVAL
            timed = sum(1 for it in self.items if it.source == "timed" and it.alive)
            if timed < S.ITEM_MAX_TIMED and len(self.items) < S.MAX_ITEMS:
                self._spawn_item(random.choice(S.ITEM_TYPES), source="timed")

        for it in self.items:
            it.ttl -= 1
            if it.ttl <= 0:
                it.alive = False
        self.items = [it for it in self.items if it.alive]

        for t in [self.player] + self.versus_foes:
            if not t.alive:
                continue
            for it in self.items:
                if not it.alive or not it.rect.colliderect(t.rect):
                    continue
                if it.kind == "mine":
                    if t.invincible > 0:        # 护盾/出生保护期免疫地雷
                        continue
                    it.alive = False
                    if t is self.player:
                        self._on_player_hit(None, S.MINE_DAMAGE, killer="地雷")
                    else:
                        self._damage_foe(t, by_player=False, direction=None,
                                         damage=S.MINE_DAMAGE, killer="地雷")
                else:
                    it.alive = False
                    self._apply_item(t, it.kind)
                    self._spawn_pickup_effect(t, it.kind)
                    self.audio.play("pickup", 0.5)
        self.items = [it for it in self.items if it.alive]

    def _spawn_item(self, kind, source, col=None, row=None):
        """在指定格或随机空格生成道具。随机格要求 EMPTY、无坦克/道具重叠。"""
        if col is None or row is None:
            empty = [(c, r) for r in range(S.MAP_ROWS) for c in range(S.MAP_COLS)
                     if self.grid[r][c] == S.EMPTY]
            random.shuffle(empty)
            for c, r in empty:
                rect = pygame.Rect(c * S.TILE_SIZE + 8, r * S.TILE_SIZE + 8, 16, 16)
                if any(t.alive and t.rect.colliderect(rect)
                       for t in [self.player] + self.versus_foes):
                    continue
                if any(it.alive and it.rect.colliderect(rect) for it in self.items):
                    continue
                col, row = c, r
                break
            else:
                return          # 无空格可刷，本轮放弃
        item = Item(col, row, kind, S.ITEM_TTL)
        item.source = source    # "timed" 定时刷 / "drop" 击杀掉落
        self.items.append(item)

    def _drop_item(self, foe):
        """击杀掉落：死亡格掉一个 heal/fire/shield；场上已有掉落则顶掉旧的。仅对战模式。"""
        if self.battle_mode != "versus" or not S.ITEM_DROP_TYPES:
            return
        self.items = [it for it in self.items if it.source != "drop"]
        col = min(int((foe.x + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_COLS - 1)
        row = min(int((foe.y + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_ROWS - 1)
        self._spawn_item(random.choice(S.ITEM_DROP_TYPES), source="drop", col=col, row=row)

    def _apply_item(self, tank, kind):
        """道具生效：heal 回复 34 HP / fire 冷却 ×0.7（叠 2 层）/ shield 无敌 5s。"""
        if kind == "heal":
            tank.hp = min(tank.hp + S.HEAL_HP, tank.max_hp)
        elif kind == "fire":
            tank.fire_stacks = min(tank.fire_stacks + 1, S.FIRE_MAX_STACKS)
            base = (tank.base_fire_cooldown if tank is self.player
                    else 2 * S.PLAYER_FIRE_COOLDOWN)
            tank.fire_cooldown_max = max(
                int(base * S.FIRE_COOLDOWN_SCALE ** tank.fire_stacks), S.FIRE_COOLDOWN_MIN)
        elif kind == "shield":
            tank.invincible = max(tank.invincible, S.SHIELD_FRAMES)

    # ---------------- 毒圈 ----------------

    def _in_zone(self, tank):
        """坦克中心格是否在安全区内（Chebyshev 距离 <= zone_radius）。"""
        c = int((tank.x + S.TANK_SIZE / 2) // S.TILE_SIZE)
        r = int((tank.y + S.TANK_SIZE / 2) // S.TILE_SIZE)
        ctr = S.MAP_ROWS // 2
        return max(abs(r - ctr), abs(c - ctr)) <= self.zone_radius

    def _update_zone(self):
        """毒圈逐圈收缩：安全期后每 3s 缩 1 圈，圈外按节拍扣血。"""
        if self.zone_radius > 0:
            self.zone_timer -= 1
            if not self._zone_warned and self.zone_radius == S.ZONE_INITIAL_RADIUS \
                    and self.zone_timer <= 180:
                self.add_announce("⚠ 毒圈即将收缩！")
                self._zone_warned = True
            if self.zone_timer <= 0:
                self.zone_timer = S.ZONE_SHRINK_INTERVAL
                self.zone_radius -= 1
                if self.zone_radius > 0:
                    self.add_announce(f"毒圈已收缩至 R{self.zone_radius}")
                else:
                    self.add_announce("决赛圈：只剩中心！")
        self.zone_tick = (self.zone_tick + 1) % S.ZONE_TICK_FRAMES
        if self.zone_tick != 0:
            return
        for t in [self.player] + self.versus_foes:
            if t.alive and not self._in_zone(t):
                self._zone_damage(t)

    def _zone_damage(self, tank):
        """圈外扣血：不算人头，淘汰照常爆炸 + 掉道具。"""
        tank.hp = max(0, tank.hp - S.ZONE_DAMAGE)
        self._spawn_hit_effect(tank, tank.hp <= 0, source="zone")
        if tank.hp > 0:
            return
        self.audio.play("explosion", 0.6)
        if tank is self.player:
            self.lives -= 1
            tank.alive = False
            self.lose_reason = "life"
            self.add_kill_feed("毒圈", self.player_name)
            self._end(False)
        else:
            tank.alive = False
            self.add_kill_feed("毒圈", tank.tag)
            tank.lives -= 1
            self._drop_item(tank)

    # ---------------- 子弹 ----------------

    def _update_bullets(self):
        for b in self.bullets:
            if b.alive:
                b.update()
                if b.alive and self.frame % S.FX_TRAIL_INTERVAL == 0:
                    # 尾迹位于弹体后下方，不参与碰撞与 RL 观测。
                    x = b.x + S.BULLET_SIZE / 2 - b.vx * 4
                    y = b.y + S.BULLET_SIZE / 2 - b.vy * 4
                    colors = ((255, 255, 255), (250, 220, 90)) if b.piercing else ((210, 100, 35),)
                    self._emit_particles(x, y, 1, colors, life=((8, 8) if b.piercing else (6, 6)),
                                         speed=(0, 0), sizes=((2, 2) if b.piercing else (1, 1)),
                                         behind=True)

        for b in self.bullets:
            if b.alive:
                self._bullet_vs_tiles(b)

        self._versus_bullet_hits()

        self.bullets = [b for b in self.bullets if b.alive]

    def _versus_bullet_hits(self):
        """对战模式子弹规则：owner 不同的子弹相撞互消；子弹打敌人（AI 子弹穿过 AI，不互伤）。"""
        for i, a in enumerate(self.bullets):
            if not a.alive:
                continue
            for b in self.bullets[i + 1:]:
                if b.alive and a.owner is not b.owner and a.rect.colliderect(b.rect):
                    x = (a.x + b.x) / 2 + S.BULLET_SIZE / 2
                    y = (a.y + b.y) / 2 + S.BULLET_SIZE / 2
                    a.alive = b.alive = False
                    self.rings.append({"x": x, "y": y, "timer": 6, "total": 6,
                                       "r0": 1, "r1": 5, "w": 1, "color": S.WHITE})
                    self._emit_particles(x, y, 4, (S.WHITE, S.YELLOW), life=(6, 6),
                                         speed=(0.2, 0.8), sizes=(1, 1))
                    break

        for b in self.bullets:
            if not b.alive:
                continue
            for t in [self.player] + self.versus_foes:
                if not b.alive:
                    break
                if not t.alive or t is b.owner or not b.rect.colliderect(t.rect):
                    continue
                if b.owner is not self.player and t is not self.player:
                    continue                       # 同阵营（AI 之间）：子弹直接穿过，不互伤
                if t.invincible > 0:               # 无敌期吸收普通弹，穿甲弹穿过
                    if not b.piercing:
                        b.alive = False
                        self._spawn_absorb(t)
                    continue
                if t is self.player:
                    b.alive = False
                    if b.owner is not None:
                        b.owner.hits_landed += 1
                    self._on_player_hit(b.direction, b.damage,
                                        killer=b.owner.tag if b.owner is not self.player else self.player_name)
                else:
                    self._damage_foe(t, by_player=b.owner is self.player, direction=b.direction,
                                     damage=b.damage,
                                     killer=b.owner.tag if b.owner is not self.player else self.player_name)
                    if b.owner is not None:
                        b.owner.hits_landed += 1
                    if not b.piercing:
                        b.alive = False

    def _bullet_vs_tiles(self, bullet):
        rect = bullet.rect
        c0 = max(rect.left // S.TILE_SIZE, 0)
        c1 = min((rect.right - 1) // S.TILE_SIZE, S.MAP_COLS - 1)
        r0 = max(rect.top // S.TILE_SIZE, 0)
        r1 = min((rect.bottom - 1) // S.TILE_SIZE, S.MAP_ROWS - 1)
        hit = False
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                tile = self.grid[r][c]
                if tile == S.BRICK:
                    self.grid[r][c] = S.EMPTY   # 砖墙被打掉
                    self._add_flash(pygame.Rect(c * S.TILE_SIZE, r * S.TILE_SIZE,
                                                S.TILE_SIZE, S.TILE_SIZE))
                    self._spawn_tile_effect(tile, c, r, bullet.x + S.BULLET_SIZE / 2,
                                            bullet.y + S.BULLET_SIZE / 2)
                    hit = hit or not bullet.piercing   # 穿甲弹毁砖但继续飞
                elif tile == S.STEEL:
                    self._spawn_tile_effect(tile, c, r, bullet.x + S.BULLET_SIZE / 2,
                                            bullet.y + S.BULLET_SIZE / 2)
                    hit = True
        if hit:
            bullet.alive = False

    # ---------------- 事件处理 ----------------

    def in_forest(self, tank):
        """坦克中心所在格是否为草地。"""
        c = min(int((tank.x + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_COLS - 1)
        r = min(int((tank.y + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_ROWS - 1)
        return self.grid[r][c] == S.FOREST

    def _knockback(self, tank, direction, dist=S.HIT_KNOCKBACK):
        """沿 direction 击退 dist 像素；撞地形/其他坦克则放弃（不做部分位移）。"""
        dx, dy = S.DIR_VECTORS[direction]
        nx, ny = tank.x + dx * dist, tank.y + dy * dist
        if (nx < 0 or ny < 0 or nx > S.SCREEN_WIDTH - S.TANK_SIZE
                or ny > S.TILE_SIZE * S.MAP_ROWS - S.TANK_SIZE):
            return
        rect = pygame.Rect(int(nx), int(ny), S.TANK_SIZE, S.TANK_SIZE)
        if self.rect_hits_tiles(rect, (S.STEEL, S.RIVER, S.BASE)):
            return
        if self._rect_hits_tank(rect, exclude=tank):
            return
        tank.x, tank.y = nx, ny

    def _damage_foe(self, foe, by_player, direction, damage, killer=None):
        """AI 受击：按来源扣 HP；归零后淘汰并掉落道具。"""
        foe.hp = max(0, foe.hp - damage)
        self._spawn_hit_effect(foe, foe.hp <= 0, direction=direction)
        self.audio.play("hit" if foe.hp > 0 else "kill", 0.55 if foe.hp > 0 else 0.75)
        if by_player:
            self.score += S.SCORE_KILL          # 每次有效命中 +100 分
        if foe.hp > 0:
            foe.invincible = S.HIT_INVINCIBLE
            if direction is not None:
                self._knockback(foe, direction)
            return
        # 血量归零 -> 淘汰（1 命制，不复活），死亡格掉落道具
        foe.alive = False
        if by_player:
            self.kills += 1                     # 击杀数只统计淘汰
        foe.lives -= 1
        self._drop_item(foe)
        self.add_kill_feed(killer or (self.player_name if by_player else "对手"), foe.tag)

    def _on_player_hit(self, direction, damage, killer=None):
        self.player.hp = max(0, self.player.hp - damage)
        self.frame_events["player_hit"] = True
        self._spawn_hit_effect(self.player, self.player.hp <= 0, direction=direction)
        self.audio.play("hit" if self.player.hp > 0 else "kill",
                        0.8 if self.player.hp > 0 else 1.0)
        if self.player.hp > 0:
            self._set_shake(4, 3)
            self.player.invincible = S.HIT_INVINCIBLE
            if direction is not None:
                self._knockback(self.player, direction)
            return
        # 血量归零 -> 坦克被击毁，直接判负（1 命制，无复活）
        self.lives -= 1
        self.player.alive = False
        self.lose_reason = "life"
        self.add_kill_feed(killer or "对手", self.player_name)
        self._end(False)

    def _update_explosions(self):
        for ex in self.explosions:
            ex.update()
        self.explosions = [ex for ex in self.explosions if not ex.done]

    def _check_win(self):
        # 对战胜利 = 全部 AI 命尽淘汰（玩家命尽在 _on_player_hit 中判负）；跑图无胜负
        if self.battle_mode == "roam":
            return
        if (self.state == STATE_PLAYING
                and all(f.lives <= 0 and not f.alive for f in self.versus_foes)):
            self._end(True)

    def _end(self, win):
        self.audio.play("win" if win else "lose")
        self.state = STATE_WIN if win else STATE_LOSE
        if win:                                  # 胜利奖励零件：基础 + 每击杀
            self.parts_earned = S.PARTS_WIN + S.PARTS_PER_KILL * self.kills
            self.parts += self.parts_earned
            p = prefs.load()                     # 读改写，保留其余偏好
            p["parts"] = self.parts
            prefs.save(p)
        if self.playtest is not None:
            self.playtest.record(self, win)

    # ---------------- 渲染 ----------------

    def render(self, screen):
        sprites = get_sprites()
        screen.fill(S.BLACK)
        self._hits.clear()                  # 每帧重建命中区，避免跨页残留
        if self.state == STATE_START:
            # 标题主页面及仓库/名片/设置等子页共用墨蓝战术网格。
            screen.fill(S.MENU_BG)
            step = S.TILE_SIZE
            major = step * 4
            for x in range(0, S.SCREEN_WIDTH, step):
                color = (36, 49, 63) if x % major == 0 else (30, 41, 54)
                pygame.draw.line(screen, color, (x, 0), (x, S.SCREEN_HEIGHT))
            for y in range(0, S.SCREEN_HEIGHT, step):
                color = (36, 49, 63) if y % major == 0 else (30, 41, 54)
                pygame.draw.line(screen, color, (0, y), (S.SCREEN_WIDTH, y))
            for y in range(0, S.SCREEN_HEIGHT, major):
                for x in range(0, S.SCREEN_WIDTH, major):
                    pygame.draw.line(screen, (48, 62, 76), (x - 2, y), (x + 2, y))
                    pygame.draw.line(screen, (48, 62, 76), (x, y - 2), (x, y + 2))
            self._render_start(screen)      # 标题各页面不渲染战场
            return
        self._render_hud(screen)

        # 先在原世界坐标中绘制完整地图，再统一放大裁剪；实体逻辑与 AI 输入不受影响。
        map_size = (S.MAP_COLS * S.TILE_SIZE, S.MAP_ROWS * S.TILE_SIZE)
        world = pygame.Surface(map_size)
        self._render_field(world, sprites, oy=0)
        zoomed_size = (round(map_size[0] * S.CAMERA_ZOOM),
                       round(map_size[1] * S.CAMERA_ZOOM))
        zoomed = pygame.transform.scale(world, zoomed_size)

        view_w, view_h = S.SCREEN_WIDTH, S.SCREEN_HEIGHT - S.HUD_HEIGHT
        pcx = (self.player.x + S.TANK_SIZE / 2) * S.CAMERA_ZOOM
        pcy = (self.player.y + S.TANK_SIZE / 2) * S.CAMERA_ZOOM
        cam_x = max(0, min(int(pcx - view_w / 2), zoomed_size[0] - view_w))
        cam_y = max(0, min(int(pcy - view_h / 2), zoomed_size[1] - view_h))
        camera = pygame.Rect(cam_x, cam_y, view_w, view_h)

        if self.shake > 0:
            amplitude = max(1, round(self.shake_max * self.shake / max(self.shake_total, 1)))
            dx = self.fx_rng.randint(-amplitude, amplitude)
            dy = self.fx_rng.randint(-amplitude, amplitude)
        else:
            dx = dy = 0
        # 限制战场绘制区域，负向震屏也不能覆盖 HUD 下缘。
        previous_clip = screen.get_clip()
        screen.set_clip(pygame.Rect(0, S.HUD_HEIGHT, S.SCREEN_WIDTH,
                                    S.SCREEN_HEIGHT - S.HUD_HEIGHT))
        screen.blit(zoomed, (dx, S.HUD_HEIGHT + dy), camera)
        screen.set_clip(previous_clip)
        self._render_overlays(screen)
        self._render_minimap(screen)
        if self.whiteout > 0:
            alpha = int(200 * self.whiteout / 4)
            flash = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
            flash.fill((255, 255, 255, alpha))
            screen.blit(flash, (0, 0))
        if self.state == STATE_PAUSED:
            if self.settings_view:
                self._render_settings(screen)   # 暂停 -> 设置页覆盖战场
            else:
                self._render_pause(screen)
        elif self.state in (STATE_WIN, STATE_LOSE):
            self._render_end(screen)

    # ---- HUD ----

    def _render_minimap(self, screen):
        """左下角小地图：显示地形、视野圈与可见敌人的红点。"""
        tile = 4
        map_w, map_h = S.MAP_COLS * S.TILE_SIZE, S.MAP_ROWS * S.TILE_SIZE
        mini_w, mini_h = S.MAP_COLS * tile, S.MAP_ROWS * tile
        pad, margin = 5, 10
        origin_x = margin + pad
        origin_y = S.SCREEN_HEIGHT - mini_h - margin - pad
        panel = pygame.Rect(margin, origin_y - pad, mini_w + pad * 2, mini_h + pad * 2)
        self._panel(screen, panel, alpha=225)
        previous_clip = screen.get_clip()
        screen.set_clip(pygame.Rect(origin_x, origin_y, mini_w, mini_h))

        colors = {
            S.EMPTY: (24, 29, 33), S.BRICK: (156, 77, 43),
            S.STEEL: (115, 125, 135), S.RIVER: (38, 100, 178),
            S.FOREST: (37, 119, 55), S.BASE: S.YELLOW,
        }
        for r in range(S.MAP_ROWS):
            for c in range(S.MAP_COLS):
                pygame.draw.rect(screen, colors[self.grid[r][c]],
                                 (origin_x + c * tile, origin_y + r * tile, tile, tile))

        def point(x, y):
            return (origin_x + int(x * mini_w / map_w),
                    origin_y + int(y * mini_h / map_h))

        pcx = self.player.x + S.TANK_SIZE / 2
        pcy = self.player.y + S.TANK_SIZE / 2
        if self.battle_mode == "versus" and self.player.alive:
            view_px = self.view_radius * S.TILE_SIZE
            pygame.draw.circle(screen, (150, 155, 160), point(pcx, pcy),
                               int(view_px * mini_w / map_w), 1)
        player_in_forest = self.in_forest(self.player)

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            ecx, ecy = enemy.x + S.TANK_SIZE / 2, enemy.y + S.TANK_SIZE / 2
            if (self.battle_mode == "versus" and self.player.alive
                    and math.hypot(ecx - pcx, ecy - pcy) > self.view_radius * S.TILE_SIZE):
                continue
            if self.player.alive and not player_in_forest and self.in_forest(enemy):
                continue
            pos = point(ecx, ecy)
            pygame.draw.circle(screen, (20, 12, 12), pos, 3)
            pygame.draw.circle(screen, (255, 64, 54), pos, 2)

        pos = point(pcx, pcy)
        pygame.draw.circle(screen, (20, 20, 12), pos, 3)
        pygame.draw.circle(screen, S.YELLOW, pos, 2)
        screen.set_clip(previous_clip)

    def _render_overlays(self, screen):
        """技能圆环（右下）+ 公告/击杀播报（右上角）。"""
        if self.player.alive:
            self._render_skill_ring(screen)

        f_ann = get_font(16)
        f_feed = get_font(12)
        margin = 10
        # 公告：右上角右对齐，黑底 1px 边，最多 2 条
        y = S.HUD_HEIGHT + 6
        for text, color, _ttl in self.announcements[:2]:
            surf = f_ann.render(text, True, color)
            w, h = surf.get_size()
            box = pygame.Rect(S.SCREEN_WIDTH - margin - (w + 20), y, w + 20, h + 6)
            bg = pygame.Surface(box.size, pygame.SRCALPHA)
            bg.fill((0, 0, 0, 170))
            screen.blit(bg, box.topleft)
            pygame.draw.rect(screen, color, box, 1, border_radius=4)
            screen.blit(surf, (box.x + 10, box.y + 3))
            y = box.bottom + 6
        # 击杀播报：公告之下右对齐，最近 3 条
        for text, _ttl, killer, victim in self.kill_feed[-3:]:
            surf = f_feed.render(text, True, S.WHITE)
            avatars_row = [self._avatar_by_tag.get(n) for n in (killer, victim)]
            icons_w = sum(14 for a in avatars_row if a)   # 每个头像 12px + 2 间距
            w, h = surf.get_size()
            box = pygame.Rect(S.SCREEN_WIDTH - margin - (w + icons_w + 10), y,
                              w + icons_w + 10, h + 4)
            bg = pygame.Surface(box.size, pygame.SRCALPHA)
            bg.fill((0, 0, 0, 170))
            screen.blit(bg, box.topleft)
            pygame.draw.rect(screen, S.DARK_GRAY, box, 1)
            ax = box.x + 5
            for a in avatars_row:               # 击杀者头像在前，受害者头像在后
                if a:
                    screen.blit(avatars.scaled(a, 12), (ax, box.y + 2))
                    ax += 14
            screen.blit(surf, (ax, box.y + 2))
            y = box.bottom + 6

    def _render_skill_ring(self, screen):
        """右下角 K 技能：绿环=可用，灰弧=恢复；显示次数与冷却秒数。"""
        p = self.player
        cx, cy, r = S.SCREEN_WIDTH - 36, S.SCREEN_HEIGHT - 36, 16
        surf = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(surf, (0, 0, 0, 150), (cx, cy), r + 5)
        cooldown = 0
        if p.skill == "dash":
            if p.dash_charges < p.dash_charges_max:
                cooldown = p.dash_recharge
            if p.dash_charges > 0:
                ratio, color = 1.0, S.GREEN
            else:
                ratio = max(0.0, min(1 - cooldown / max(p.skill_cooldown_max, 1), 1.0))
                color = S.GRAY
        elif p.skill_cooldown > 0:
            cooldown = p.skill_cooldown
            ratio = max(0.0, min(1 - cooldown / max(p.skill_cooldown_max, 1), 1.0))
            color = S.GRAY
        else:
            ratio, color = 1.0, S.GREEN
        pygame.draw.circle(surf, (*color, 90), (cx, cy), r, 2)
        if ratio > 0:
            start = -math.pi / 2
            stop = start + ratio * 2 * math.pi
            pygame.draw.arc(surf, (*color, 255), (cx - r, cy - r, r * 2, r * 2),
                            start, stop, 4)
        screen.blit(surf, (0, 0))
        name = get_font(12).render(T(f"skill_name_{p.skill}"), True, S.WHITE)
        screen.blit(name, (cx - name.get_width() // 2, cy - name.get_height() // 2))
        if p.skill == "dash":
            count = get_font(10).render(f"×{p.dash_charges}", True,
                                        S.GREEN if p.dash_charges > 0 else S.GRAY)
            screen.blit(count, (cx + r + 3, cy - count.get_height() // 2))
        if cooldown > 0:
            seconds = math.ceil(cooldown / S.FPS * 10) / 10
            cd = get_font(10).render(f"{seconds:.1f}s", True, S.YELLOW)
            screen.blit(cd, (cx - cd.get_width() // 2, cy + r + 3))

    def _icon(self, key, surf, size):
        """把精灵缩放到指定尺寸用于 HUD 图标（缓存，避免每帧重算）。"""
        ck = (key, size)
        if ck not in self._icon_cache:
            self._icon_cache[ck] = pygame.transform.scale(surf, (size, size))
        return self._icon_cache[ck]

    def _render_hud(self, screen):
        pygame.draw.rect(screen, S.HUD_BG, (0, 0, S.SCREEN_WIDTH, S.HUD_HEIGHT))
        f9 = get_font(9)

        # 左：双行剩余敌人卡片，上行标签、下行大数字
        left_card = pygame.Rect(6, 4, 104, 40)
        pygame.draw.rect(screen, S.PANEL_BG, left_card, border_radius=4)
        pygame.draw.rect(screen, S.PANEL_BORDER, left_card, 1, border_radius=4)
        left_header = pygame.Rect(left_card.x + 1, left_card.y + 1, left_card.w - 2, 14)
        pygame.draw.rect(screen, (18, 20, 30), left_header, border_radius=3)
        pygame.draw.line(screen, (42, 44, 56), (left_card.x + 8, left_card.y + 18),
                         (left_card.right - 8, left_card.y + 18))
        pygame.draw.rect(screen, S.YELLOW, (left_card.x + 6, left_card.y + 6, 2, 7))
        pygame.draw.lines(screen, S.YELLOW, False,
                          [(left_card.right - 14, left_card.y + 6),
                           (left_card.right - 6, left_card.y + 6),
                           (left_card.right - 6, left_card.y + 14)], 1)
        lab_left = f9.render(T("hud_left"), True, S.LIGHT_GRAY)
        screen.blit(lab_left, (left_card.x + 12, left_header.centery - lab_left.get_height() // 2))
        foes_left = sum(1 for f in self.versus_foes if f.alive)
        count = get_font(20).render(str(foes_left), True, S.WHITE)
        count_x = left_card.x + 12
        count_y = left_card.bottom - 2 - count.get_height()
        screen.blit(count, (count_x + 1, count_y))  # 双绘形成粗体，不修改共享字体
        screen.blit(count, (count_x, count_y))

        # 中：玩家真实百分比血量与连续比例条
        hp_card = pygame.Rect(116, 4, 136, 40)
        pygame.draw.rect(screen, S.PANEL_BG, hp_card, border_radius=4)
        pygame.draw.rect(screen, S.PANEL_BORDER, hp_card, 1, border_radius=4)
        hp_header = pygame.Rect(hp_card.x + 1, hp_card.y + 1, hp_card.w - 2, 14)
        pygame.draw.rect(screen, (18, 20, 30), hp_header, border_radius=3)
        pygame.draw.line(screen, (42, 44, 56), (hp_card.x + 8, hp_card.y + 18),
                         (hp_card.right - 8, hp_card.y + 18))
        pygame.draw.rect(screen, S.GREEN, (hp_card.x + 6, hp_card.y + 6, 2, 7))
        hp_lab = f9.render(T("hud_hp"), True, S.LIGHT_GRAY)
        screen.blit(hp_lab, (hp_card.x + 12, hp_header.centery - hp_lab.get_height() // 2))
        hp_ratio = max(0.0, min(1.0, self.player.hp / max(self.player.max_hp, 1)))
        hp_text = get_font(18).render(f"{int(round(hp_ratio * 100))}%", True, S.WHITE)
        screen.blit(hp_text, (hp_card.x + 12, hp_card.bottom - 3 - hp_text.get_height()))
        hp_bar = pygame.Rect(hp_card.x + 60, hp_card.bottom - 10, hp_card.w - 72, 4)
        pygame.draw.rect(screen, S.DARK_GRAY, hp_bar)
        filled_w = int(round(hp_bar.width * hp_ratio))
        if filled_w > 0:
            pygame.draw.rect(screen, S.GREEN, (hp_bar.x, hp_bar.y, filled_w, hp_bar.height))

        # 右：排位安全区使用同样的双行结构
        if self.battle_mode == "versus":
            zone_txt = ("ZONE MAX" if self.zone_radius <= 0
                        else f"ZONE {self.zone_timer // 60 + 1}s")
            z = get_font(18).render(zone_txt, True, S.RED)
            lab = f9.render(T("zone_card"), True, S.LIGHT_GRAY)
            zone_w = max(142, lab.get_width() + 36, z.get_width() + 24)
            zone_card = pygame.Rect(S.SCREEN_WIDTH - 6 - zone_w, 4, zone_w, 40)
            pygame.draw.rect(screen, S.PANEL_BG, zone_card, border_radius=4)
            pygame.draw.rect(screen, S.PANEL_BORDER, zone_card, 1, border_radius=4)
            zone_header = pygame.Rect(zone_card.x + 1, zone_card.y + 1, zone_card.w - 2, 14)
            pygame.draw.rect(screen, (18, 20, 30), zone_header, border_radius=3)
            pygame.draw.line(screen, (42, 44, 56), (zone_card.x + 8, zone_card.y + 18),
                             (zone_card.right - 8, zone_card.y + 18))
            pygame.draw.rect(screen, S.RED, (zone_card.x + 6, zone_card.y + 6, 2, 7))
            pygame.draw.lines(screen, S.RED, False,
                              [(zone_card.right - 14, zone_card.y + 6),
                               (zone_card.right - 6, zone_card.y + 6),
                               (zone_card.right - 6, zone_card.y + 14)], 1)
            screen.blit(lab, (zone_card.x + 12, zone_header.centery - lab.get_height() // 2))
            screen.blit(z, (zone_card.x + 12, zone_card.bottom - 3 - z.get_height()))

        pygame.draw.line(screen, S.PANEL_BORDER, (0, S.HUD_HEIGHT - 1), (S.SCREEN_WIDTH, S.HUD_HEIGHT - 1))

    def _render_field(self, screen, sprites, oy=S.HUD_HEIGHT):
        # 玩家是否藏在草地里：决定草地画在坦克之下还是之上（单向可见）
        player_in_forest = self.in_forest(self.player)

        # 视野（战争迷雾）：以玩家为中心的纯圆形范围，不遮挡
        view_px = self.view_radius * S.TILE_SIZE
        pcx = self.player.x + S.TANK_SIZE / 2
        pcy = self.player.y + S.TANK_SIZE / 2

        def in_view(x, y):
            """仅排位限制视野；其它模式及阵亡观战均直接可见。"""
            if self.battle_mode != "versus" or not self.player.alive:
                return True
            return math.hypot(x - pcx, y - pcy) <= view_px

        def draw_forest():
            for r in range(S.MAP_ROWS):
                for c in range(S.MAP_COLS):
                    if self.grid[r][c] == S.FOREST:
                        # 固定格子哈希混合绿/棕树，同一位置不会逐帧闪烁。
                        img = sprites.forest_brown if (r * 31 + c * 17) % 4 < 2 else sprites.forest
                        screen.blit(img, (c * S.TILE_SIZE, oy + r * S.TILE_SIZE))

        def draw_hp(tank, color):
            """坦克头顶 26×3 连续百分比血条，下方弹匣点位置不变。"""
            x0 = int(tank.x) + 1
            y0 = oy + int(tank.y) - 6
            ratio = max(0.0, min(1.0, tank.hp / max(tank.max_hp, 1)))
            pygame.draw.rect(screen, (60, 60, 66), (x0, y0, 26, 3))
            filled_w = int(round(26 * ratio))
            if filled_w > 0:
                pygame.draw.rect(screen, color, (x0, y0, filled_w, 3))

        def draw_invincible(tank):
            """坦克常显；护盾环呼吸，最后 12 帧仅环体闪烁提示。"""
            if tank.invincible <= 0:
                return
            frames = sprites.invincible_frames
            if tank.invincible <= 12:
                index = 2 if (tank.invincible // 3) % 2 else 0
            else:
                index = (tank.invincible // 5) % len(frames)
            img = frames[index]
            screen.blit(img, (round(tank.x + S.TANK_SIZE / 2 - img.get_width() / 2),
                              oy + round(tank.y + S.TANK_SIZE / 2 - img.get_height() / 2)))

        # 地形（森林除外）
        screen.blit(sprites.grounds[self.current_map_index - 1], (0, oy))  # 当前地图专属地板
        for r in range(S.MAP_ROWS):
            for c in range(S.MAP_COLS):
                tile = self.grid[r][c]
                if tile == S.EMPTY or tile == S.FOREST:
                    continue
                if tile == S.RIVER:            # 河流双帧缓慢流动（0.5s 一帧）
                    img = sprites.river_b if (self.frame // 30) % 2 else sprites.tiles[S.RIVER]
                else:
                    img = sprites.tiles[tile]
                screen.blit(img, (c * S.TILE_SIZE, oy + r * S.TILE_SIZE))
        # 无外墙边界提示：1px 暗灰线框（边界由代码拦截，线框仅视觉提示）
        pygame.draw.rect(screen, S.DARK_GRAY,
                         (0, oy, S.MAP_COLS * S.TILE_SIZE, S.MAP_ROWS * S.TILE_SIZE), 1)

        if player_in_forest:
            draw_forest()                   # 草地里：草地铺在坦克下方 -> 看得见所有对手

        # 道具（地形之上、坦克之下；最后 3s 闪烁提示即将消失；视野外不可见）
        for it in self.items:
            if it.ttl < S.ITEM_BLINK_TTL and (self.frame // 10) % 2 == 0:
                continue
            if not in_view(it.x + it.SIZE / 2, it.y + it.SIZE / 2):
                continue
            screen.blit(sprites.items[it.kind], (it.x, oy + it.y))

        # 毒圈：圈外格子罩半透明红（覆盖地形与道具，坦克仍可辨识）
        if self.zone_radius < S.ZONE_INITIAL_RADIUS:
            zone_red = pygame.Surface((S.TILE_SIZE, S.TILE_SIZE), pygame.SRCALPHA)
            zone_red.fill((255, 40, 40, 64))
            ctr = S.MAP_ROWS // 2
            for r in range(S.MAP_ROWS):
                for c in range(S.MAP_COLS):
                    if max(abs(r - ctr), abs(c - ctr)) > self.zone_radius:
                        screen.blit(zone_red, (c * S.TILE_SIZE, oy + r * S.TILE_SIZE))

            # 下一圈收缩位置：红色虚线预告框
            tgt = self.zone_radius - 1
            x1 = (ctr - tgt) * S.TILE_SIZE
            x2 = (ctr + tgt + 1) * S.TILE_SIZE
            y1, y2 = oy + x1, oy + x2
            line_c = (255, 60, 60)
            for lo, hi, fixed, horiz in ((x1, x2, y1, True), (x1, x2, y2, True),
                                         (y1, y2, x1, False), (y1, y2, x2, False)):
                step = 20
                p = lo
                while p < hi:
                    q = min(p + 12, hi)
                    if horiz:
                        pygame.draw.line(screen, line_c, (p, fixed), (q, fixed), 2)
                    else:
                        pygame.draw.line(screen, line_c, (fixed, p), (fixed, q), 2)
                    p += step

        def draw_particles(behind):
            for p in self.particles:
                if p.behind != behind or not self._effect_visible(p.x, p.y):
                    continue
                pygame.draw.rect(screen, p.color,
                                 (round(p.x), oy + round(p.y), p.size, p.size))

        # 底层效果：弹道尾迹与疾冲残影不遮盖坦克和弹体。
        draw_particles(True)
        for a in self.afterimages:
            if self._effect_visible(a.x + S.TANK_SIZE / 2, a.y + S.TANK_SIZE / 2):
                screen.blit(a.sprite, (a.x, oy + a.y))

        # 坦克（玩家）；无敌期也保持车身常显，草内保留透明剪影。
        if self.player.alive:
            tank_img = sprites.player_tanks[self.player.tank_type][self.player.direction]
            if player_in_forest:
                shadow = pygame.mask.from_surface(tank_img).to_surface(
                    setcolor=(0, 0, 0, 52), unsetcolor=(0, 0, 0, 0))
                for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0),
                               (1, 0), (-1, 1), (0, 1), (1, 1)):
                    screen.blit(shadow, (self.player.x + dx, oy + self.player.y + dy))
            screen.blit(tank_img, (self.player.x, oy + self.player.y))
            draw_invincible(self.player)
        for e in self.enemies:
            if not e.alive:
                continue
            if not in_view(e.x + S.TANK_SIZE / 2, e.y + S.TANK_SIZE / 2):
                continue                      # 视野外敌人不渲染
            # AI 按随机到的型号渲染，无敌护盾环不替代车身。
            screen.blit(sprites.player_tanks[e.tank_type][e.direction], (e.x, oy + e.y))
            # 环比草格大，草外看草内时须整环跳过，避免边缘泄露位置。
            if self._effect_visible(e.x + S.TANK_SIZE / 2, e.y + S.TANK_SIZE / 2):
                draw_invincible(e)
        # 子弹（视野外不渲染）
        for b in self.bullets:
            if not in_view(b.x, b.y):
                continue
            if b.piercing:
                img = sprites.bullet_piercing
                screen.blit(img, (b.x - 1, oy + b.y - 1))
            else:
                screen.blit(sprites.bullet, (b.x, oy + b.y))

        # 上层效果：火花、碎屑、枪口、闪光环和爆炸。
        draw_particles(False)
        for m in self.muzzles:
            if not self._effect_visible(m["x"], m["y"]):
                continue
            images = sprites.muzzle_piercing if m["piercing"] else sprites.muzzle
            img = images[m["direction"]]
            screen.blit(img, (round(m["x"] - img.get_width() / 2),
                              oy + round(m["y"] - img.get_height() / 2)))
        for f in self.flashes:
            rect = f["rect"]
            if not self._effect_visible(rect.centerx, rect.centery):
                continue
            flash = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            flash.fill((255, 255, 255, int(200 * f["timer"] / 2)))
            screen.blit(flash, (rect.x, oy + rect.y))
        for r in self.rings:
            if r.get("delay", 0) > 0 or not self._effect_visible(r["x"], r["y"]):
                continue
            progress = (r["total"] - r["timer"]) / max(r["total"] - 1, 1)
            radius = int(r["r0"] + progress * (r["r1"] - r["r0"]))
            pygame.draw.circle(screen, r.get("color", S.YELLOW),
                               (int(r["x"]), oy + int(r["y"])), radius, r["w"])
        for ex in self.explosions:
            if not self._effect_visible(ex.x, ex.y):
                continue
            frames = sprites.kill_explosions if ex.kind == "kill" else sprites.explosions
            img = frames[ex.frame]
            screen.blit(img, (ex.x - img.get_width() // 2, oy + ex.y - img.get_height() // 2))
        for e in self.enemies:
            if e.alive and e.fan_flash > 0 \
                    and self._effect_visible(e.x + S.TANK_SIZE / 2, e.y + S.TANK_SIZE / 2):
                self._render_fan_flash(screen, oy, e, e.fan_flash)
        if self.fan_flash > 0 and self.player.alive:
            self._render_fan_flash(screen, oy, self.player, self.fan_flash)

        if not player_in_forest:
            draw_forest()                   # 草地外：草地同时盖住坦克与特效
        # 战争迷雾最后遮盖世界层，避免视野外战斗反馈泄露位置。
        if self.battle_mode == "versus" and self.player.alive and view_px < S.MAP_COLS * S.TILE_SIZE:
            fog = pygame.Surface((S.TILE_SIZE, S.TILE_SIZE), pygame.SRCALPHA)
            fog.fill((0, 0, 0, 200))
            for r in range(S.MAP_ROWS):
                for c in range(S.MAP_COLS):
                    if not in_view(c * S.TILE_SIZE + S.TILE_SIZE / 2, r * S.TILE_SIZE + S.TILE_SIZE / 2):
                        screen.blit(fog, (c * S.TILE_SIZE, oy + r * S.TILE_SIZE))

        # 血条、弹匣和名字保持在世界效果之上；草内敌人仍不泄露信息。
        if self.player.alive:
            draw_hp(self.player, S.GREEN)
            self._draw_mag_pips(screen, oy, self.player)
            self._render_range_hint(screen, oy)
        for e in self.enemies:
            if not e.alive or not self._effect_visible(e.x + S.TANK_SIZE / 2,
                                                       e.y + S.TANK_SIZE / 2):
                continue
            draw_hp(e, S.RED)
            if self.show_enemy_names:
                tag = get_font(12).render(e.tag, True, S.RED)
                tx = e.x + (S.TANK_SIZE - tag.get_width()) // 2
                ty = oy + e.y - 22
                screen.fill((0, 0, 0), (tx - 2, ty - 1, tag.get_width() + 4, tag.get_height() + 2))
                screen.blit(tag, (tx, ty))

    def _render_fan_flash(self, screen, oy, tank, flash):
        """8 帧薄扇面 + 两道分段像素弧；最外弧严格对应 fan_radius。"""
        radius = int(tank.fan_radius)
        pad = 4
        center_2d = radius + pad
        size = (radius + pad) * 2
        px = tank.x + S.TANK_SIZE / 2
        py = oy + tank.y + S.TANK_SIZE / 2
        origin = (round(px - center_2d), round(py - center_2d))
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        fx, fy = S.DIR_VECTORS[tank.direction]
        center = math.atan2(fy, fx)
        half = math.radians(tank.fan_half_angle)
        points = [(center_2d, center_2d)]
        for i in range(7):
            a = center - half + 2 * half * i / 6
            points.append((center_2d + radius * math.cos(a),
                           center_2d + radius * math.sin(a)))
        pygame.draw.polygon(surf, (250, 220, 90, 3 * flash), points)
        for ring_radius, color, width in ((round(radius * 0.68), (255, 240, 170), 1),
                                          (radius, (250, 220, 90), 2)):
            rect = (center_2d - ring_radius, center_2d - ring_radius,
                    ring_radius * 2, ring_radius * 2)
            for i in range(6):              # 留隙分段，保持像素弧清晰
                a0 = center - half + 2 * half * i / 6
                a1 = center - half + 2 * half * (i + 0.72) / 6
                pygame.draw.arc(surf, (*color, 18 * flash), rect, a0, a1, width)
        screen.blit(surf, origin)

    def _render_range_hint(self, screen, oy):
        """玩家平A锁定圈（常驻）：以坦克为中心的虚线圆，半径=射程；锁定到目标时变红。"""
        p = self.player
        r = p.fan_radius if p.fire_mode == "fan" else (p.bullet_frames or 0) * S.BULLET_SPEED
        if r <= 0:
            return
        cx = p.x + S.TANK_SIZE / 2
        cy = oy + p.y + S.TANK_SIZE / 2
        locked = self._auto_target(p) is not None
        color = (255, 90, 70, 180) if locked else (255, 255, 255, 160)

        surf = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        steps = 48
        for i in range(0, steps, 2):                 # 隔段画 -> 虚线圆
            a0 = 2 * math.pi * i / steps
            a1 = 2 * math.pi * (i + 1) / steps
            pygame.draw.line(surf, color,
                             (cx + r * math.cos(a0), cy + r * math.sin(a0)),
                             (cx + r * math.cos(a1), cy + r * math.sin(a1)))
        screen.blit(surf, (0, 0))

    def _draw_mag_pips(self, screen, oy, tank):
        """头顶血条正下方的子弹格：有弹黄/已耗暗灰；换弹中按比例逐格填充。"""
        x0 = int(tank.x) + 1
        y0 = oy + int(tank.y) - 2
        if tank.reload_timer > 0:
            ratio = 1 - tank.reload_timer / max(tank.reload_frames, 1)
            filled_n = int(ratio * tank.mag_size)
        else:
            filled_n = tank.mag
        for i in range(tank.mag_size):
            color = S.YELLOW if i < filled_n else S.DARK_GRAY
            pygame.draw.rect(screen, color, (x0 + i * 6, y0, 5, 2))

    def _render_overlay(self, screen):
        overlay = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*S.MENU_BG, 180))
        screen.blit(overlay, (0, 0))

    def _panel(self, screen, rect, alpha=190):
        """界面文字底板：压暗战场，保证文字在任何地形上都可读。"""
        surf = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
        surf.fill((*S.PANEL_BG, alpha))
        screen.blit(surf, (rect[0], rect[1]))
        pygame.draw.rect(screen, S.PANEL_BORDER, rect, 1)

    def _page_title(self, screen, key, dy=0):
        """子页统一标题：居中黄字 + 下方分隔线，可按页面微调纵坐标。"""
        img = get_font(20).render(T(key), True, S.YELLOW)
        screen.blit(img, ((S.SCREEN_WIDTH - img.get_width()) // 2, TITLE_Y + dy))
        pygame.draw.line(screen, S.DARK_GRAY, (PANEL_X + 16, TITLE_LINE_Y + dy),
                         (PANEL_X + PANEL_W - 16, TITLE_LINE_Y + dy))

    def _hint(self, screen, key, y=HINT_Y, color=None):
        """底部灰色提示行（居中）。"""
        img = get_font(12).render(T(key), True, color or S.GRAY)
        screen.blit(img, ((S.SCREEN_WIDTH - img.get_width()) // 2, y))

    @staticmethod
    def _list_y0(n):
        """n 行列表在面板内容区垂直居中后的首行 y。"""
        span = PANEL_H - 60 - 28
        used = n * ROW_H + max(0, n - 1) * (ROW_PITCH - ROW_H)
        return LIST_Y0 + max(0, (span - used) // 2)

    def _btn_face(self, screen, rect, selected=False):
        """按钮底板（复古斜面三态）：选中=黄框+左黄条，悬停=提亮，按下=斜面反转。"""
        mx, my = pygame.mouse.get_pos()
        hover = (self._mouse_nav and not self.keybind_waiting
                 and rect.collidepoint(mx // S.SCALE, my // S.SCALE))
        pressed = hover and pygame.mouse.get_pressed()[0]
        if selected:
            fill, hi, lo = (54, 48, 22), S.YELLOW, (122, 96, 24)
        elif hover:
            fill, hi, lo = (52, 56, 66), (172, 180, 192), (24, 26, 32)
        else:
            fill, hi, lo = (28, 30, 36), (88, 92, 102), (14, 14, 18)
        if pressed:                       # 按下时高光/暗边互换，产生“凹进去”的手感
            hi, lo = lo, hi
        body = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        body.fill((*fill, 230))
        screen.blit(body, rect.topleft)
        pygame.draw.line(screen, hi, rect.topleft, (rect.right - 1, rect.y))
        pygame.draw.line(screen, hi, rect.topleft, (rect.x, rect.bottom - 1))
        pygame.draw.line(screen, lo, (rect.x, rect.bottom - 1),
                         (rect.right - 1, rect.bottom - 1))
        pygame.draw.line(screen, lo, (rect.right - 1, rect.y),
                         (rect.right - 1, rect.bottom - 1))
        if selected:
            pygame.draw.rect(screen, S.YELLOW, (rect.x, rect.y, 3, rect.h))
        return hover, pressed

    def _row(self, screen, y, selected, width=MENU_W, x=MENU_X, height=ROW_H):
        """列表行按钮底板（三态），返回矩形供命中。"""
        rect = pygame.Rect(x, y, width, height)
        self._btn_face(screen, rect, selected)
        return rect

    def _menu_button(self, screen, text, y, selected, width=MENU_W, x=MENU_X, hit_key=None):
        """列表式菜单项：文字居中；三态底板 + 选中/悬停左侧箭头；按住文字下移 1px。"""
        rect = pygame.Rect(x, y, width, ROW_H)
        hover, pressed = self._btn_face(screen, rect, selected)
        color = S.YELLOW if selected else (S.WHITE if hover else S.LIGHT_GRAY)
        img = get_font(20).render(text, True, color)
        dy = 1 if pressed else 0
        screen.blit(img, (rect.centerx - img.get_width() // 2,
                          rect.y + (ROW_H - img.get_height()) // 2 + dy))
        if selected or hover:
            ty = rect.centery + dy
            pygame.draw.polygon(screen, S.YELLOW if selected else S.LIGHT_GRAY,
                                [(rect.x + 9, ty - 4), (rect.x + 15, ty),
                                 (rect.x + 9, ty + 4)])
        if hit_key:
            self._hits[hit_key] = rect

    def _render_start(self, screen):
        """标题界面（线框布局）：顶栏（玩家名片）+ 中央地图卡片 + 按钮列。"""
        w = S.SCREEN_WIDTH

        if self.garage:
            self._render_garage(screen)
            return
        if self.profile_view:
            self._render_profile(screen)
            return
        if self.keybind_view:
            self._render_keybind(screen)
            return
        if self.settings_view:
            self._render_settings(screen)
            return

        sprites = get_sprites()

        # 顶栏：左=玩家名片（头像 30px + 名字，点击进入改名页）
        av = 30
        if self.player_avatar:
            screen.blit(avatars.scaled(self.player_avatar[1], av), (10, 7))
        else:
            screen.blit(self._icon("title", sprites.player_tanks[self.tank_type][S.UP], av),
                        (10, 7))
        pygame.draw.rect(screen, S.PANEL_BORDER, (10, 7, av, av), 1)
        name = get_font(18).render(self.player_name, True, S.WHITE)
        name_y = 7 + (av - name.get_height()) // 2
        screen.blit(name, (10 + av + 8, name_y))
        self._hits["profile"] = pygame.Rect(6, 3, av + 12 + name.get_width() + 10, av + 8)

        # 顶栏右：零件余额（像素装甲图标 + 黄数字）
        pv = get_font(18).render(str(self.parts), True, S.YELLOW)
        px = w - 12 - pv.get_width()
        icon = self._icon("parts", sprites.parts_icon, 16)
        screen.blit(icon, (px - 20, 14))
        screen.blit(pv, (px, 13))

        pygame.draw.line(screen, S.DARK_GRAY, (0, 44), (w, 44))

        if self.start_notice is not None:
            notice_keys = {
                "versus": ("versus_1", "versus_2"),
                "agent_loading": ("agent_loading_1", "agent_loading_2"),
                "agent_failed": ("agent_failed_1", "agent_failed_2"),
            }
            for i, key in enumerate(notice_keys[self.start_notice]):
                color = S.YELLOW if self.start_notice == "agent_loading" and i == 0 else (
                    S.RED if i == 0 else S.WHITE)
                img = get_font(16).render(T(key), True, color)
                screen.blit(img, ((w - img.get_width()) // 2, 240 + i * 32))
            hint_key = "hint_agent_loading" if self.start_notice == "agent_loading" else "hint_back"
            hint = get_font(14).render(T(hint_key), True, S.WHITE)
            screen.blit(hint, ((w - hint.get_width()) // 2, 360))
            return

        # 中央地图卡片（ROW_MAP_CONFIG 焦点态）：< 亮色蓝图 > + 地图名
        card = pygame.Rect(CARD_TANK)
        focused = self.mode_index == ROW_MAP_CONFIG
        self._panel(screen, card)
        if focused:
            pygame.draw.rect(screen, S.YELLOW, card, 2)
        self._render_map_thumb(screen, card)
        acy = card.y + 52                            # 箭头与缩略图齐平（三态小方块）
        for hit, cx0, side in (("cfg_map_left", card.x - 20, -1),
                               ("cfg_map_right", card.right + 20, 1)):
            chip = pygame.Rect(cx0 - 14, acy - 14, 28, 28)
            hover, pressed = self._btn_face(screen, chip)
            tx = chip.centerx + (1 if pressed else 0) * side
            color = (196, 206, 216) if focused or hover else (142, 153, 166)
            for offset in (-5, 0):               # 两条折线组成《或》，不依赖字体字形
                bx = tx + offset * side
                pygame.draw.lines(screen, color, False,
                                  [(bx, acy - 6), (bx + 5 * side, acy),
                                   (bx, acy + 6)], 1)
            self._hits[hit] = chip
        self._hits["cfg_map_card"] = card
        mname = get_font(16).render(T(f"map_{self.map_index}"), True,
                                    S.YELLOW if focused else S.WHITE)
        screen.blit(mname, (card.centerx - mname.get_width() // 2, card.y + 126))

        # 按钮列：对战 / 排位 / 自定义 / 坦克营地 / 设置
        keys = ("mode_pure", "mode_versus", "mode_roam", "mode_garage", "mode_settings")
        hit_keys = ("btn_pure", "btn_versus", "btn_roam", "btn_garage", "btn_settings")
        idxs = (MODE_PURE, MODE_VERSUS, MODE_ROAM, MODE_GARAGE, ROW_SETTINGS)
        for i, (key, mi) in enumerate(zip(keys, idxs)):
            self._menu_button(screen, T(key), MODE_Y0 + i * MODE_PITCH,
                              self.mode_index == mi, hit_key=hit_keys[i])

        # 底部：分隔线 + 操作提示 + AI 说明
        pygame.draw.line(screen, S.DARK_GRAY, (MENU_X, FOOTER_LINE_Y),
                         (MENU_X + MENU_W, FOOTER_LINE_Y))
        hint = get_font(12).render(T("hint_controls"), True, S.GRAY)
        screen.blit(hint, ((w - hint.get_width()) // 2, FOOTER_HINT_Y))
        ai = get_font(12).render(T("hint_ai"), True, S.GREEN)
        screen.blit(ai, ((w - ai.get_width()) // 2, FOOTER_AI_Y))

    def _render_map_thumb(self, screen, card):
        """中央卡片的亮色战术蓝图：17x17 浅底网格 + 几何地形（每格 6px）。"""
        bg, grid_line = (235, 232, 220), (210, 205, 190)
        board = pygame.Rect(card.x + 10, card.y + 10, card.w - 20, 108)
        screen.fill(bg, board)
        pygame.draw.rect(screen, (126, 122, 112), board, 1)

        ox, oy, cell = card.centerx - 51, card.y + 13, 6
        grid_size = S.MAP_COLS * cell
        for i in range(S.MAP_COLS + 1):
            x = ox + i * cell
            pygame.draw.line(screen, grid_line, (x, oy), (x, oy + grid_size))
        for i in range(S.MAP_ROWS + 1):
            y = oy + i * cell
            pygame.draw.line(screen, grid_line, (ox, y), (ox + grid_size, y))

        if self.map_index == 0:
            q = get_font(40).render("?", True, (96, 94, 88))
            screen.blit(q, q.get_rect(center=(card.centerx, oy + grid_size // 2)))
            return

        from .level import VERSUS_MAPS
        template = VERSUS_MAPS[self.map_index - 1]
        colors = {S.BRICK: (224, 124, 72), S.STEEL: (113, 128, 145),
                  S.RIVER: (86, 164, 224), S.FOREST: (104, 178, 102)}
        char_to_tile = {".": S.EMPTY, "B": S.BRICK, "S": S.STEEL,
                        "R": S.RIVER, "F": S.FOREST}
        for r, row in enumerate(template):
            for c, ch in enumerate(row):
                tile = char_to_tile[ch]
                if tile == S.EMPTY:
                    continue
                rect = pygame.Rect(ox + c * cell, oy + r * cell, cell, cell)
                color = colors[tile]
                if tile == S.FOREST:
                    pygame.draw.circle(screen, color, rect.center, 3)
                    pygame.draw.circle(screen, (153, 207, 129),
                                       (rect.centerx - 1, rect.centery - 1), 1)
                    continue
                screen.fill(color, rect)
                if tile == S.STEEL:
                    pygame.draw.line(screen, (188, 200, 208), rect.topleft,
                                     (rect.right - 1, rect.y))
                    pygame.draw.line(screen, (188, 200, 208), rect.topleft,
                                     (rect.x, rect.bottom - 1))
                elif tile == S.RIVER:
                    pygame.draw.line(screen, (177, 222, 246),
                                     (rect.x + 1, rect.centery),
                                     (rect.right - 2, rect.centery))

    def _render_profile(self, screen):
        """名片编辑页：大头像（两侧箭头切换）+ 名字输入行 + 提示。"""
        w = S.SCREEN_WIDTH
        self._panel(screen, pygame.Rect(PANEL).move(0, PROFILE_DY))
        self._page_title(screen, "profile_title", PROFILE_DY)

        # 头像及两侧箭头与面板同步上移，程序绘制三角不依赖字体字形
        ax, ay, asz = w // 2 - 28, 176 + PROFILE_DY, 56
        if self.player_avatar:
            screen.blit(avatars.scaled(self.player_avatar[1], asz), (ax, ay))
        else:
            big = pygame.transform.scale(
                get_sprites().player_tanks[self.tank_type][S.UP], (asz, asz))
            screen.blit(big, (ax, ay))
        cy = ay + asz // 2
        # 头像框两侧：淡色双尖角，与头像留6px间距，点击切换头像
        lchip = pygame.Rect(ax - 34, cy - 14, 28, 28)
        rchip = pygame.Rect(ax + asz + 6, cy - 14, 28, 28)
        for chip, side in ((lchip, -1), (rchip, 1)):
            hover, pressed = self._btn_face(screen, chip)
            cx0 = chip.centerx + (1 if pressed else 0) * side
            color = (196, 206, 216) if hover else (142, 153, 166)
            for offset in (-5, 0):
                bx = cx0 + offset * side
                pygame.draw.lines(screen, color, False,
                                  [(bx, cy - 6), (bx + 5 * side, cy),
                                   (bx, cy + 6)], 1)
        self._hits["profile_av_left"] = lchip
        self._hits["profile_av_right"] = rchip
        self._hits["profile_av"] = pygame.Rect(ax, ay, asz, asz)

        # 头像池计数（池空提示无头像）
        items = avatars.pool()
        if items:
            names = [n for n, _ in items]
            idx = names.index(self.player_avatar[0]) + 1 if (
                self.player_avatar and self.player_avatar[0] in names) else 0
            note = "%d / %d" % (idx, len(items))
        else:
            note = T("profile_no_avatar")
        cnt = get_font(12).render(note, True, S.GRAY)
        screen.blit(cnt, (w // 2 - cnt.get_width() // 2, 240 + PROFILE_DY))

        # 输入行：默认只展示名字，点击名字框后才进入改名（黄框 + 光标）
        box = pygame.Rect(PROFILE_BOX)
        pygame.draw.rect(screen, (36, 36, 40) if not self.profile_focus else S.DARK_GRAY, box)
        pygame.draw.rect(screen, S.YELLOW if self.profile_focus else S.PANEL_BORDER, box, 1)
        self._hits["profile_name"] = box
        f16 = get_font(16)
        if self.profile_focus:
            cursor = "_" if (self.frame // 18) % 2 == 0 else " "
            parts = ((self.profile_editing, S.WHITE), (self.profile_composing, S.LIGHT_GRAY),
                     (cursor, S.WHITE))
        else:
            parts = ((self.profile_editing, S.LIGHT_GRAY),)
        imgs = [f16.render(s, True, c) for s, c in parts if s]
        x = box.centerx - sum(i.get_width() for i in imgs) // 2
        for img in imgs:                          # 分段绘制：组合内容用灰色区分
            screen.blit(img, (x, box.y + (box.h - img.get_height()) // 2))
            x += img.get_width()

        # 导入头像按钮（选择本地图片复制进 assets/avatars）
        btn = pygame.Rect(w // 2 - 70, box.bottom + 16, 140, 28)
        hover, pressed = self._btn_face(screen, btn)
        txt = get_font(16).render(T("profile_import"), True,
                                  S.YELLOW if hover else S.WHITE)
        screen.blit(txt, (btn.centerx - txt.get_width() // 2,
                          btn.centery - txt.get_height() // 2 + (1 if pressed else 0)))
        self._hits["profile_import"] = btn

        if not self.profile_composing:            # 输入法候选窗会占这块，组合时先让位
            self._hint(screen, "hint_profile" if self.profile_focus else "hint_profile_view",
                       HINT_Y + PROFILE_DY)

    def _render_settings(self, screen):
        """八行设置页；标题/暂停共用。"""
        if self.settings_from == "pause":
            overlay = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((*S.MENU_BG, 160))          # 遮罩战场，同暂停界面样式
            screen.blit(overlay, (0, 0))
        self._panel(screen, PANEL)
        self._page_title(screen, "mode_settings")

        labels = ("cfg_music", "cfg_sfx", "cfg_master_volume", "cfg_sfx_volume",
                  "cfg_players", "cfg_enemy_names", "cfg_keys", "cfg_back")
        values = (T("set_on") if self.audio.music_on else T("set_off"),
                  T("set_on") if self.audio.sfx_on else T("set_off"),
                  "%d%%" % self.audio.master_volume,
                  "%d%%" % self.audio.sfx_volume,
                  str(self.num_combatants),
                  T("set_on") if self.show_enemy_names else T("set_off"), "", "")
        f16 = get_font(16)
        row_h, pitch = 24, 28                 # 八行紧凑排列，底部止于 380
        for i in range(len(labels)):
            selected = i == self.settings_index
            rect = self._row(screen, LIST_Y0 + i * pitch, selected, height=row_h)
            self._hits["set_%d" % i] = rect
            color = S.YELLOW if selected else S.WHITE
            label = f16.render(T(labels[i]), True, color)
            screen.blit(label, (rect.x + 14, rect.y + (rect.h - label.get_height()) // 2))
            if values[i]:
                val = f16.render(values[i], True, S.YELLOW)
                vx = rect.right - 16 - val.get_width()
                screen.blit(val, (vx, rect.y + (rect.h - val.get_height()) // 2))
                if i in (2, 3, 4):              # 音量与人数：数值两侧画小三角
                    cy = rect.centery
                    pygame.draw.polygon(screen, S.LIGHT_GRAY,
                                        [(vx - 8, cy), (vx - 2, cy - 5), (vx - 2, cy + 5)])
                    tx = vx + val.get_width() + 8
                    pygame.draw.polygon(screen, S.LIGHT_GRAY,
                                        [(tx + 6, cy), (tx, cy - 5), (tx, cy + 5)])

        self._hint(screen, "hint_settings")

    def _render_keybind(self, screen):
        """键位子页：方向四键 + J 普攻 + K 技能 + 恢复默认。"""
        self._panel(screen, PANEL)
        self._page_title(screen, "keybind_title")

        names = ("keybind_up", "keybind_down", "keybind_left",
                 "keybind_right", "keybind_fire", "keybind_skill")
        f16 = get_font(16)
        y0 = LIST_Y0
        pitch = 32                       # 七行紧凑排列，避开底部提示
        for i in range(7):
            selected = i == self.keybind_index
            rect = self._row(screen, y0 + i * pitch, selected)
            self._hits["kb_%d" % i] = rect
            color = S.YELLOW if selected else S.WHITE
            label = T("keybind_reset") if i == 6 else T(names[i])
            screen.blit(f16.render(label, True, color),
                        (rect.x + 14, rect.y + (ROW_H - f16.get_height()) // 2))
            if i < 6:
                if selected and self.keybind_waiting:
                    val_text = T("keybind_wait")
                else:
                    val_text = pygame.key.name(self.keybinds[S.KEYBIND_ORDER[i]]).upper()
                val = f16.render(val_text, True, S.YELLOW)
                screen.blit(val, (rect.right - 16 - val.get_width(),
                                  rect.y + (ROW_H - val.get_height()) // 2))

        self._hint(screen, "hint_keybind")

    def _render_garage(self, screen):
        """坦克仓库：左侧大预览、右侧属性条、底部型号卡片。"""
        sprites = get_sprites()
        tt = S.TANK_ORDER[self.garage_index]
        cfg = S.TANK_TYPES[tt]
        f10, f12, f14 = get_font(10), get_font(12), get_font(14)
        dy = (S.SCREEN_HEIGHT - 340) // 2 - PANEL_Y  # 整组高 340px，垂直居中

        self._panel(screen, (PANEL_X, PANEL_Y + dy, PANEL_W, PANEL_H))
        self._page_title(screen, "mode_garage", dy=dy)
        parts = f12.render(str(self.parts), True, S.YELLOW)
        px = PANEL_X + PANEL_W - 16 - parts.get_width()
        parts_icon = self._icon("parts", sprites.parts_icon, 16)
        screen.blit(parts_icon, (px - 20, TITLE_Y + dy + 4))
        screen.blit(parts, (px, TITLE_Y + dy + 5))

        preview = pygame.Rect(40, 164 + dy, 158, 168)
        details = pygame.Rect(206, 164 + dy, 170, 168)
        self._panel(screen, preview)
        self._panel(screen, details)
        self._hits["garage_select"] = preview

        # 左侧预览：蓝灰八角展台托出暗色坦克，源尺寸整数倍放大。
        left, right = preview.x + 14, preview.right - 14
        top, bottom = 184 + dy, 296 + dy
        cut = 12
        platform = [
            (left + cut, top), (right - cut, top),
            (right, top + cut), (right, bottom - cut),
            (right - cut, bottom), (left + cut, bottom),
            (left, bottom - cut), (left, top + cut),
        ]
        pygame.draw.polygon(screen, (36, 49, 63), platform)
        pygame.draw.polygon(screen, S.PANEL_BORDER, platform, 1)
        screen.fill(S.YELLOW, (preview.x + 8, preview.y + 8, 2, 12))
        page = f10.render("%d / %d" % (self.garage_index + 1, len(S.TANK_ORDER)),
                          True, S.GRAY)
        screen.blit(page, (preview.right - 12 - page.get_width(), preview.y + 8))
        pygame.draw.ellipse(screen, (24, 30, 38),
                            (preview.x + 25, 276 + dy, preview.w - 50, 18))
        source = sprites.garage_tanks[tt]
        big = pygame.transform.scale(source, (source.get_width() * 4,
                                               source.get_height() * 4))
        screen.blit(big, (preview.centerx - big.get_width() // 2, 184 + dy))
        state_text = T("in_use") if tt == self.tank_type else T("garage_owned")
        action_text = state_text if tt == self.tank_type else T("garage_choose")
        action = f12.render(action_text, True,
                            S.GREEN if tt == self.tank_type else S.YELLOW)
        screen.blit(action, (preview.centerx - action.get_width() // 2, 304 + dy))

        # 右侧资料：型号、双行以内简介、三项相对属性条。
        screen.fill(S.YELLOW, (details.x + 12, details.y + 11, 2, 14))
        name = get_font(18).render(T(f"tank_{tt}"), True, S.YELLOW)
        screen.blit(name, (details.x + 20, details.y + 8))
        desc_lines, line = [], ""
        for ch in T(f"tank_desc_{tt}"):
            if line and f12.size(line + ch)[0] > details.w - 24:
                desc_lines.append(line.strip())
                line = ch.lstrip()
            else:
                line += ch
        if line:
            desc_lines.append(line.strip())
        for i, text in enumerate(desc_lines):
            desc = f12.render(text, True, S.LIGHT_GRAY)
            screen.blit(desc, (details.x + 12, 198 + dy + i * 14))
        for line_y in (232 + dy, 304 + dy):
            pygame.draw.line(screen, S.DARK_GRAY,
                             (details.x + 12, line_y), (details.right - 12, line_y))

        configs = S.TANK_TYPES.values()
        max_speed = max(c["speed"] for c in configs)
        min_cooldown = min(c["fire_cooldown"] for c in configs)
        min_skill_cd = min(c["skill_cooldown"] for c in configs)
        stat_rows = (
            (T("garage_speed"), "%.1f" % cfg["speed"], cfg["speed"] / max_speed),
            (T("garage_rate"), "%df" % cfg["fire_cooldown"],
             min_cooldown / cfg["fire_cooldown"]),
            (T("garage_skill_cd"), "%.2fs" % (cfg["skill_cooldown"] / S.FPS),
             min_skill_cd / cfg["skill_cooldown"]),
        )
        for i, (label, value, ratio) in enumerate(stat_rows):
            y = 240 + dy + i * 20
            lab = f12.render(label, True, S.GRAY)
            val = f12.render(value, True, S.WHITE)
            screen.blit(lab, (details.x + 12, y))
            screen.blit(val, (details.right - 12 - val.get_width(), y))
            bar_x = details.x + 52
            bar_w = details.right - 12 - val.get_width() - 8 - bar_x
            pygame.draw.rect(screen, (48, 48, 56), (bar_x, y + 7, bar_w, 4))
            pygame.draw.rect(screen, S.YELLOW,
                             (bar_x, y + 7, max(3, int(bar_w * ratio)), 4))

        mag = f12.render("%s %d" % (T("garage_mag"), cfg["max_bullets"]), True, S.GRAY)
        screen.blit(mag, (details.x + 12, 312 + dy))

        # 底部型号卡片：黄框为当前预览，绿字为实际出战型号。
        for i, tank_type in enumerate(S.TANK_ORDER):
            card = pygame.Rect(40 + i * 116, 342 + dy, 104, 48)
            selected = i == self.garage_index
            self._btn_face(screen, card, selected)
            if selected:
                pygame.draw.rect(screen, S.YELLOW, card, 1)
            card_name = f14.render(T(f"tank_{tank_type}"), True,
                                   S.YELLOW if selected else S.LIGHT_GRAY)
            screen.blit(card_name, (card.centerx - card_name.get_width() // 2,
                                    card.y + 5))
            card_state = T("in_use") if tank_type == self.tank_type else T("garage_owned")
            status = f10.render(card_state, True,
                                S.GREEN if tank_type == self.tank_type else S.GRAY)
            screen.blit(status, (card.centerx - status.get_width() // 2, card.y + 30))
            self._hits["garage_tank_%d" % i] = card

        back = pygame.Rect(326, 418 + dy, 64, 26)
        hover, pressed = self._btn_face(screen, back)
        back_text = f14.render(T("cfg_back"), True, S.YELLOW if hover else S.LIGHT_GRAY)
        screen.blit(back_text, (back.centerx - back_text.get_width() // 2,
                                back.centery - back_text.get_height() // 2 + (1 if pressed else 0)))
        self._hits["garage_back"] = back
        hint = f12.render(T("hint_garage"), True, S.GRAY)
        screen.blit(hint, (back.x - 12 - hint.get_width(), 425 + dy))

    def _render_pause(self, screen):
        overlay = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*S.MENU_BG, 160))
        screen.blit(overlay, (0, 0))
        self._panel(screen, PAUSE_PANEL)
        w = S.SCREEN_WIDTH

        title = get_font(26).render(T("pause"), True, S.WHITE)
        screen.blit(title, ((w - title.get_width()) // 2, PAUSE_TITLE_Y))

        bx = PAUSE_PANEL[0] + (PAUSE_PANEL[2] - PAUSE_W) // 2
        for i, key in enumerate(("resume", "restart", "back_title", "mode_settings")):
            self._menu_button(screen, T(key), PAUSE_Y0 + i * PAUSE_PITCH,
                              i == self.pause_index, width=PAUSE_W, x=bx,
                              hit_key="pause_%d" % i)

        self._hint(screen, "hint_pause", PAUSE_HINT_Y, S.GRAY)

    def _render_end(self, screen):
        """结算页：上=战绩横条，下=排名表（人多自动分两列），底部=再来一局/返回。"""
        self._render_overlay(screen)
        w = S.SCREEN_WIDTH
        win = self.state == STATE_WIN
        f12, f14, f18 = get_font(12), get_font(14), get_font(18)

        # 上横条：左=胜负（失败附原因），右=击杀/用时 两列
        card_a = pygame.Rect(END_CARD_A)
        self._panel(screen, card_a)
        title = get_font(24).render(T("win" if win else "lose"), True,
                                    S.YELLOW if win else S.RED)
        screen.blit(title, (card_a.x + 16, card_a.y + 16))
        if not win:
            cause = f12.render(T("cause_life"), True, S.RED)
            screen.blit(cause, (card_a.x + 16, card_a.y + 58))
        elif self.parts_earned:
            gain = f14.render("+%d %s" % (self.parts_earned, T("parts")), True, S.GREEN)
            screen.blit(gain, (card_a.x + 16, card_a.y + 56))
        seconds = self.time_frames // S.FPS
        stats = ((T("kills"), self.kills), (T("time"), f"{seconds}s"))
        for i, (lab, val) in enumerate(stats):
            cx = card_a.x + 220 + i * 92
            l = f12.render(lab, True, S.GRAY)
            v = f18.render(str(val), True, S.WHITE)
            screen.blit(l, (cx - l.get_width() // 2, card_a.y + 20))
            screen.blit(v, (cx - v.get_width() // 2, card_a.y + 42))

        # 下卡片：排名表（存活者按 hp 降序，淘汰者排后；超过 6 人自动分两列）
        right = pygame.Rect(END_CARD_B)
        self._panel(screen, right)
        rtitle = f18.render(T("end_rank"), True, S.WHITE)
        screen.blit(rtitle, (right.centerx - rtitle.get_width() // 2, right.y + 12))
        head = f12.render("#", True, S.GRAY)
        screen.blit(head, (right.x + 14, right.y + 40))
        head_name = f12.render(T("end_you"), True, S.GRAY)
        screen.blit(head_name, (right.x + 38, right.y + 40))

        entries = [(self.player, self.player_name, S.YELLOW)]
        entries += [(f, f.tag, S.LIGHT_GRAY) for f in self.versus_foes]
        entries.sort(key=lambda e: (not e[0].alive, -(e[0].hp if e[0].alive else 0)))
        cols = 1 if len(entries) <= 6 else 2
        per = (len(entries) + cols - 1) // cols
        y0 = right.y + 58
        row_h = min(24, (right.bottom - 8 - y0) // max(per, 1))
        col_w = (right.w - 24) // cols
        fname = f14 if row_h >= 20 else f12
        for idx, (t, name, color) in enumerate(entries):
            c, r = divmod(idx, per)
            x = right.x + 12 + c * col_w
            y = y0 + r * row_h
            avatar = self._avatar_by_tag.get(name)
            if avatar:
                screen.blit(avatars.scaled(avatar, 14), (x, y + (row_h - 14) // 2))
                x += 18
            surf = fname.render(f"{idx + 1}. {name}", True, color)
            screen.blit(surf, (x, y + (row_h - surf.get_height()) // 2))
            st = f12.render(T("end_alive") if t.alive else T("end_dead"), True,
                            S.GREEN if t.alive else S.DARK_GRAY)
            screen.blit(st, (right.x + 12 + c * col_w + col_w - 12 - st.get_width(),
                             y + (row_h - 12) // 2))

        # 底部按钮：再来一局 / 返回（真实命中；Enter/Esc 同效）
        bx = (w - (END_BTN_W * 2 + END_BTN_GAP)) // 2
        for i, (key, hit) in enumerate((("end_again", "end_again"), ("end_back", "end_back"))):
            rect = pygame.Rect(bx + i * (END_BTN_W + END_BTN_GAP), END_BTN_Y,
                               END_BTN_W, END_BTN_H)
            hover, pressed = self._btn_face(screen, rect)
            surf = f14.render(T(key), True, S.YELLOW if hover else S.WHITE)
            screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                               rect.centery - surf.get_height() // 2 +
                               (1 if pressed else 0)))
            self._hits[hit] = rect


def _window_icon():
    """用坦克素材生成窗口图标（标题栏与任务栏共用），素材缺失时返回 None。"""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "assets", "tanks", "standard.png")
    try:
        tank = pygame.image.load(path).convert_alpha()
    except Exception:
        return None
    tank = pygame.transform.scale(tank, (tank.get_width() * 2, tank.get_height() * 2))
    icon = pygame.Surface((64, 64), pygame.SRCALPHA)
    icon.blit(tank, ((64 - tank.get_width()) // 2, (64 - tank.get_height()) // 2))
    return icon


def create_display(scale=S.SCALE):
    """创建固定尺寸窗口，并返回 (窗口 screen, 逻辑分辨率画布 logical)。"""
    screen = pygame.display.set_mode((S.SCREEN_WIDTH * scale, S.SCREEN_HEIGHT * scale))
    icon = _window_icon()
    if icon is not None:
        pygame.display.set_icon(icon)     # 替换 Pygame 默认图标
    logical = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT))
    return screen, logical


def present(screen, logical):
    """把逻辑画布整数放大后贴满窗口（最近邻取样，像素保持锐利）。"""
    pygame.transform.scale(logical, screen.get_size(), screen)
