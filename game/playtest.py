"""试玩日志：每局对战结束追加一行 CSV 到 playtest/sessions.csv。

只在人类入口（main.py）开启；AI 训练/评估路径默认关闭，不污染数据。
"""

import csv
import os
from datetime import datetime

from . import settings as S

LOG_DIR = "playtest"
LOG_FILE = os.path.join(LOG_DIR, "sessions.csv")

_HEADER = ["session", "ts", "result", "lose_reason",
           "score", "kills", "lives_left", "time_sec"]


class PlaytestLogger:
    """start_session() 开一局；record(game, win) 在每局胜负判定时调用。"""

    def __init__(self):
        self.session = None
        self._file = None
        self._writer = None

    def _ensure_file(self):
        if self._file is not None:
            return
        os.makedirs(LOG_DIR, exist_ok=True)
        is_new = not os.path.exists(LOG_FILE)
        self._file = open(LOG_FILE, "a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        if is_new:
            self._writer.writerow(_HEADER)
            self._file.flush()

    def start_session(self):
        """一局对战开始，生成会话 ID。"""
        self.session = datetime.now().strftime("%Y%m%d_%H%M%S")

    def record(self, game, win):
        self._ensure_file()
        self._writer.writerow([
            self.session,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "win" if win else "lose",
            game.lose_reason or "",
            game.score,
            game.kills,
            max(game.lives, 0),
            round(game.time_frames / S.FPS, 1),
        ])
        self._file.flush()
