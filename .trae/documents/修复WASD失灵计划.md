# 修复 WASD 失灵 计划

## 1. 概要

现象：游戏里只有上下左右箭头能移动，WASD 完全无反应。
诊断：[main.py](file:///c:/Users/CJP/Desktop/AI坦克大战/main.py#L10-L15) 的 `_KEY_TO_DIR` 映射本身正确（W/A/S/D 都在），代码逻辑无 bug。根本原因是 **Windows 中文输入法（IME）在游戏窗口处于激活状态，把字母键消息吞掉去组字了**，pygame 收不到 W/A/S/D 的按键事件。箭头键不被 IME 处理，所以正常。这是中文 Windows + pygame 的经典问题。

修复思路：启动游戏时为窗口禁用 IME（进程级，不影响系统输入法设置）；顺手让标题/暂停菜单也支持 W/S 选择，保持键位体验一致。

## 2. 现状分析

- `main.py`：`_KEY_TO_DIR` 已含 `K_w/K_a/K_s/K_d`，事件循环按 KEYDOWN/KEYUP 维护 `pressed_dirs` 栈——事件根本到不了，所以栈永远为空。
- [core.py](file:///c:/Users/CJP/Desktop/AI坦克大战/game/core.py) `handle_event()`：菜单导航只认 `K_UP/K_DOWN`，不认 W/S（本次顺带补上）。
- 空格射击用 `pygame.key.get_pressed()` 轮询——IME 激活时空格也可能被当"确认候选"吞掉，禁用 IME 后一并解决。
- 平台：Windows（`sys.platform == "win32"`），pygame 2.6.1 / SDL2，`pygame.display.get_wm_info()["window"]` 可拿到 HWND。

## 3. 提议改动

### 3.1 `main.py`：禁用 IME（核心修复）

新增 `_disable_ime()` 并在 `create_display()` 之后调用一次：

```python
def _disable_ime():
    """Windows 下为游戏窗口禁用输入法，防止中文 IME 吞掉 WASD/空格键。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = pygame.display.get_wm_info()["window"]
        ctypes.windll.imm32.ImmAssociateContext(hwnd, None)
    except Exception:
        pass          # 拿不到句柄/无 imm32 时静默跳过，不影响游戏
```

说明：
- `ImmAssociateContext(hwnd, NULL)` 是 Win32 标准做法，只影响本进程窗口，退出即恢复，不改系统输入法。
- 用 `try/except` 兜底，保证非 Windows 或异常环境下游戏照常启动。
- 恢复系统 IME 无需处理（关联随窗口销毁自动解除）。

### 3.2 `game/core.py`：菜单键位补齐（顺手一致性）

`handle_event()` 的方向选择分支由
`if key in (pygame.K_UP, pygame.K_DOWN)` 扩展为
`if key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s)`，
`step = -1 if key in (pygame.K_UP, pygame.K_w) else 1`。
效果：标题界面和暂停菜单同样支持 W/S 上下选择。

### 3.3 文档同步（各 1 行）

- [README.md](file:///c:/Users/CJP/Desktop/AI坦克大战/README.md) 操作表：注明"启动时已自动禁用窗口输入法，WASD 与方向键等效"。
- [GDD.md](file:///c:/Users/CJP/Desktop/AI坦克大战/docs/GDD.md) 变更记录加一行 v1.2 补充说明。

## 4. 关键假设与决策

1. 假设 IME 吞键是唯一原因（依据：映射代码正确 + 箭头正常 + 中文 Windows 环境）；若修复后仍无效，再排查键盘硬件/驱动层。
2. 选择"禁用 IME"而非"改用 get_pressed 轮询字母键"：IME 在消息层拦截，轮询同样收不到，治本是断开窗口与 IME 的关联。
3. 不给游戏加"按 Shift 切换输入法"类逻辑：保持进程级静默禁用，用户零感知。
4. 菜单补 W/S 属于同一键位体验问题，一并修；不新增其他键位绑定。

## 5. 验证方案

| 验证项 | 方法 | 通过标准 |
|---|---|---|
| 逻辑回归 | headless 脚本向 Game 注入合成 KEYDOWN(K_w) 事件 + `update()` | 坦克按 W 上移；菜单 W/S 可导航 |
| 启动回归 | `python main.py` 真机启动 | 窗口正常打开、无异常输出 |
| 真机验收（用户） | 中文输入法激活状态下运行游戏 | WASD 可移动、空格可射击、菜单 W/S 可选 |
| 环境兜底 | headless 下 `create_display()`（dummy 驱动） | `_disable_ime()` 不抛异常（get_wm_info 在 dummy 下可能无 window 键，走 except 分支） |
| 回归 | `evaluate.py --episodes 3 --seed 1` | 结果与基线一致（0% 胜率不变） |
