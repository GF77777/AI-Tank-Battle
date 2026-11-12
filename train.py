"""DQN 训练入口：headless 高速训练，保存模型与训练日志。"""

import argparse
import csv
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # 无窗口高速训练（须在 pygame 导入前设置）

import numpy as np
import torch

from ai.dqn import DQNAgent
from evaluate import evaluate
from game import settings as S
from game.env import STATE_DIM, VersusEnv

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


def parse_args():
    p = argparse.ArgumentParser(description="AI 坦克大战 DQN 训练")
    p.add_argument("--episodes", type=int, default=5000, help="训练局数（自博弈收敛慢，需要更多局数）")
    p.add_argument("--batch-size", type=int, default=128, help="加大 batch 平滑梯度（自博弈非平稳环境）")
    p.add_argument("--lr", type=float, default=5e-4, help="略降低学习率提升自博弈稳定性")
    p.add_argument("--gamma", type=float, default=0.99)
    p.add_argument("--buffer", type=int, default=200_000, help="经验回放容量（更大=样本更多样）")
    p.add_argument("--eps-start", type=float, default=1.0)
    p.add_argument("--eps-end", type=float, default=0.05, help="自博弈仍需少量探索，但末段要能收敛出可用策略")
    p.add_argument("--eps-decay", type=int, default=250_000, help="ε 线性衰减的决策步数（5000 局约 70 万步，末段 ε=0.05）")
    p.add_argument("--sync", type=int, default=500, help="target net 同步间隔（自博弈对手=自己，需更快跟上）")
    p.add_argument("--save-every", type=int, default=200, help="每多少局保存一次模型")
    p.add_argument("--log-every", type=int, default=50, help="每多少局打印一次统计")
    p.add_argument("--seed", type=int, default=0, help="随机种子（0 表示固定 0）")
    p.add_argument("--learn-every", type=int, default=4, help="每 k 个决策步做一次梯度更新（标准 DQN=4，省约 75 成计算）")
    p.add_argument("--eval-every", type=int, default=200, help="每 N 局做一次贪心评估，0 关闭")
    p.add_argument("--eval-episodes", type=int, default=20, help="每次评估跑几局（20 局方差更小）")
    p.add_argument("--out", type=str, default=os.path.join(MODELS_DIR, "dqn_tank.pth"))
    p.add_argument("--resume", type=str, default=None, help="加载已有模型继续训练")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(MODELS_DIR, exist_ok=True)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    agent = DQNAgent(STATE_DIM, S.N_ACTIONS, lr=args.lr, gamma=args.gamma,
                     buffer_capacity=args.buffer, batch_size=args.batch_size,
                     sync_interval=args.sync)
    env = VersusEnv()
    env.set_opponents(agent)      # 自博弈：3 个对手与学习者共用同一份参数
    if args.resume:
        agent.load(args.resume)
        print(f"已加载模型继续训练: {args.resume}")
    print(f"设备: {agent.device} | 状态维度: {STATE_DIM} | 动作数: {S.N_ACTIONS}")

    log_path = os.path.join(MODELS_DIR, "train_log.csv")
    log_new = not os.path.exists(log_path)
    log_file = open(log_path, "a", newline="", encoding="utf-8")
    writer = csv.writer(log_file)
    if log_new:
        writer.writerow(["episode", "reward", "kills", "win", "epsilon", "steps"])

    eval_path = os.path.join(MODELS_DIR, "eval_log.csv")
    eval_new = not os.path.exists(eval_path)
    eval_file = open(eval_path, "a", newline="", encoding="utf-8")
    eval_writer = csv.writer(eval_file)
    if eval_new:
        eval_writer.writerow(["train_episode", "eval_win_rate", "eval_avg_kills",
                              "eval_avg_reward", "eval_avg_steps"])

    global_step = 0
    rewards, kills_hist, wins = [], [], []
    eps = args.eps_start
    for ep in range(1, args.episodes + 1):
        state = env.reset()
        ep_reward = 0.0
        done = False
        info = {"kills": 0, "win": False, "steps": 0}
        while not done:
            eps = max(args.eps_end,
                      args.eps_start - (args.eps_start - args.eps_end) * global_step / args.eps_decay)
            action = agent.act(state, eps)
            next_state, reward, done, info = env.step(action, epsilon=eps)
            agent.store(state, action, reward, next_state, done)
            if global_step % args.learn_every == 0:
                agent.learn()
            global_step += 1
            ep_reward += reward
            state = next_state

        rewards.append(ep_reward)
        kills_hist.append(info["kills"])
        wins.append(1 if info["win"] else 0)
        writer.writerow([ep, f"{ep_reward:.1f}", info["kills"],
                         int(info["win"]), f"{eps:.4f}", info["steps"]])
        log_file.flush()

        if ep % args.log_every == 0:
            print(f"Episode {ep}/{args.episodes} | 平均奖励 {np.mean(rewards):8.1f} | "
                  f"平均击杀 {np.mean(kills_hist):4.1f} | "
                  f"胜率 {np.mean(wins) * 100:5.1f}% | ε {eps:.3f}")
            rewards, kills_hist, wins = [], [], []
        if ep % args.save_every == 0:
            agent.save(args.out)
            print(f"模型已保存: {args.out}")
        if args.eval_every > 0 and ep % args.eval_every == 0:
            metrics, _ = evaluate(agent, args.eval_episodes)
            print(f"[EVAL] ep={ep} 胜率={metrics['win_rate'] * 100:5.1f}% | "
                  f"平均击杀={metrics['avg_kills']:.1f} | 平均奖励={metrics['avg_reward']:.1f}")
            eval_writer.writerow([ep, f"{metrics['win_rate']:.3f}", f"{metrics['avg_kills']:.2f}",
                                  f"{metrics['avg_reward']:.1f}", f"{metrics['avg_steps']:.0f}"])
            eval_file.flush()

    agent.save(args.out)
    log_file.close()
    eval_file.close()
    print(f"训练完成，最终模型: {args.out} | 日志: {log_path}")


if __name__ == "__main__":
    main()
