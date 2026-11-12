"""玩家/AI 名片池：扫描 assets/avatars/*.png，文件名（去扩展名）即名字。

头像来源：名片页「导入头像」按钮（复制进本目录），或直接把图片丢进 assets/avatars/。
目录为空时使用内置的像素头像（程序绘制，见 _builtin_avatar），保证名片页/对局都有头像可换。
"""

import os
import random
import shutil

import pygame

_AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "assets", "avatars")
_EXT = (".png", ".jpg", ".jpeg")

_pool = None          # [(name, surface)] 懒加载缓存
_scaled_cache = {}    # (id(surface), size) -> surface 缩放缓存


def pool():
    """懒加载扫描头像目录；返回 [(名字, 原图 surface)]。"""
    global _pool
    if _pool is None:
        _pool = []
        try:
            files = sorted(os.listdir(_AVATAR_DIR))
        except OSError:
            files = []
        for fn in files:
            stem, ext = os.path.splitext(fn)
            if ext.lower() not in _EXT or not stem:
                continue
            try:
                img = pygame.image.load(os.path.join(_AVATAR_DIR, fn))
                if pygame.display.get_surface() is not None:
                    img = img.convert_alpha()
            except Exception:
                continue                    # 坏文件跳过，不影响其他
            _pool.append((stem, img))
        if not _pool:                       # 无素材：用内置像素头像兜底
            _pool = [(_FALLBACK_NAMES[i], _builtin_avatar(c))
                     for i, c in enumerate(_BG_COLORS)]
    return _pool


_BG_COLORS = ((200, 70, 60), (60, 120, 200), (80, 180, 90), (220, 170, 60),
              (150, 90, 200), (60, 180, 180), (200, 90, 160), (110, 110, 120),
              (170, 120, 70), (90, 140, 60), (70, 100, 190), (190, 130, 40))


def _builtin_avatar(color):
    """程序绘制的像素头像（纯色底 + 眼睛 + 嘴），不依赖字体与图片素材。"""
    s = pygame.Surface((48, 48))
    s.fill(color)
    dark = tuple(max(0, c - 80) for c in color)
    pygame.draw.rect(s, dark, (0, 0, 48, 48), 3)
    for ex in (11, 27):                     # 两只眼睛
        pygame.draw.rect(s, (245, 245, 245), (ex, 15, 10, 9))
        pygame.draw.rect(s, (30, 30, 30), (ex + 3, 18, 4, 4))
    pygame.draw.rect(s, (40, 40, 40), (16, 32, 16, 5))      # 嘴
    return s


def assign(n, exclude=()):
    """随机不重复抽 n 个 (名字, surface)；池不足允许重复；空池返回 []。"""
    available = [item for item in pool() if item[0] not in exclude]
    if not available:
        return []
    random.shuffle(available)
    picked = available[:n]
    i = 0
    while len(picked) < n:                  # 池不足时循环补齐
        picked.append(available[i % len(available)])
        i += 1
    return picked


# AI 名字池（头像与名字解耦：头像随机取素材，名字从这里随机匹配）
_FALLBACK_NAMES = ("铁锤", "疾风", "夜鹰", "赤狐", "破晓", "黑曜",
                   "雷鸣", "霜刃", "幽影", "赤焰", "铁壁", "流星")


def fallback_names(n, exclude=()):
    """随机产出 n 个不重复的备用名字（与 exclude 也不重复）。"""
    names = [x for x in _FALLBACK_NAMES if x not in exclude]
    random.shuffle(names)
    out = []
    while len(out) < n and names:
        out.append(names.pop())
    while len(out) < n:                     # 名字用尽时加序号兜底（不会重名）
        out.append("%s%d" % (_FALLBACK_NAMES[len(out) % len(_FALLBACK_NAMES)], len(out) + 1))
    return out


def by_filename(stem):
    """按文件名取 (名字, surface)；不存在返回 None。"""
    for name, img in pool():
        if name == stem:
            return name, img
    return None


def reload():
    """清空缓存并重新扫描头像目录（导入新图片后调用）。"""
    global _pool
    _pool = None
    _scaled_cache.clear()


def import_file(path):
    """把本地图片导入头像池（复制进 assets/avatars），返回 (名字, surface)。

    同名文件自动加序号，不覆盖已有头像；失败返回 None。
    """
    ext = os.path.splitext(path)[1].lower()
    if ext not in _EXT:
        return None
    try:
        os.makedirs(_AVATAR_DIR, exist_ok=True)
        stem = os.path.splitext(os.path.basename(path))[0] or "avatar"
        name = stem
        dst = os.path.join(_AVATAR_DIR, name + ext)
        i = 2
        while os.path.exists(dst) and os.path.abspath(dst) != os.path.abspath(path):
            name = "%s_%d" % (stem, i)
            dst = os.path.join(_AVATAR_DIR, name + ext)
            i += 1
        if os.path.abspath(dst) != os.path.abspath(path):
            shutil.copyfile(path, dst)
        reload()
        return by_filename(name)
    except Exception:
        return None


def next_of(name, step=1):
    """按池顺序取相邻头像（循环）；池空返回 None。"""
    items = pool()
    if not items:
        return None
    names = [n for n, _ in items]
    idx = names.index(name) if name in names else -step
    return items[(idx + step) % len(items)]


def scaled(surface, size):
    """缩放头像到 size x size（带缓存）；大图（照片）平滑缩放更清晰，像素头像保持锐利。"""
    key = (id(surface), size)
    if key not in _scaled_cache:
        if surface.get_width() >= size * 4:
            _scaled_cache[key] = pygame.transform.smoothscale(surface, (size, size))
        else:
            _scaled_cache[key] = pygame.transform.scale(surface, (size, size))
    return _scaled_cache[key]
