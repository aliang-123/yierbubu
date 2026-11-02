"""开机自启动（Windows）。

通过写入当前用户注册表 Run 项实现登录后自动启动：
  HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\YierBubu
非 Windows 平台安全降级：is_enabled() 恒返回 False，set_enabled() 静默无操作。
"""
import os
import sys

try:
    import winreg
    _HAS_REG = True
except Exception:  # pragma: no cover - 非 Windows 无 winreg
    winreg = None
    _HAS_REG = False

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "YierBubu"


def _launch_command() -> str:
    """构造自启动要执行的命令。

    - 打包后（PyInstaller frozen）：直接用可执行文件自身（已是窗口程序，无控制台）。
    - 源码运行：用当前解释器启动 main.py（若用 pythonw 启动则无控制台窗口）。
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{sys.executable}" "{script}"'


def is_enabled() -> bool:
    """当前是否已开启开机自启动。"""
    if not _HAS_REG:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_enabled(enabled: bool):
    """开启或关闭开机自启动。"""
    if not _HAS_REG:
        return
    try:
        with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(
                    key, APP_NAME, 0, winreg.REG_SZ, _launch_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
    except Exception:
        # 写入注册表失败（权限等）时静默忽略，不影响主程序运行。
        pass
