"""验证音频系统（目录式角色列表 + 按角色分开的状态音效，offscreen 无头）：

1) audio_dir 解析到 Assets/Audio；每个角色目录含 >=1 个真实音频；全局 mood_*.wav 兜底存在；
2) AudioManager 构造、默认开启；play_character / play_mood 无异常；
3) 角色音效为“列表”：往目录里加更多文件即被纳入（用临时目录验证 _list_clips 排除 mood_ 前缀）；
4) play_mood 优先取“当前角色目录”的 mood_<心情>.*，否则回落全局兜底；
5) set_enabled 持久化；
6) PetWindow 构造与 _apply_style 换装触发音频不崩溃；菜单含「音效」。

运行：QT_QPA_PLATFORM=offscreen ./.venv/Scripts/python.exe smoke_audio_fix.py
"""
import os
import sys
import tempfile
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pet import sprites
from pet.activity import ActivityMonitor
from pet.audio import (AudioManager, audio_dir, _list_clips,
                       _list_character_clips, _list_mood_clips)
from pet.config import UserSettings
from pet.pet_window import PetWindow, Mood
from pet.reminders import ReminderCenter
from pet.styles import PetStyle
from pet.systemmon import SystemMonitor


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    d = audio_dir()
    print("audio_dir =", d)
    assert os.path.isdir(d), "音频目录不存在"

    # 1) 全局心情兜底文件
    for name in ["mood_angry.wav", "mood_happy.wav", "mood_love.wav", "mood_sad.wav"]:
        assert os.path.exists(os.path.join(d, name)), f"缺少全局兜底 {name}"
    print("PASS: 全局心情兜底 mood_*.wav 齐备")

    # 2) 每个角色目录含真实音频
    for st in PetStyle.all():
        clips = _list_character_clips(st)
        assert clips, f"角色 {st.raw()} 目录无音频"
        print(f"  {st.raw()}: {len(clips)} 个角色音效 -> {os.path.basename(clips[0])}")
    print("PASS: 四个角色目录均含真实音频（目录式列表）")

    # 3) AudioManager + 播放不崩溃
    aud = AudioManager()
    assert aud.is_enabled(), "音频默认应开启"
    for st in PetStyle.all():
        aud.play_character(st)
    for m in [Mood.Angry, Mood.Happy, Mood.Love, Mood.Sad]:
        aud.play_mood(m)
    print("PASS: AudioManager 构造、play_character / play_mood 在 offscreen 下无异常")

    # 4) 列表扩展性：临时目录验证 _list_clips 列出音频并排除 mood_ 前缀
    tmp = tempfile.mkdtemp()
    try:
        open(os.path.join(tmp, "a.wav"), "wb").close()
        open(os.path.join(tmp, "b.mp3"), "wb").close()
        open(os.path.join(tmp, "mood_angry.wav"), "wb").close()
        open(os.path.join(tmp, "notes.txt"), "wb").close()
        all_clips = _list_clips(tmp)
        char_clips = _list_clips(tmp, prefix="", exclude_prefix="mood_")  # 排除 mood_
        mood_clips = _list_clips(tmp, prefix="mood_")
        assert len(all_clips) == 3, f"应列出 3 个音频，实际 {len(all_clips)}"
        assert len(char_clips) == 2, f"角色列表应排除 mood_，实际 {len(char_clips)}"
        assert len(mood_clips) == 1, f"mood_ 前缀应命中 1，实际 {len(mood_clips)}"
        print("PASS: 目录式列表可扩展（新增文件即纳入，mood_ 前缀被正确区分）")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # 5) play_mood 回落：当前角色目录无 mood 文件时，使用全局兜底（不崩溃）
    aud2 = AudioManager()
    aud2.play_character(PetStyle.Yier)     # 设定 current_style
    assert aud2._current_style == PetStyle.Yier
    # yier 目录里没有 mood_ 文件 -> 应回落到全局 mood_*.wav
    assert _list_mood_clips(PetStyle.Yier, Mood.Angry) == [], "yier 暂无专属 mood 文件"
    aud2.play_mood(Mood.Angry)             # 走全局兜底路径
    print("PASS: play_mood 无角色专属文件时回落全局兜底")

    # 6) 开关持久化
    try:
        UserSettings.set("audio.enabled", True)
        a3 = AudioManager()
        assert a3.is_enabled()
        a3.set_enabled(False)
        assert UserSettings.get("audio.enabled") is False
        a4 = AudioManager()
        assert not a4.is_enabled()
        a4.set_enabled(True)
        assert UserSettings.get("audio.enabled") is True
        print("PASS: 开关持久化（audio.enabled）正确")
    finally:
        UserSettings.set("audio.enabled", True)

    # 7) 集成：PetWindow 构造 + 换装触发音频不崩溃
    sheet = sprites.SpriteSheet.load()
    assert sheet is not None, "精灵图集加载失败"
    center = ReminderCenter(ActivityMonitor(), SystemMonitor())
    pet = PetWindow(sheet, center)
    center.delegate = pet
    menu = pet._build_app_menu()
    texts = [a.text() for a in menu.actions()]
    assert "音效" in texts, "菜单缺少「音效」开关"
    print("PASS: 菜单含「音效」开关")
    for st in PetStyle.all():
        pet._apply_style(st)
    print("PASS: PetWindow 构造与 _apply_style 换装音频挂钩安全（无崩溃）")

    print("\nALL AUDIO SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
