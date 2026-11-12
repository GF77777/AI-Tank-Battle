"""训练曲线绘制：读 CSV，用 pygame 自绘 models/train_curve.png（不依赖 matplotlib）。"""

import csv
import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game.core import get_font

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE, "models")
TRAIN_LOG = os.path.join(MODELS_DIR, "train_log.csv")
EVAL_LOG = os.path.join(MODELS_DIR, "eval_log.csv")
OUT_PNG = os.path.join(MODELS_DIR, "train_curve.png")

W, H = 960, 640
WHITE = (252, 252, 252)
GRID = (224, 224, 224)
AXIS = (90, 90, 90)
TEXT = (40, 40, 40)
C_RAW = (170, 200, 235)
C_MA = (30, 90, 180)
C_WIN = (200, 60, 50)
C_KILL = (40, 150, 70)


def read_train_rewards(path):
    if not os.path.exists(path):
        return []
    rewards = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rewards.append(float(row["reward"]))
    return rewards


def read_eval_rows(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "ep": int(row["train_episode"]),
                "win": float(row["eval_win_rate"]),
                "kills": float(row["eval_avg_kills"]),
            })
    return rows


def moving_avg(values, k=20):
    out = []
    for i in range(len(values)):
        lo = max(0, i - k + 1)
        out.append(sum(values[lo:i + 1]) / (i - lo + 1))
    return out


def x_at(i, n, panel):
    if n <= 1:
        return panel.left
    return panel.left + panel.width * (i / (n - 1))


def y_at(v, lo, hi, panel):
    if hi - lo < 1e-9:
        hi = lo + 1.0
    return panel.bottom - panel.height * (v - lo) / (hi - lo)


def draw_panel_frame(screen, panel, ticks, fmt, color=TEXT, right_axis=False):
    pygame.draw.rect(screen, AXIS, panel, 1)
    small = get_font(13)
    for t in ticks:
        y = int(y_at(t, ticks[0], ticks[-1], panel))
        pygame.draw.line(screen, GRID, (panel.left, y), (panel.right, y))
        label = small.render(fmt(t), True, color)
        if right_axis:
            screen.blit(label, (panel.right + 6, y - label.get_height() // 2))
        else:
            screen.blit(label, (panel.left - 8 - label.get_width(), y - label.get_height() // 2))


def draw_series(screen, values, vmin, vmax, panel, color, width=1):
    n = len(values)
    if n == 0:
        return
    pts = []
    step = max(1, n // 1600)  # 点太多时抽稀，保持绘制速度
    for i in range(0, n, step):
        pts.append((int(x_at(i, n, panel)), int(y_at(values[i], vmin, vmax, panel))))
    if n > 1 and pts:
        pts.append((int(x_at(n - 1, n, panel)), int(y_at(values[-1], vmin, vmax, panel))))
    if len(pts) >= 2:
        pygame.draw.lines(screen, color, False, pts, width)
    else:
        pygame.draw.circle(screen, color, pts[0], 2)


def nice_range(values):
    lo, hi = min(values), max(values)
    if hi - lo < 1.0:
        lo, hi = lo - 1.0, hi + 1.0
    pad = (hi - lo) * 0.08
    return lo - pad, hi + pad


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    screen.fill(WHITE)

    rewards = read_train_rewards(TRAIN_LOG)
    evals = read_eval_rows(EVAL_LOG)
    n = len(rewards)

    title = get_font(24).render("AI 坦克大战 · DQN 训练曲线", True, TEXT)
    screen.blit(title, (28, 22))
    sub = get_font(15).render(
        f"训练局数(按日志行序): {n}    贪心评估次数: {len(evals)}", True, TEXT)
    screen.blit(sub, (28, 62))

    # ---- 上 panel：每局奖励 + 滑动均值 ----
    p1 = pygame.Rect(84, 110, W - 84 - 96, 270)
    if rewards:
        lo, hi = nice_range(rewards + moving_avg(rewards))
        ticks = [lo + (hi - lo) * k / 4 for k in range(5)]
        draw_panel_frame(screen, p1, ticks, lambda v: f"{v:.0f}")
        draw_series(screen, rewards, lo, hi, p1, C_RAW, 1)
        draw_series(screen, moving_avg(rewards, 20), lo, hi, p1, C_MA, 3)
        legend_raw = get_font(14).render("每局奖励", True, C_RAW)
        legend_ma = get_font(14).render("20 局滑动均值", True, C_MA)
        screen.blit(legend_raw, (p1.right - 200, p1.top + 8))
        screen.blit(legend_ma, (p1.right - 200, p1.top + 28))
        if rewards:
            last = get_font(14).render(f"最新滑动均值 {moving_avg(rewards, 20)[-1]:.1f}", True, TEXT)
            screen.blit(last, (p1.left, p1.top - 22))
    else:
        screen.blit(get_font(18).render("没有训练日志 models/train_log.csv", True, TEXT),
                    (p1.left + 20, p1.top + 100))

    # ---- 下 panel：贪心评估胜率 + 平均击杀 ----
    p2 = pygame.Rect(84, 450, W - 84 - 96, 150)
    pygame.draw.rect(screen, AXIS, p2, 1)
    if evals:
        small = get_font(13)
        for k in range(5):
            val = k / 4 * 100
            y = int(y_at(val, 0, 100, p2))
            pygame.draw.line(screen, GRID, (p2.left, y), (p2.right, y))
            lab = small.render(f"{val:.0f}%", True, C_WIN)
            screen.blit(lab, (p2.left - 8 - lab.get_width(), y - lab.get_height() // 2))
        draw_series(screen, [r["win"] * 100 for r in evals], 0, 100, p2, C_WIN, 3)

        kmax = max(2.0, math.ceil(max(r["kills"] for r in evals) * 1.15))
        for k in range(5):
            val = kmax * k / 4
            y = int(y_at(val, 0, kmax, p2))
            lab = small.render(f"{val:g}", True, C_KILL)
            screen.blit(lab, (p2.right + 6, y - lab.get_height() // 2))
        draw_series(screen, [r["kills"] for r in evals], 0, kmax, p2, C_KILL, 2)

        screen.blit(get_font(14).render("胜率(%)", True, C_WIN), (p2.right - 190, p2.top + 8))
        screen.blit(get_font(14).render("平均击杀", True, C_KILL), (p2.right - 110, p2.top + 8))
        screen.blit(get_font(14).render(f"x={len(evals)} 个评估点", True, TEXT),
                    (p2.left, p2.top - 22))
    else:
        screen.blit(get_font(18).render("暂无评估数据（训练时 --eval-every > 0 会生成 eval_log.csv）",
                                        True, TEXT), (p2.left + 10, p2.top + 60))

    pygame.image.save(screen, OUT_PNG)
    pygame.quit()
    print(f"曲线已保存: {OUT_PNG}")


if __name__ == "__main__":
    main()
