"""音频管理器：为「一二布布桌面宠物」增加音效。

功能（对应需求）：
  - 支持开启 / 关闭（set_enabled / is_enabled），持久化到 UserSettings（audio.enabled）。
  - 按展示角色播放对应音频（play_character）：每次切换形象（含启动、菜单换装）即播放。
  - 按心情 / 状态播放音频（play_mood，可选增强）：例如生气 → 生气音效。
  - 资源优先使用 Assets/Audio/<name>.wav；若用户日后放入真实角色语音同名覆盖即可替换，
    无需改动任何代码。
  - 安全降级：无音频设备 / offscreen / QtMultimedia 缺失时全部静默失败，绝不抛异常或崩溃。

实现：基于 PyQt6.QtMultimedia.QSoundEffect（低延迟短音效，支持音量与静音），
每个音频文件懒加载并缓存一个 QSoundEffect 实例，重复播放时 restart。
"""
import os
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


class AudioManager:
    def __init__(self, volume: float = 0.7):
        # 默认开启音效；仅当显式存为 False / "0" / 0 时关闭
        self._enabled = UserSettings.get("audio.enabled", True) not in (False, "0", 0)
        self._volume = volume
        self._effects: dict = {}  # 绝对路径 -> QSoundEffect

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

    def _play_file(self, path: str):
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

    # ---------- 对外播放接口 ----------
    def play_character(self, style: PetStyle):
        """按展示角色播放对应音频（满足“根据角色播放”，含启动与换装）。"""
        if not self._enabled:
            return
        self._play_file(os.path.join(audio_dir(), f"{style.raw()}.wav"))

    def play_mood(self, mood):
        """按心情 / 状态播放对应音频（可选增强，例如生气 → 生气音效）。"""
        if not self._enabled:
            return
        name = getattr(mood, "name", None)
        if not name:
            return
        self._play_file(os.path.join(audio_dir(), f"mood_{name.lower()}.wav"))
