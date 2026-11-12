"""输入法开关：战斗/菜单关闭文本输入（中文 IME 不吞按键），名片页开启以输入中文。

Windows 下 SDL 关闭文本输入时会解绑 IME 上下文，这里自己保存/恢复
ImmAssociateContext，保证名片页能重新挂上当前的中文输入法。
"""

import sys

import pygame

_imm = None         # imm32（非 Windows / 加载失败为 False）
_hwnd = None        # 游戏窗口句柄
_ctx = None         # 保存的 IME 上下文
_rect = None        # 输入框矩形（逻辑坐标），用于摆放候选窗
_active = False     # 当前是否处于文本输入（编辑名字）状态


def _setup():
    """懒加载 imm32 与窗口句柄；不可用时返回 False。"""
    global _imm, _hwnd
    if _imm is None:
        if sys.platform != "win32":
            _imm = False
        else:
            try:
                import ctypes
                _imm = ctypes.windll.imm32
            except Exception:
                _imm = False
    if _imm and _hwnd is None:
        try:
            _hwnd = pygame.display.get_wm_info()["window"]
        except Exception:
            _hwnd = 0
    return bool(_imm and _hwnd)


def disable():
    """关闭文本输入并解绑 IME（保存上下文，供 enable 恢复）。"""
    global _ctx, _active
    try:
        pygame.key.stop_text_input()
    except Exception:
        pass
    if _setup():
        try:
            got = _imm.ImmAssociateContext(_hwnd, 0)
            if got:
                _ctx = got
        except Exception:
            pass
    _active = False


def enable(rect=None):
    """开启文本输入并挂回 IME；rect 为逻辑坐标输入框，用于定位候选窗。"""
    global _ctx, _rect, _active
    try:
        pygame.key.start_text_input()
    except Exception:
        pass
    if _setup():
        try:
            if not _ctx:
                _ctx = _imm.ImmCreateContext()
            _imm.ImmAssociateContext(_hwnd, _ctx)   # 放在 SDL 之后，避免被 SDL 覆盖
        except Exception:
            pass
    if rect is not None:
        _rect = pygame.Rect(rect)
        try:
            from . import settings as S
            # SDL 用这个矩形的右下角当"光标"定位候选窗：宽度传 0，让候选窗落在输入框左端下方，
            # 否则会跑到整条输入框的最右端（看起来飘到面板外）。
            pygame.key.set_text_input_rect(
                pygame.Rect(_rect.x, _rect.y, 0, _rect.h).scale_by(S.SCALE))
        except Exception:
            pass
        reposition()
    _active = True


def reposition():
    """把输入法候选窗放到输入框正下方、组合串对齐输入框（Windows 屏幕坐标）。

    SDL 只会给它自己的 IME 上下文定位，我们接管上下文后必须自己摆位置，
    否则候选窗会停在屏幕左上角。每开始/更新组合时调用一次。
    """
    if not (_setup() and _ctx and _rect is not None):
        return
    try:
        import ctypes
        from ctypes import wintypes as wt
        user32 = ctypes.windll.user32

        class CANDIDATEFORM(ctypes.Structure):
            _fields_ = [("dwIndex", wt.DWORD), ("dwStyle", wt.DWORD),
                        ("ptCurrentPos", wt.POINT), ("rcArea", wt.RECT)]

        class COMPOSITIONFORM(ctypes.Structure):
            _fields_ = [("dwStyle", wt.DWORD), ("ptCurrentPos", wt.POINT),
                        ("rcArea", wt.RECT)]

        from . import settings as S
        # 候选窗：输入框左下角下方（屏幕坐标）
        pt = wt.POINT(int(_rect.x * S.SCALE), int(_rect.bottom * S.SCALE))
        user32.ClientToScreen(_hwnd, ctypes.byref(pt))
        cf = CANDIDATEFORM(0, 0x0040, wt.POINT(pt.x, pt.y), wt.RECT(0, 0, 0, 0))
        _imm.ImmSetCandidateWindow(_ctx, ctypes.byref(cf))
        # 组合串：输入框左上角
        cpt = wt.POINT(int(_rect.x * S.SCALE), int(_rect.y * S.SCALE))
        user32.ClientToScreen(_hwnd, ctypes.byref(cpt))
        comp = COMPOSITIONFORM(0x0020, wt.POINT(cpt.x, cpt.y), wt.RECT(0, 0, 0, 0))
        _imm.ImmSetCompositionWindow(_ctx, ctypes.byref(comp))
    except Exception:
        pass


def restore():
    """退出编辑时回到禁用状态。"""
    if _active:
        disable()
