"""游戏实体：坦克（玩家/AI 对手共用 PlayerTank）、子弹、爆炸。"""

import math

import pygame

from . import settings as S


def tile_to_px(col, row):
    """格子坐标 -> 坦克左上角像素（28px 坦克居中于 32px 格子）。"""
    return col * S.TILE_SIZE + 2, row * S.TILE_SIZE + 2


class Tank:
    """坦克基类：位置/朝向/移动请求/开火冷却。移动碰撞由 Game 裁决。"""

    def __init__(self, x, y, direction, speed, is_player):
        self.x = float(x)
        self.y = float(y)
        self.direction = direction
        self.speed = speed
        self.is_player = is_player
        self.alive = True
        self.fire_cooldown = 0          # 剩余冷却帧
        self.invincible = 0             # 无敌/出生保护剩余帧
        self.max_hp = S.VERSUS_HP       # 100 点整数 HP，显示时直接对应百分比
        self.hp = self.max_hp
        self.fire_stacks = 0            # 火力道具叠层（冷却 ×0.7^stacks）
        self.fire_cooldown_max = S.PLAYER_FIRE_COOLDOWN if is_player else 2 * S.PLAYER_FIRE_COOLDOWN
        self.shots_fired = 0            # 累计开火次数（子弹/范围技），训练奖励用
        self.hits_landed = 0            # 累计命中次数，训练奖励用

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), S.TANK_SIZE, S.TANK_SIZE)

    def set_direction(self, d):
        """转向；90 度转向时把垂直轴对齐到 4px 网格，保证能穿过单格通道。"""
        if d == self.direction:
            return
        self.direction = d
        if d in (S.UP, S.DOWN):
            self.x = round(self.x / S.ALIGN_GRID) * S.ALIGN_GRID
        else:
            self.y = round(self.y / S.ALIGN_GRID) * S.ALIGN_GRID

    def tick_timers(self):
        if self.fire_cooldown > 0:
            self.fire_cooldown -= 1
        if self.invincible > 0:
            self.invincible -= 1
        if self.reload_timer > 0:
            self.reload_timer -= 1
            if self.reload_timer == 0:
                self.mag = self.mag_size        # 换弹完成，弹匣补满

    def make_bullet(self, piercing=False, max_frames=None, target=None):
        """在炮口位置生成子弹。piercing=True 为穿甲弹（穿砖穿人，被钢板挡）。
        max_frames: 射程帧数，None=不限（全图）。target: 锁定的追踪目标（None=直飞）。"""
        dx, dy = S.DIR_VECTORS[self.direction]
        cx = self.x + S.TANK_SIZE / 2
        cy = self.y + S.TANK_SIZE / 2
        bx = cx + dx * (S.TANK_SIZE / 2) - S.BULLET_SIZE / 2
        by = cy + dy * (S.TANK_SIZE / 2) - S.BULLET_SIZE / 2
        if piercing:
            self.skill_cooldown = self.skill_cooldown_max
        else:
            self.fire_cooldown = self.fire_cooldown_max
        self.shots_fired += 1
        damage = self.skill_damage if piercing else self.attack_damage
        return Bullet(bx, by, self.direction, self.is_player, piercing,
                      max_frames, target, damage)


class PlayerTank(Tank):
    def __init__(self, x, y, tank_type=S.DEFAULT_TANK):
        cfg = S.TANK_TYPES[tank_type]
        super().__init__(x, y, S.UP, cfg["speed"], is_player=True)
        self.tank_type = tank_type
        self.base_fire_cooldown = cfg["fire_cooldown"]   # 基准冷却（火力道具在此基础上缩放）
        self.fire_cooldown_max = cfg["fire_cooldown"]
        self.max_bullets = cfg["max_bullets"]          # 场上子弹上限（火力道具另加）
        self.attack_damage = cfg["attack_damage"]     # 普攻每次有效命中伤害
        self.skill_damage = cfg["skill_damage"]       # 穿甲/冲击波伤害；疾冲为 0
        self.skill_cooldown_max = cfg["skill_cooldown"]  # 技能冷却总帧数
        self.skill_cooldown = 0                        # 技能剩余冷却帧
        self.fire_mode = cfg["fire_mode"]              # single/burst/fan
        self.burst_gap = cfg.get("burst_gap", 6)       # burst：二连发间隔帧
        self.bullet_frames = cfg.get("bullet_frames")  # 普通弹射程帧数（None=全图）
        self.piercing_frames = cfg.get("piercing_frames")  # 穿甲弹射程帧数（None=全图）
        self.fan_radius = cfg.get("fan_radius", 0)     # fan：扇形半径（px）
        self.fan_half_angle = cfg.get("fan_half_angle", 30)
        self.shock_radius = cfg.get("shock_radius", cfg.get("fan_radius", 0))  # 冲击波半径（px）
        self.skill = cfg.get("skill", "piercing")       # piercing/dash/shockwave
        self.dash_tiles = cfg.get("dash_tiles", 3)     # dash：疾冲格数
        self.dash_charges_max = cfg.get("dash_charges", 1)  # 疾冲储存上限
        self.dash_charges = self.dash_charges_max      # 当前可用次数
        self.dash_recharge = 0                         # 下一次充能剩余帧
        self.burst_pending = 0                        # AI burst：待补发数（0/1）
        self.burst_timer = 0                          # AI burst：补发倒计时帧
        self.fan_flash = 0                            # AI fan：扇面闪光剩余帧（玩家用 Game.fan_flash）
        self.mag_size = S.MAG_SIZES[tank_type]        # 弹匣容量（打空自动换弹）
        self.mag = self.mag_size                      # 当前余量
        self.reload_frames = S.RELOAD_FRAMES[tank_type]  # 换弹总时长（帧）
        self.reload_timer = 0                         # 换弹剩余帧（>0 = 换弹中，禁射）
        self.invincible = S.RESPAWN_INVINCIBLE

    def tick_timers(self):
        super().tick_timers()
        if self.skill_cooldown > 0:
            self.skill_cooldown -= 1
        # 疾冲独立充能：每段冷却恢复 1 次，直到存满。
        if self.skill == "dash" and self.dash_charges < self.dash_charges_max:
            self.dash_recharge -= 1
            if self.dash_recharge <= 0:
                self.dash_charges += 1
                self.dash_recharge = (self.skill_cooldown_max
                                      if self.dash_charges < self.dash_charges_max else 0)


