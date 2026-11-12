"""加载已训练的 DQN 模型，观看 4 个 AI 自博弈互殴（玩家侧也由同一模型驱动，ε=0）。"""

import argparse
import os

import pygame

from ai.dqn import DQNAgent
from game import settings as S
from game.core import Game, STATE_PLAYING, create_display, present
from game.env import STATE_DIM, build_foe_state, decode_action

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "dqn_tank.pth")


def _start_battle(game, agent):
    """接线对战驱动并开一局：3 个对手走 game.dqn_agent，玩家侧由主循环驱动。"""
    game.dqn_agent = agent
    game._build_foe_state = build_foe_state
    game._decode_vs_action = decode_action
    game._reset_battle()
    game.state = STATE_PLAYING


def main():
    parser = argparse.ArgumentParser(description="观看 4 个 AI 自博弈对战")
    parser.add_argument("--model", type=str, default=MODEL_PATH, help="模型文件路径")
    args = parser.parse_args()
    if not os.path.exists(args.model):
        raise SystemExit(f"模型文件不存在: {args.model}，请先运行 train.py 训练")

    pygame.init()
    screen, logical = create_display()
    pygame.display.set_caption("AI 坦克大战 - AI 自博弈观战")
    clock = pygame.time.Clock()

    game = Game()
    agent = DQNAgent(STATE_DIM, S.N_ACTIONS)
    agent.load(args.model)
    _start_battle(game, agent)
    print(f"已加载模型: {args.model}（设备 {agent.device}），4 AI 自博弈，ε=0 观战模式")

    player_action = (None, False)   # 玩家侧 AI 的当前决策 (方向, 开火)
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) \
                        and game.state != STATE_PLAYING:
                    _start_battle(game, agent)

        if game.state == STATE_PLAYING:
            # 玩家侧与 3 个对手同一节奏：每 FRAME_SKIP 帧决策一次，决策间重复执行
            if game.frame % S.FRAME_SKIP == 0:
                obs = build_foe_state(game, game.player, game.versus_foes)
                player_action = decode_action(agent.act(obs, 0.0))
            game.update(input_dir=player_action[0], input_fire=player_action[1])
        else:
            game.update()  # 推动结算界面闪烁动画

        game.render(logical)
        present(screen, logical)
        pygame.display.flip()
        clock.tick(S.FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
