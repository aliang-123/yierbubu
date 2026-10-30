"""活动监视：输入空闲时长 + 前台进程（用于摸鱼检测）。

Windows 下通过 user32 的 GetLastInputInfo / GetForegroundWindow 获取；
其它平台做安全降级（空闲返回极大值、前台返回 None）。
"""
import platform
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None


class AppCategory(Enum):
    Ide = "ide"
    Terminal = "terminal"
    Video = "video"
    Music = "music"
    Social = "social"
    Game = "game"


_CATEGORY_EMOTION = {
    AppCategory.Ide: ["work"],
    AppCategory.Terminal: ["work"],
    AppCategory.Video: ["lazy", "happy"],
    AppCategory.Music: ["lazy", "happy"],
    AppCategory.Social: ["love", "happy"],
    AppCategory.Game: ["happy"],
}


def category_emotion_tags(cat: Optional[AppCategory]) -> list:
    if cat is None:
        return []
    return _CATEGORY_EMOTION.get(cat, [])


# 视为摸鱼/娱乐的进程名（不含 .exe，大小写不敏感）
SLACK_PROCESS_NAMES = {
    "bilibili", "哔哩哔哩", "qqplayer", "qqlive", "iqiyi", "youkudesktop",
    "youku", "potplayermini64", "potplayer", "vlc", "cloudmusic",
    "qqmusic", "thunderplayer", "mpv", "wmp", "wmplayer",
}

APP_CATEGORIES: Dict[str, AppCategory] = {
    # IDE
    "devenv": AppCategory.Ide, "code": AppCategory.Ide, "idea64": AppCategory.Ide,
    "idea": AppCategory.Ide, "pycharm64": AppCategory.Ide, "pycharm": AppCategory.Ide,
    "webstorm64": AppCategory.Ide, "rider64": AppCategory.Ide, "goland64": AppCategory.Ide,
    "clion64": AppCategory.Ide, "datagrip64": AppCategory.Ide, "cursor": AppCategory.Ide,
    # Terminal
    "windowsterminal": AppCategory.Terminal, "wt": AppCategory.Terminal,
    "powershell": AppCategory.Terminal, "cmd": AppCategory.Terminal,
    "bash": AppCategory.Terminal, "conhost": AppCategory.Terminal,
    # Video
    "bilibili": AppCategory.Video, "qqplayer": AppCategory.Video,
    "qqlive": AppCategory.Video, "iqiyi": AppCategory.Video,
    "youkudesktop": AppCategory.Video, "potplayermini64": AppCategory.Video,
    "vlc": AppCategory.Video,
    # Music
    "cloudmusic": AppCategory.Music, "qqmusic": AppCategory.Music,
    "spotify": AppCategory.Music,
    # Social
    "wechat": AppCategory.Social, "qq": AppCategory.Social, "tim": AppCategory.Social,
    # Game
    "steam": AppCategory.Game,
}


@dataclass
class _WinApi:
    available: bool = False


_api = _WinApi()


def _init_win_api():
    if platform.system() != "Windows":
        _api.available = False
        return
    try:
        import ctypes
        from ctypes import wintypes
        global _user32, _GetLastInputInfo, _GetForegroundWindow, _GetWindowThreadProcessId
        _user32 = ctypes.windll.user32

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT),
                        ("dwTime", wintypes.DWORD)]

        _LASTINPUTINFO = LASTINPUTINFO
        _user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
        _user32.GetLastInputInfo.restype = wintypes.BOOL
        _user32.GetForegroundWindow.restype = wintypes.HWND
        _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                                     ctypes.POINTER(wintypes.DWORD)]
        _GetLastInputInfo = _user32.GetLastInputInfo
        _GetForegroundWindow = _user32.GetForegroundWindow
        _GetWindowThreadProcessId = _user32.GetWindowThreadProcessId
        _LASTINPUTINFO_CLS = LASTINPUTINFO
        _api.available = True
    except Exception:
        _api.available = False


_init_win_api()


def idle_seconds() -> float:
    """距上次用户输入的秒数。无法获取时返回极大值。"""
    if not _api.available:
        return float("inf")
    try:
        import ctypes
        info = _LASTINPUTINFO_CLS()
        info.cbSize = ctypes.sizeof(info)
        if _GetLastInputInfo(ctypes.byref(info)):
            idle_ms = _user32.GetTickCount() - info.dwTime
            return max(0.0, idle_ms / 1000.0)
    except Exception:
        pass
    return float("inf")


def _foreground_process_name() -> Optional[str]:
    if not _api.available or psutil is None:
        return None
    try:
        hwnd = _GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes_ctypes_dword()
        _GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return None
        proc = psutil.Process(pid.value)
        return proc.name()
    except Exception:
        return None


def wintypes_ctypes_dword():
    import ctypes
    return ctypes.wintypes.DWORD(0)


class ActivityMonitor:
    def __init__(self):
        self._front_process_name: Optional[str] = None
        self._front_since = time.time()

    @property
    def front_process_name(self) -> Optional[str]:
        name = _foreground_process_name()
        if name != self._front_process_name:
            self._front_process_name = name
            self._front_since = time.time()
        return self._front_process_name

    @property
    def front_category(self) -> Optional[AppCategory]:
        name = self._front_process_name
        if name is None:
            return None
        # 进程名可能带 .exe，规范化
        key = name.lower().replace(".exe", "")
        return APP_CATEGORIES.get(key)

    @property
    def slacking_seconds(self) -> float:
        name = self._front_process_name
        if name is None:
            return 0.0
        key = name.lower().replace(".exe", "")
        if key not in SLACK_PROCESS_NAMES:
            return 0.0
        return time.time() - self._front_since