class Bullet:
    def __init__(self, x, y, direction, from_player, piercing=False, max_frames=None,
                 target=None, damage=0):
        self.x = float(x)
        self.y = float(y)
        self.direction = direction
        self.from_player = from_player
        self.piercing = piercing    # 穿甲弹：穿砖穿人，被钢板/边界挡
        self.frames_left = max_frames  # 射程帧数，None=不限；到 0 消亡
        self.alive = True
        self.owner = None           # 对战模式指回发射者坦克；闯关模式不用（None）
        self.target = target        # 锁定的追踪目标（None=直线飞）
        self.damage = damage        # 每次有效命中扣除的 HP
        dx, dy = S.DIR_VECTORS[direction]
        self.vx = float(dx)         # 速度单位向量（追踪时逐帧旋转）
        self.vy = float(dy)

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), S.BULLET_SIZE, S.BULLET_SIZE)

    def update(self):
        # 追踪：目标存活则按每帧最大转角转向目标中心；目标死亡保持直飞
        if self.target is not None and self.target.alive:
            tx = self.target.x + S.TANK_SIZE / 2 - (self.x + S.BULLET_SIZE / 2)
            ty = self.target.y + S.TANK_SIZE / 2 - (self.y + S.BULLET_SIZE / 2)
            if tx or ty:
                cur = math.atan2(self.vy, self.vx)
                want = math.atan2(ty, tx)
                diff = (want - cur + math.pi) % (2 * math.pi) - math.pi
                turn = max(-S.BULLET_HOMING_TURN, min(S.BULLET_HOMING_TURN, diff))
                cur += turn
                self.vx, self.vy = math.cos(cur), math.sin(cur)
        self.x += self.vx * S.BULLET_SPEED
        self.y += self.vy * S.BULLET_SPEED
        # direction 同步为速度主导轴（击退方向 / RL 状态向量复用）
        if abs(self.vx) >= abs(self.vy):
            self.direction = S.RIGHT if self.vx > 0 else S.LEFT
        else:
            self.direction = S.DOWN if self.vy > 0 else S.UP
        if self.frames_left is not None:
            self.frames_left -= 1
            if self.frames_left <= 0:
                self.alive = False
        if (self.x < 0 or self.y < 0
                or self.x > S.SCREEN_WIDTH - S.BULLET_SIZE
                or self.y > S.TILE_SIZE * S.MAP_ROWS - S.BULLET_SIZE):
            self.alive = False


class Item:
    """地面道具：kind ∈ heal/fire/shield/mine；ttl 到 0 消失。占满 1 格。"""

    SIZE = S.TILE_SIZE

    def __init__(self, col, row, kind, ttl):
        self.x = col * S.TILE_SIZE + (S.TILE_SIZE - self.SIZE) // 2
        self.y = row * S.TILE_SIZE + (S.TILE_SIZE - self.SIZE) // 2
        self.kind = kind
        self.ttl = ttl
        self.alive = True

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.SIZE, self.SIZE)


class Explosion:
    """三帧像素爆炸：普通命中 12 帧，淘汰 24 帧。"""

    DURATIONS = {"hit": 12, "kill": 24}

    def __init__(self, x, y, kind="hit"):
        self.x = x
        self.y = y
        self.kind = kind
        self.timer = self.DURATIONS[kind]

    @property
    def frame(self):
        duration = self.DURATIONS[self.kind]
        idx = (duration - self.timer) // (duration // 3)
        return min(idx, 2)

    @property
    def done(self):
        return self.timer <= 0

    def update(self):
        self.timer -= 1


class PixelParticle:
    """无碰撞的 1～2px 粒子，仅做位置积分与寿命计时。"""

    def __init__(self, x, y, vx, vy, color, size, life, behind=False):
        self.x = float(x)
        self.y = float(y)
        self.vx = vx
        self.vy = vy
        self.color = color
        self.size = size
        self.timer = life
        self.behind = behind

    @property
    def done(self):
        return self.timer <= 0

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.timer -= 1


class Afterimage:
    """疾冲经过位置的青蓝残影，12 帧淡出。"""

    DURATION = 12

    def __init__(self, sprite, x, y, color=(70, 180, 255)):
        self.sprite = sprite.copy()
        tint = pygame.Surface(self.sprite.get_size(), pygame.SRCALPHA)
        tint.fill((*color, 220))
        self.sprite.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.sprite.set_alpha(120)
        self.x = x
        self.y = y
        self.timer = self.DURATION

    @property
    def done(self):
        return self.timer <= 0

    def update(self):
        self.timer -= 1
        self.sprite.set_alpha(max(0, int(120 * self.timer / self.DURATION)))
