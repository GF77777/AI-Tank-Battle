"""人类玩家入口：开始界面 -> 游戏 -> 胜负结算。运行：python main.py"""

import os
import sys

# pythonw 无控制台启动时 stdout/stderr 为空，兜底避免 print 报错
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

os.environ.setdefault("SDL_IME_SHOW_UI", "1")   # 显示输入法候选窗（需在 pygame 初始化前）

import pygame

from game import ime
from game import settings as S
from game.core import Game, create_display, present

ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "tank.ico")


def set_console_icon():
    """把 Windows 控制台窗口（python 黑窗）图标换成坦克，无独立控制台时跳过。"""
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32.GetConsoleWindow.restype = wintypes.HWND
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.LoadImageW.argtypes = (wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                      ctypes.c_int, ctypes.c_int, wintypes.UINT)
        user32.SendMessageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT,
                                        wintypes.WPARAM, wintypes.LPARAM)
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return
        hicon = user32.LoadImageW(None, ICON_PATH, 1, 0, 0, 0x10)   # IMAGE_ICON | LR_LOADFROMFILE
        if hicon:
            user32.SendMessageW(hwnd, 0x0080, 0, hicon)             # WM_SETICON ICON_SMALL
            user32.SendMessageW(hwnd, 0x0080, 1, hicon)             # WM_SETICON ICON_BIG
    except Exception:
        pass


def set_taskbar_identity():
    """独立任务栏标识；否则从终端启动时任务栏沿用终端图标。"""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AITankBattle.Game")
    except Exception:
        pass


def main():
    set_taskbar_identity()          # 须在创建窗口前设置
    set_console_icon()
    pygame.init()
    pygame.display.set_caption("AI Tank Battle")
    screen, logical = create_display()
    ime.disable()                  # 战斗中禁用输入法，中文 IME 不吞按键
    clock = pygame.time.Clock()
    game = Game(log_playtest=True)
    game.start_agent_preload()       # 标题界面后台加载，避免首次点击阻塞

    pressed_dirs = []   # 按下的方向键栈，最后按下的优先生效（手感更好）
    running = True
    while running:
        fire_key = game.keybinds["fire"]
        skill_key = game.keybinds["skill"]
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN and event.key in game.dir_keys:
                d = game.dir_keys[event.key]
                if d in pressed_dirs:
                    pressed_dirs.remove(d)
                pressed_dirs.append(d)
            elif event.type == pygame.KEYUP and event.key in game.dir_keys:
                d = game.dir_keys[event.key]
                if d in pressed_dirs:
                    pressed_dirs.remove(d)
            if event.type == pygame.KEYDOWN:
                if event.key == fire_key:
                    game.player_fire()       # J：普攻
                elif event.key == skill_key:
                    game.player_skill()      # K：瞬发技能
            if not game.handle_event(event):
                running = False

        input_dir = pressed_dirs[-1] if pressed_dirs else None
        game.update(input_dir=input_dir)
        game.render(logical)
        present(screen, logical)
        pygame.display.flip()
        clock.tick(S.FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
