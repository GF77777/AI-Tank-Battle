"""代码合成音效：numpy 生成波形 -> pygame.mixer.Sound，零外部素材。

无音频设备 / mixer 初始化失败时自动静音降级（enabled=False），
保证 headless 训练与评估不受影响。
"""

import numpy as np
import pygame

FALLBACK_RATE = 22050
_MASTER_VOLUME = 0.45


def _sweep(rate, f0, f1, dur, wave="sine", volume=0.5, curve=1.0):
    """频率从 f0 线性扫到 f1 的短音，末段按幂次衰减。"""
    n = int(rate * dur)
    t = np.arange(n) / rate
    freq = np.linspace(f0, f1, n)
    phase = 2 * np.pi * np.cumsum(freq) / rate
    sig = np.sign(np.sin(phase)) * 0.6 if wave == "square" else np.sin(phase)
    env = np.power(1.0 - np.linspace(0.0, 1.0, n), curve)
    attack = max(int(rate * 0.004), 1)
    env[:attack] *= np.linspace(0.0, 1.0, attack)
    return sig * env * volume


def _noise(rate, dur, volume=0.6, smooth=4, seed=7):
    """带简单低通的噪声爆发，指数衰减；固定局部种子保证可复现。"""
    n = int(rate * dur)
    rng = np.random.default_rng(seed)
    sig = rng.uniform(-1.0, 1.0, n)
    sig = np.convolve(sig, np.ones(smooth) / smooth, mode="same")
    sig /= max(np.max(np.abs(sig)), 1e-6)
    env = np.exp(-np.linspace(0.0, 6.0, n))
    return sig * env * volume


def _mix(*signals):
    """按最长音轨补零叠加，峰值过高时整体等比压到 0.95。"""
    mixed = np.zeros(max(len(sig) for sig in signals), dtype=np.float64)
    for sig in signals:
        mixed[:len(sig)] += sig
    peak = np.max(np.abs(mixed))
    if peak > 0.95:
        mixed *= 0.95 / peak
    return mixed


def _notes(rate, freqs, dur, wave="sine", volume=0.4):
    """把一串音符拼成琶音。"""
    return np.concatenate([_sweep(rate, f, f, dur, wave, volume, curve=0.6) for f in freqs])


def _to_sound(samples):
    """浮点波形 -> pygame.Sound（按 mixer 的声道数组装 int16）。"""
    channels = pygame.mixer.get_init()[2]
    data = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    if channels == 2:
        data = np.repeat(data[:, None], 2, axis=1)
    return pygame.sndarray.make_sound(np.ascontiguousarray(data))


class Audio:
    """音效池：初始化一次，play(name) 播放；失败时静默。"""

    def __init__(self):
        self.enabled = False
        self.sounds = {}
        self.music_on = True             # 音乐开关（占位：当前无 BGM）
        self.sfx_on = True               # 音效开关
        self.master_volume = 100         # 总音量百分比
        self.sfx_volume = 100            # 音效音量百分比
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            info = pygame.mixer.get_init()
            if not info:
                return
            rate = info[0]
            # 核心战斗音效：方波保留 FC 质感，低频与噪声补齐力度和层次。
            shoot_scout = _mix(
                _sweep(rate, 1250, 520, 0.055, "square", 0.18, curve=1.4),
                _noise(rate, 0.025, 0.08, smooth=2, seed=11))
            shoot_standard = _mix(
                _sweep(rate, 760, 180, 0.085, "square", 0.20, curve=1.3),
                _sweep(rate, 180, 70, 0.070, "sine", 0.10, curve=1.8),
                _noise(rate, 0.035, 0.07, smooth=3, seed=13))
            shoot_heavy = _mix(
                _sweep(rate, 380, 80, 0.130, "square", 0.20, curve=1.5),
                _sweep(rate, 120, 45, 0.130, "sine", 0.17, curve=1.8),
                _noise(rate, 0.110, 0.16, smooth=6, seed=17))
            hit = _mix(
                _noise(rate, 0.090, 0.24, smooth=2, seed=19),
                _sweep(rate, 1500, 900, 0.035, "square", 0.10, curve=1.2),
                _sweep(rate, 210, 70, 0.085, "square", 0.14, curve=1.8))
            kill = _mix(
                _noise(rate, 0.320, 0.50, smooth=5, seed=23),
                _sweep(rate, 260, 45, 0.260, "square", 0.18, curve=1.7),
                _sweep(rate, 95, 38, 0.300, "sine", 0.22, curve=2.0))
            self.sounds = {
                "shoot": _to_sound(_sweep(rate, 880, 240, 0.07, "square", 0.22)),
                "explosion": _to_sound(_noise(rate, 0.28, 0.55)),
                "pickup": _to_sound(_notes(rate, (660, 990), 0.08, "sine", 0.35)),
                "win": _to_sound(_notes(rate, (523, 659, 784, 1047), 0.11, "square", 0.28)),
                "lose": _to_sound(_notes(rate, (392, 330, 262), 0.18, "square", 0.28)),
                "shoot_scout": _to_sound(shoot_scout),
                "shoot_standard": _to_sound(shoot_standard),
                "shoot_heavy": _to_sound(shoot_heavy),
                "hit": _to_sound(hit),
                "kill": _to_sound(kill),
            }
            self.enabled = True
        except (pygame.error, ValueError):
            self.enabled = False
            self.sounds = {}

    def set_music(self, on):
        """音乐开关（占位：当前无 BGM，待加入后在此 start/stop 循环）。"""
        self.music_on = bool(on)

    def set_sfx(self, on):
        self.sfx_on = bool(on)

    def set_master_volume(self, value):
        self.master_volume = max(0, min(100, int(value)))

    def set_sfx_volume(self, value):
        self.sfx_volume = max(0, min(100, int(value)))

    def play(self, name, volume=1.0):
        if not self.enabled or not self.sfx_on:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        try:
            channel = pygame.mixer.find_channel()
            if channel is not None:
                # 音量属于本次 Channel，避免 AI 播放改变玩家同款音效。
                channel.set_volume(
                    _MASTER_VOLUME * self.master_volume / 100
                    * self.sfx_volume / 100 * volume)
                channel.play(snd)
        except pygame.error:
            pass
