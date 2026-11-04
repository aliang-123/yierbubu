"""音频管理器：为「一二布布桌面宠物」增加音效。

资源布局（按角色分目录，方便随时往里加音频）：
  Assets/Audio/
    <角色>/                 # 角色目录：classic / yier / bubu / duo
      <任意名>.wav/.mp3/... # 该角色的音效列表（多个则随机播放，避免连续重复）
      mood_<心情>.<ext>     # 该角色专属“状态/心情”音效（如 mood_angry.wav）
    mood_<心情>.wav         # 全局心情音效兜底（合成），仅当对应角色目录没有时回落使用

功能（对应需求）：
  - 支持开启 / 关闭（set_enabled / is_enabled），持久化到 UserSettings（audio.enabled）。
  - 按展示角色播放对应音频（play_character）：每次切换形象（含启动、菜单换装）从该角色目录
    随机取一个文件播放；目录为空时回落到旧式单文件 Assets/Audio/<角色>.wav。
  - 按心情 / 状态播放音频（play_mood，可选增强）：优先播放“当前角色目录”下的
    mood_<心情>.*，找不到则回落到全局 Assets/Audio/mood_<心情>.wav。
  - 安全降级：无音频设备 / offscreen / QtMultimedia 缺失时全部静默失败，绝不抛异常或崩溃。

实现：基于 PyQt6.QtMultimedia.QSoundEffect（低延迟短音效，支持音量与静音）；每个音频文件
懒加载并缓存一个 QSoundEffect 实例，重复播放时 restart。
"""
import os
import random
import sys

# QtMultimedia 在某些精简 / 无音频后端的环境下可能不可用；做防御性导入，
# 缺失时 AudioManager 退化为“静默无操作”，不影响主程序。
try:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtMultimedia import QSoundEffect
    _HAS_QT_MULTIMEDIA = True
except Exception:  # pragma: no cover
    QUrl = None
    QSoundEffect = None
    _HAS_QT_MULTIMEDIA = False

from .config import UserSettings
from .styles import PetStyle

# 支持的音频扩展名（WAV 最稳；MP3/OGG 等依赖平台解码器，Windows 下通常可用）。
AUDIO_EXTS = (".wav", ".mp3", ".ogg", ".oga", ".m4a", ".flac", ".aac")


def audio_dir() -> str:
    """解析音频资源目录，与 sprites._asset_dir 保持一致的分发 / 开发双路径策略。"""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
        cand = os.path.join(base, "Assets", "Audio")
        if os.path.isdir(cand):
            return os.path.abspath(cand)
        cand2 = os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                             "Assets", "Audio")
        if os.path.isdir(cand2):
            return os.path.abspath(cand2)
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "Assets", "Audio"),
        os.path.join(os.getcwd(), "Assets", "Audio"),
    ]
    for c in candidates:
        if os.path.isdir(os.path.abspath(c)):
            return os.path.abspath(c)
    return os.path.abspath(candidates[0])


def _character_dir(style: PetStyle) -> str:
    return os.path.join(audio_dir(), style.raw())


def _list_clips(directory: str, prefix: str = "", exclude_prefix: str = "") -> list:
    """列出 directory 下满足 prefix 前缀（且不以 exclude_prefix 开头）与音频扩展名的文件。

    prefix / exclude_prefix 大小写不敏感；排序返回，保证可复现。
    """
    if not os.path.isdir(directory):
        return []
    out = []
    for name in os.listdir(directory):
        low = name.lower()
        if not low.endswith(AUDIO_EXTS):
            continue
        if prefix and not low.startswith(prefix):
            continue
        if exclude_prefix and low.startswith(exclude_prefix):
            continue
        out.append(os.path.join(directory, name))
    return sorted(out)


def _list_character_clips(style: PetStyle) -> list:
    """角色音效列表：该角色目录下所有音频，排除 mood_ 前缀的状态音效。"""
    return _list_clips(_character_dir(style), prefix="", exclude_prefix="mood_")


