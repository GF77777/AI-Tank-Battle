"""VersusEnv：对战竞技场自博弈 RL 环境。学习者=game.player，3 个对手共用同一 agent。

状态向量 384 维（自身 8 + 基地 1 恒 0 + 对手 4×7 + 子弹 8×5 + 地图 289 + 道具 3×4 + 元信息 6），
网络结构 384→256→256→10。1 命制：血尽即淘汰，无复活；毒圈向中心收缩。
元信息新增「到安全区边缘的有符号距离」与「离场地中心比例」，让网络能直接学躲圈。
"""

import math

import numpy as np
import pygame

from . import settings as S
from .core import STATE_LOSE, STATE_PLAYING, STATE_WIN, Game

# 状态向量维度：自身8 + 基地1(恒0) + 对手4×7 + 子弹8×5 + 地图17×17 + 道具3×4 + 元信息6 = 384
STATE_DIM = 384
MAX_ENEMIES = 4                # 状态向量保留 4 个对手槽（对战实际 3 个，空槽补 0）
MAX_BULLETS = 8

# 各段在状态向量中的起始下标
_IDX_PLAYER = 0
_IDX_BASE = 8
_IDX_ENEMY = 9
_IDX_BULLET = _IDX_ENEMY + MAX_ENEMIES * 7          # 37
_IDX_MAP = _IDX_BULLET + MAX_BULLETS * 5            # 77
_IDX_ITEMS = _IDX_MAP + S.MAP_ROWS * S.MAP_COLS     # 366
_IDX_META = _IDX_ITEMS + S.MAX_ITEMS * 4            # 378

_ITEM_KIND_IDX = {kind: i for i, kind in enumerate(S.ITEM_TYPES)}   # heal0 fire1 shield2 mine3


def decode_action(action):
    """动作编号 -> (方向常量或 None, 是否开火)。"""
    if 1 <= action <= 4:
        return action - 1, False
    if 5 <= action <= 8:
        return action - 5, True
    if action == 9:
        return None, True
    return None, False


