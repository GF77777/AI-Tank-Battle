"""DQN 贪心评估：加载模型，ε=0 跑 N 局，输出胜率/击杀/奖励等指标。"""

import argparse
import csv
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # 评估全程无窗口

import numpy as np

from ai.dqn import DQNAgent
from game import settings as S
from game.env import STATE_DIM, VersusEnv

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
DEFAULT_MODEL = os.path.join(MODELS_DIR, "dqn_tank.pth")


def evaluate(agent, episodes=20, seed=None, verbose=False):
    """贪心策略（ε=0）评估，返回 (汇总指标, 每局明细)。

    seed 固定时同模型多次评估结果完全一致；seed=None 时不改动全局随机状态。
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    env = VersusEnv()
    env.set_opponents(agent)      # 自博弈对战：对手与学习者同一模型，双方均 ε=0
    rows = []
    for ep in range(1, episodes + 1):
        state = env.reset()
        ep_reward = 0.0
        done = False
        info = {"kills": 0, "win": False, "steps": 0, "score": 0}
        while not done:
            action = agent.act(state, 0.0)
            state, reward, done, info = env.step(action, epsilon=0.0)
            ep_reward += reward
        rows.append({
            "episode": ep,
            "reward": ep_reward,
            "kills": info.get("kills", 0),
            "win": bool(info.get("win", False)),
            "steps": info.get("steps", 0),
            "score": info.get("score", 0),
        })
        if verbose:
            print(f"  eval ep{ep:>2}: reward={ep_reward:8.1f} kills={rows[-1]['kills']:2d} "
                  f"win={rows[-1]['win']} steps={rows[-1]['steps']}")

    if not rows:
        return {"win_rate": 0.0, "avg_kills": 0.0, "avg_reward": 0.0,
                "avg_steps": 0.0, "avg_score": 0.0}, rows

    return {
        "win_rate": float(np.mean([r["win"] for r in rows])),
        "avg_kills": float(np.mean([r["kills"] for r in rows])),
        "avg_reward": float(np.mean([r["reward"] for r in rows])),
        "avg_steps": float(np.mean([r["steps"] for r in rows])),
        "avg_score": float(np.mean([r["score"] for r in rows])),
    }, rows


def parse_args():
    p = argparse.ArgumentParser(description="AI 坦克大战 DQN 贪心评估")
    p.add_argument("--model", type=str, default=DEFAULT_MODEL, help="模型文件路径")
    p.add_argument("--episodes", type=int, default=20, help="评估局数")
    p.add_argument("--seed", type=int, default=123, help="随机种子（固定可复现）")
    p.add_argument("--out", type=str, default=os.path.join(MODELS_DIR, "eval_result.csv"),
                   help="每局明细输出路径")
    return p.parse_args()


def main():
    args = parse_args()
    if not os.path.exists(args.model):
        raise SystemExit(f"模型文件不存在: {args.model}，请先运行 train.py 训练")

    agent = DQNAgent(STATE_DIM, S.N_ACTIONS)
    agent.load(args.model)
    print(f"模型: {args.model}（设备 {agent.device}） | 评估 {args.episodes} 局 | seed={args.seed}")

    metrics, rows = evaluate(agent, args.episodes, seed=args.seed, verbose=True)

    print(f"\n评估结果: 胜率 {metrics['win_rate'] * 100:.1f}% | "
          f"平均击杀 {metrics['avg_kills']:.1f} | 平均奖励 {metrics['avg_reward']:.1f} | "
          f"平均步数 {metrics['avg_steps']:.0f} | 平均得分 {metrics['avg_score']:.0f}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["episode", "reward", "kills", "win", "steps", "score"])
        for r in rows:
            w.writerow([r["episode"], f"{r['reward']:.1f}", r["kills"],
                        int(r["win"]), r["steps"], r["score"]])
    print(f"明细已写入: {args.out}")


if __name__ == "__main__":
    main()