def _list_mood_clips(style: PetStyle, mood) -> list:
    """某角色的状态/心情音效列表：该角色目录下 mood_<心情> 前缀的音频。"""
    name = getattr(mood, "name", None)
    if not name:
        return []
    return _list_clips(_character_dir(style), prefix=f"mood_{name.lower()}")


class AudioManager:
    def __init__(self, volume: float = 0.7):
        # 默认开启音效；仅当显式存为 False / "0" / 0 时关闭
        self._enabled = UserSettings.get("audio.enabled", True) not in (False, "0", 0)
        self._volume = volume
        self._effects: dict = {}  # 绝对路径 -> QSoundEffect
        self._current_style: PetStyle = None  # 当前展示角色（play_mood 用）
        self._last_picked: dict = {}  # key -> 上次播放路径，避免连续重复

    # ---------- 开关 ----------
    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)
        UserSettings.set("audio.enabled", self._enabled)

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, float(volume)))
        for fx in self._effects.values():
            try:
                fx.setVolume(self._volume)
            except Exception:
                pass

    # ---------- 内部 ----------
    def _effect_for(self, path: str):
        """懒加载并缓存一个 QSoundEffect；文件不存在或后端不可用则返回 None。"""
        if not _HAS_QT_MULTIMEDIA:
            return None
        abs_path = os.path.abspath(path)
        fx = self._effects.get(abs_path)
        if fx is not None:
            return fx
        if not os.path.exists(abs_path):
            return None
        try:
            fx = QSoundEffect()
            fx.setSource(QUrl.fromLocalFile(abs_path))
            fx.setVolume(self._volume)
            self._effects[abs_path] = fx
            return fx
        except Exception:
            return None

    def _play_path(self, path: str):
        if not self._enabled or not path:
            return
        try:
            fx = self._effect_for(path)
            if fx is None:
                return
            if fx.isPlaying():
                fx.stop()
            fx.play()
        except Exception:
            # 无音频设备 / 后端错误等一律吞掉，避免影响主循环
            pass

    @staticmethod
    def _pick(candidates: list, key: str, last_picked: dict):
        """从候选中随机取一个，尽量不与上一个相同（列表>1 时）。"""
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        prev = last_picked.get(key)
        choices = [c for c in candidates if c != prev] or candidates
        pick = random.choice(choices)
        last_picked[key] = pick
        return pick

    # ---------- 对外播放接口 ----------
    def play_character(self, style: PetStyle):
        """按展示角色播放对应音频（满足“根据角色播放”，含启动与换装）。

        优先播放该角色目录下的音频列表（随机不重复）；目录为空时回落到旧式单文件。
        """
        if not self._enabled:
            return
        self._current_style = style
        clips = _list_character_clips(style)
        if not clips:
            # 兼容旧布局：Assets/Audio/<角色>.wav
            single = os.path.join(audio_dir(), f"{style.raw()}.wav")
            if os.path.exists(single):
                self._play_path(single)
            return
        pick = self._pick(clips, style.raw(), self._last_picked)
        if pick:
            self._play_path(pick)

    def play_mood(self, mood):
        """按心情 / 状态播放对应音频（可选增强）。

        优先播放“当前角色目录”下的 mood_<心情>.*；若该角色未提供，则回落到全局
        Assets/Audio/mood_<心情>.wav（合成兜底），保证状态音效始终可用。
        """
        if not self._enabled:
            return
        clips = []
        if self._current_style is not None:
            clips = _list_mood_clips(self._current_style, mood)
        if not clips:
            name = getattr(mood, "name", None)
            if name:
                g = os.path.join(audio_dir(), f"mood_{name.lower()}.wav")
                if os.path.exists(g):
                    self._play_path(g)
            return
        key = f"{self._current_style.raw()}:mood:{getattr(mood, 'name', '').lower()}"
        pick = self._pick(clips, key, self._last_picked)
        if pick:
            self._play_path(pick)
