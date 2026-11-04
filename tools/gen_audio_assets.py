"""生成「一二布布桌面宠物」的角色 / 心情短音频素材。

为什么是合成而非下载：
  - 一二布布的角色语音多为原作者版权内容，粉丝项目的打包音频并无明确的再分发许可，
    直接打包进 exe 存在法律与可用性问题；
  - 本脚本仅用 Python 标准库（wave / struct / math）合成，零外部依赖、可离线复现、
    许可清晰，且每个角色拥有可辨识的独立动机（音色 / 音高 / 走向不同）；
  - AudioManager 支持把真实 .wav 直接丢进 Assets/Audio/ 同名覆盖即可替换，无需改代码。

输出：Assets/Audio/<角色>.wav 与 Assets/Audio/mood_<心情>.wav
  - classic 经典一二：温暖中音，两音轻柔
  - yier    活力一二：明亮高音，上行三音（俏皮）
  - bubu    活力布布：柔和低音，下行两音（温吞）
  - duo     一二布布：跨音区琶音（合体）
  - mood_angry  生气：短促低沉方波下行（“哼”）
  - mood_happy  开心：明亮上行三音
  - mood_love   喜欢：柔和两音
  - mood_sad    难过：低音缓慢下行
"""
import math
import os
import struct
import wave

SR = 44100
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "Assets", "Audio")

# 每个音符：(频率Hz, 起拍s, 时长s, 振幅0~1, 波形, 附加谐波[(倍频, 振幅)])
SINE_SOFT = [(2, 0.15), (3, 0.07)]


def _render_note(freq, start, dur, amp, wave_type, harmonics):
    n = int(SR * (start + dur)) - int(SR * start)
    base = int(SR * start)
    out = [0.0] * base + [0.0] * 0  # 占位，下面单独算
    samples = []
    total = int(SR * dur)
    atk = 0.008
    for i in range(total):
        t = i / SR
        if t < atk:
            env = t / atk
        else:
            rel = (t - atk) / (dur - atk) if dur > atk else 1.0
            env = math.exp(-3.0 * rel)
        if wave_type == "square":
            s = 0.0
            for k in range(1, 8, 2):
                s += (1.0 / k) * math.sin(2 * math.pi * freq * k * t)
            s *= (4.0 / math.pi)
        elif wave_type == "saw":
            s = 0.0
            for k in range(1, 7):
                s += (1.0 / k) * math.sin(2 * math.pi * freq * k * t)
            s *= (2.0 / math.pi)
        else:  # sine + 软谐波
            s = math.sin(2 * math.pi * freq * t)
            for h, a in (harmonics or []):
                s += a * math.sin(2 * math.pi * freq * h * t)
        samples.append(amp * env * s)
    return base, samples


def compose(notes):
    length = 0
    for freq, start, dur, amp, wtype, harm in notes:
        length = max(length, int(SR * (start + dur)))
    buf = [0.0] * length
    for freq, start, dur, amp, wtype, harm in notes:
        base, samples = _render_note(freq, start, dur, amp, wtype, harm)
        for i, v in enumerate(samples):
            if base + i < length:
                buf[base + i] += v
    # 归一化，避免叠加削波
    peak = max(1e-6, max(abs(x) for x in buf))
    scale = 0.9 / peak
    pcm = bytearray()
    for x in buf:
        v = int(max(-1.0, min(1.0, x * scale)) * 32767)
        pcm += struct.pack("<h", v)
    return bytes(pcm)


def write_wav(name, pcm):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)
    print(f"  wrote {name} ({len(pcm)} bytes)")


def main():
    motifs = {
        # 角色：温暖 / 明亮 / 柔和 / 合体
        "classic.wav": [
            (523.25, 0.00, 0.18, 0.50, "sine", SINE_SOFT),
            (659.25, 0.16, 0.32, 0.45, "sine", SINE_SOFT),
        ],
        "yier.wav": [
            (783.99, 0.00, 0.12, 0.50, "sine", SINE_SOFT),
            (1046.50, 0.10, 0.12, 0.50, "sine", SINE_SOFT),
            (1318.51, 0.20, 0.34, 0.45, "sine", SINE_SOFT),
        ],
        "bubu.wav": [
            (440.00, 0.00, 0.20, 0.50, "sine", SINE_SOFT),
            (349.23, 0.18, 0.36, 0.42, "sine", SINE_SOFT),
        ],
        "duo.wav": [
            (523.25, 0.00, 0.14, 0.45, "sine", SINE_SOFT),
            (659.25, 0.12, 0.14, 0.45, "sine", SINE_SOFT),
            (392.00, 0.24, 0.32, 0.42, "sine", SINE_SOFT),
        ],
        # 心情：生气 / 开心 / 喜欢 / 难过
        "mood_angry.wav": [
            (220.00, 0.00, 0.10, 0.55, "square", None),
            (180.00, 0.09, 0.20, 0.50, "square", None),
        ],
        "mood_happy.wav": [
            (1046.50, 0.00, 0.10, 0.50, "sine", SINE_SOFT),
            (1318.51, 0.09, 0.12, 0.50, "sine", SINE_SOFT),
            (1567.98, 0.19, 0.30, 0.45, "sine", SINE_SOFT),
        ],
        "mood_love.wav": [
            (523.25, 0.00, 0.22, 0.45, "sine", SINE_SOFT),
            (783.99, 0.18, 0.32, 0.40, "sine", SINE_SOFT),
        ],
        "mood_sad.wav": [
            (440.00, 0.00, 0.30, 0.45, "sine", SINE_SOFT),
            (349.23, 0.26, 0.42, 0.40, "sine", SINE_SOFT),
        ],
    }
    print(f"输出目录：{OUT_DIR}")
    for name, notes in motifs.items():
        write_wav(name, compose(notes))
    print("完成。")


if __name__ == "__main__":
    main()
