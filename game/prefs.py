"""用户偏好持久化：prefs.json 存音乐/音效/人数/对手名字/玩家名片，损坏时回默认值。"""

import json
import os

_DEFAULT = {"music": True, "sfx": True, "master_volume": 100, "sfx_volume": 100,
            "players": 4, "name": "玩家", "avatar": "",
            "keys": {}, "parts": 0, "enemy_names": False}
_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "prefs.json")


def load():
    """读取偏好；文件缺失/损坏/键缺失/类型不符时用默认值补齐。"""
    prefs = dict(_DEFAULT)
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, default in _DEFAULT.items():
            if key in data and isinstance(data[key], type(default)):
                prefs[key] = data[key]
    except (OSError, ValueError):
        pass
    prefs["music"] = bool(prefs["music"])
    prefs["sfx"] = bool(prefs["sfx"])
    for key in ("master_volume", "sfx_volume"):
        if isinstance(prefs[key], bool):       # bool 是 int 子类，音量不接受布尔值
            prefs[key] = _DEFAULT[key]
        prefs[key] = max(0, min(100, prefs[key]))
    # 键位只保留 int 值（脏数据丢弃，回落默认）
    prefs["keys"] = {k: v for k, v in prefs["keys"].items() if isinstance(v, int)}
    return prefs


def save(prefs):
    """覆盖写入；失败静默（不影响游戏运行）。"""
    try:
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False)
    except OSError:
        pass
