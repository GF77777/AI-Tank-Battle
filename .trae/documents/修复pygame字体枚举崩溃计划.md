# 修复：pygame.font.match_font 枚举系统字体时崩溃

## Summary

`python main.py` 启动时在 `get_font(40)` → `pygame.font.match_font(name)` 处崩溃：

```
TypeError: expected str, bytes or os.PathLike object, not int
  File ".../site-packages/pygame/sysfont.py", line 82, in initsysfonts_win32
    if splitext(font)[1].lower() not in OpenType_extensions:
```

**根因**：`pygame.font.match_font` / `SysFont` 会调用 `initsysfonts_win32()` 枚举 Windows 字体注册表；本机注册表中有一个字体项的值是整数而非字符串路径，导致 `os.fspath(int)` 抛 TypeError。这是 pygame + Windows 的环境 bug，不是项目代码 bug，但项目所有文字都走 `get_font()`，因此游戏完全无法启动。

## Current State Analysis

- 所有字体都通过 [core.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/core.py#L92-L100) 的 `get_font(size)` 获取；`get_font` 内部唯一调用 `pygame.font.match_font(name)` 来查字体路径。
- [core.py:80-89](file:///c:/Users/CGF/Desktop/AI坦克大战/game/core.py#L80-L89) 的 `_detect_cjk_font()` 也调用 `match_font`，同样会崩。
- [plot_curve.py](file:///c:/Users/CGF/Desktop/AI坦克大战/plot_curve.py#L11) 从 `game.core` 导入 `get_font`，修复 core.py 即同时覆盖曲线图。
- 本机 `C:\Windows\Fonts\` 下可直接用路径访问的中文字体已确认存在：`msyh.ttc`、`simhei.ttf`、`simsun.ttc`、`simkai.ttf`。
- `pygame.font.Font(绝对路径, size)` 是直接按文件加载，**不触发注册表枚举**，可绕开崩溃。

## Proposed Changes

### [core.py](file:///c:/Users/CGF/Desktop/AI坦克大战/game/core.py)

**1. 新增一个候选字体路径列表**（在 `_font_cache` 附近）：

```python
# 直接用绝对路径加载系统字体，绕过 pygame.font.match_font 的注册表枚举（
# 本机字体注册表有非法整数值，match_font 会抛 TypeError）。
import os
_FONT_CANDIDATES = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyh.ttc"),    # 微软雅黑
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simhei.ttf"),  # 黑体
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simsun.ttc"),  # 宋体
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simkai.ttf"),  # 楷体
]
_FONT_PATH = None  # 懒加载：第一次 get_font 时确定可用字体路径
```

（`os` 已在文件顶部 import，无需重复。）

**2. 重写 `get_font(size)`**：用 `os.path.exists` 找路径，直接 `Font(path, size)`；找不到回退 `Font(None, size)`；整体 try/except 兜底。

```python
def get_font(size):
    if size not in _font_cache:
        global _FONT_PATH
        if _FONT_PATH is None:
            for p in _FONT_CANDIDATES:
                try:
                    if os.path.exists(p):
                        _FONT_PATH = p
                        break
                except OSError:
                    continue
        try:
            _font_cache[size] = (pygame.font.Font(_FONT_PATH, size)
                                  if _FONT_PATH else pygame.font.Font(None, size))
        except Exception:
            _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]
```

**3. 重写 `_detect_cjk_font()`**：判断候选字体文件是否存在（而不是调 `match_font`）。

```python
def _detect_cjk_font():
    global _cjk_ok
    if _cjk_ok is None:
        _cjk_ok = any(os.path.exists(p) for p in _FONT_CANDIDATES)
    return _cjk_ok
```

**4. 删除不再使用的 `match_font` 调用**（上面两处替换后即无残留）。

## Assumptions & Decisions

| 决策 | 理由 |
|---|---|
| 用 `os.path.exists` + 绝对路径而非 `match_font` | 直接文件加载不触发注册表枚举，从根本上绕开崩溃；Windows 字体路径固定 |
| 优先 msyh.ttc（微软雅黑） | 渲染效果最接近原 `microsoftyahei` 意图 |
| 用 `os.environ.get("WINDIR", r"C:\Windows")` 而非硬编码 | 兼容 Windows 安装在非 C 盘的情况 |
| 保留 `Font(None, size)` 兜底 | 极端情况下（无中文字体）游戏仍能启动，只是中文显示为方框 |
| try/except 兜底 | 防止任何单字体加载异常再次导致崩溃 |
| 不改 audio/sprites/其他模块 | 只有 core.py 涉及字体，其他模块不碰 |

## Verification

1. `python -c "import os; from game.core import get_font; print(get_font(20).render('测试中文', True, (255,255,255)).get_size())"` — 不再抛 TypeError，能正常返回尺寸。
2. `python main.py` — 能进入标题界面，中文标题、菜单文字正常显示（不弹框）。需人工确认或截图。
3. `python -c "from game.core import _detect_cjk_font; print(_detect_cjk_font())"` — 输出 `True`。