def _in_forest(game, tank):
    """坦克中心所在格是否为草地（与 core.Game.in_forest 同规则）。"""
    c = min(int((tank.x + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_COLS - 1)
    r = min(int((tank.y + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_ROWS - 1)
    return game.grid[r][c] == S.FOREST


def build_foe_state(game, me, foes):
    """对战模式 AI 视角的 384 维状态：me 占自身槽，foes（玩家+其他AI）占敌人槽；
    基地槽恒 0；子弹 owner is me 记 +1 否则 -1；元信息=存活对手比例/自身血量比例/
    毒圈半径比例/收缩倒计时比例/离安全区边缘有符号距离/离中心比例。
    草地隐藏：观察者不在草地时，草地里的对手从对手槽隐去（单向可见）。"""
    v = np.zeros(STATE_DIM, dtype=np.float32)
    norm_x = S.SCREEN_WIDTH - S.TANK_SIZE
    norm_y = S.TILE_SIZE * S.MAP_ROWS - S.TANK_SIZE

    # 自身 8：x、y、朝向 one-hot(4)、存活、无敌计时
    v[0] = me.x / norm_x
    v[1] = me.y / norm_y
    v[2 + me.direction] = 1.0
    v[6] = 1.0 if me.alive else 0.0
    v[7] = me.invincible / S.RESPAWN_INVINCIBLE

    # 基地 1：对战无基地，恒 0

    # 对手 4×7：x、y、朝向 one-hot(4)、存活（不足补 0）
    # 可见性 = 视野圆内（与玩家同规则）且 草地单向隐身（我在草外时草内对手不可见）
    me_hidden = _in_forest(game, me)
    view_px = S.VIEW_RADIUS_TILES * S.TILE_SIZE
    mcx, mcy = me.x + S.TANK_SIZE / 2, me.y + S.TANK_SIZE / 2

    def _seen(t):
        if math.hypot(t.x + S.TANK_SIZE / 2 - mcx, t.y + S.TANK_SIZE / 2 - mcy) > view_px:
            return False                          # 视野外
        return me_hidden or not _in_forest(game, t)  # 草地单向隐身

    visible = [t for t in foes if t.alive and _seen(t)]
    i = _IDX_ENEMY
    for e in visible[:MAX_ENEMIES]:
        v[i] = e.x / norm_x
        v[i + 1] = e.y / norm_y
        v[i + 2 + e.direction] = 1.0
        v[i + 6] = 1.0
        i += 7

    # 子弹 8×5：x、y、vx、vy、归属（自己的弹 1 / 他人的弹 -1 / 空位 0）；视野外不可见
    i = _IDX_BULLET
    for b in game.bullets[:MAX_BULLETS]:
        if math.hypot(b.x - mcx, b.y - mcy) > view_px:
            i += 5
            continue
        dx, dy = S.DIR_VECTORS[b.direction]
        v[i] = b.x / S.SCREEN_WIDTH
        v[i + 1] = b.y / (S.TILE_SIZE * S.MAP_ROWS)
        v[i + 2] = float(dx)
        v[i + 3] = float(dy)
        v[i + 4] = 1.0 if b.owner is me else -1.0
        i += 5

    # 地图 289：每格地形编码 ÷5（砖墙会被打掉，是动态信息）
    v[_IDX_MAP:_IDX_MAP + S.MAP_ROWS * S.MAP_COLS] = (
        np.asarray(game.grid, dtype=np.float32).reshape(-1) / 5.0
    )

    # 道具 3×4：x、y、种类（kind/3）、有效标志；按剩余 ttl 降序取前 3，空槽补 0；视野外不可见（与玩家同规则）
    items = sorted(
        (it for it in game.items
         if it.alive and math.hypot(it.x + it.SIZE / 2 - mcx, it.y + it.SIZE / 2 - mcy) <= view_px),
        key=lambda it: -it.ttl,
    )
    i = _IDX_ITEMS
    for it in items[:S.MAX_ITEMS]:
        v[i] = it.x / S.SCREEN_WIDTH
        v[i + 1] = it.y / (S.TILE_SIZE * S.MAP_ROWS)
        v[i + 2] = _ITEM_KIND_IDX[it.kind] / 3.0
        v[i + 3] = 1.0
        i += 4

    # 元信息 6：存活对手比例、自身血量比例、毒圈半径比例、距下次收缩倒计时比例、
    #            离安全区边缘的有符号距离（>0 圈内 / <0 圈外）、离场地中心比例
    alive_foes = sum(1 for t in foes if t.alive)
    v[_IDX_META] = alive_foes / max(len(foes), 1)
    me_hp = game.player.hp if me is game.player else getattr(me, "hp", 1)
    me_max_hp = getattr(me, "max_hp", S.VERSUS_HP)
    v[_IDX_META + 1] = max(me_hp, 0) / max(me_max_hp, 1)
    v[_IDX_META + 2] = game.zone_radius / S.ZONE_INITIAL_RADIUS
    v[_IDX_META + 3] = game.zone_timer / S.ZONE_SHRINK_INTERVAL
    ctr = S.MAP_ROWS // 2
    c = min(int((me.x + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_COLS - 1)
    r = min(int((me.y + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_ROWS - 1)
    cheb = max(abs(r - ctr), abs(c - ctr))
    v[_IDX_META + 4] = (game.zone_radius - cheb) / S.ZONE_INITIAL_RADIUS
    v[_IDX_META + 5] = cheb / ctr
    return v


class VersusEnv:
    """自博弈 FFA 环境：学习者=game.player，3 个对手由 set_opponents 注入的同一 agent 驱动。

    动作空间（10）：0=不动，1~4=上/下/左/右，5~8=移动+射击，9=原地射击。
    每 4 帧（FRAME_SKIP）做一次决策，决策间重复执行该动作（等效 ~15 决策/秒）。
    只学学习者视角的 transition（标准自博弈简化）；对手与学习者在每一步共享 ε。
    """

    def __init__(self):
        if not pygame.get_init():
            pygame.init()
        S.AI_RANDOM_TANK = False      # 训练/评估恒 standard，保证自博弈对手分布稳定
        self.game = Game()
        self.game.num_combatants = 4   # 训练恒 4 人局（与玩家侧 2-10 可选隔离，NUM_COMBATANTS_MAX 勿用）
        # Game 的对战驱动钩子：状态构造函数与动作解码器
        self.game._build_foe_state = build_foe_state
        self.game._decode_vs_action = decode_action
        self.decision_steps = 0
        self._kills0 = 0
        self._lives0 = S.VERSUS_LIVES
        self._prev_xy = None        # 上一步玩家坐标（算移动奖励）
        self._shots0 = 0            # 上一步累计开火数
        self._hits0 = 0             # 上一步累计命中数

    def set_opponents(self, agent):
        """注入对手驱动（自博弈：与学习者同一 agent）。"""
        self.game.foe_agent = agent

    # ---------------- Gym 风格接口 ----------------

    def reset(self):
        """开新一局，返回初始状态向量。"""
        self.game._reset_battle()
        self.game.state = STATE_PLAYING
        self.decision_steps = 0
        self._kills0 = 0
        self._lives0 = S.VERSUS_LIVES
        self._prev_xy = (self.game.player.x, self.game.player.y)
        self._shots0 = self.game.player.shots_fired
        self._hits0 = self.game.player.hits_landed
        return self._state()

    def step(self, action, epsilon=0.0):
        """执行一个决策（内部推进 FRAME_SKIP 帧），返回 (state, reward, done, info)。

        epsilon: 本步对手的探索率（自博弈：对手与学习者共享 ε）。
        """
        self.game.foe_epsilon = epsilon
        direction, fire = decode_action(action)
        for _ in range(S.FRAME_SKIP):
            if self.game.state != STATE_PLAYING:
                break
            self.game.update(input_dir=direction, input_fire=fire)

        g = self.game
        p = g.player
        # 移动奖励：鼓励到处走、抑制蹲点
        moved = 0.0
        if self._prev_xy is not None:
            moved = math.hypot(p.x - self._prev_xy[0], p.y - self._prev_xy[1])
        self._prev_xy = (p.x, p.y)

        # 开火/命中：抑制扫射，有效命中给正反馈
        dshot = p.shots_fired - self._shots0
        dhit = p.hits_landed - self._hits0
        self._shots0 = p.shots_fired
        self._hits0 = p.hits_landed

        # 安全区：圈外重罚；贴边（<=1 格）轻罚，引导提前撤离
        zone_pen = 0.0
        if not g._in_zone(p):
            zone_pen = S.VS_R_ZONE_OUT
        elif g.zone_radius > 0:
            ctr = S.MAP_ROWS // 2
            c = min(int((p.x + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_COLS - 1)
            r = min(int((p.y + S.TANK_SIZE / 2) // S.TILE_SIZE), S.MAP_ROWS - 1)
            if g.zone_radius - max(abs(r - ctr), abs(c - ctr)) <= 1:
                zone_pen = S.VS_R_ZONE_EDGE

        reward = ((g.kills - self._kills0) * S.VS_R_KILL
                  + (self._lives0 - g.lives) * S.VS_R_DEATH
                  + S.VS_R_STEP
                  + (S.VS_R_MOVE if moved >= 3.0 else S.VS_R_IDLE)
                  + zone_pen
                  + dshot * S.VS_R_SHOT
                  + dhit * S.VS_R_HIT)
        self._kills0 = g.kills
        self._lives0 = g.lives
        self.decision_steps += 1

        # 1 命制：被淘汰即终局（VS_R_DEATH 已含终局惩罚），胜利无额外叠加
        truncated = g.state == STATE_PLAYING and self.decision_steps >= S.MAX_DECISION_STEPS
        done = g.state != STATE_PLAYING or truncated
        info = {
            "kills": g.kills,
            "win": g.state == STATE_WIN,
            "steps": self.decision_steps,
            "score": g.score,
            "truncated": truncated,
            "shots": p.shots_fired,
            "hits": p.hits_landed,
        }
        return self._state(), reward, done, info

    def _state(self):
        """学习者视角状态（me=player，foes=3 个 AI）。"""
        return build_foe_state(self.game, self.game.player, self.game.versus_foes)
