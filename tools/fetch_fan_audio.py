"""从粉丝项目 sduwcdd/YierPet-Windows 提取全部音频到本项目的 Assets/Audio。

映射规则（对应角色名前缀）：
  yier-*  -> Assets/Audio/yier/
  bubu-*  -> Assets/Audio/bubu/
然后复制：
  yier/*  -> Assets/Audio/classic/   (classic 与 yier 同为「一二」声线)
  bubu/*  -> Assets/Audio/duo/       (duo 与 bubu 同为「布布」声线)

下载走 curl（复用已验证可用的网络通道），API 取文件清单，raw 取内容。
"""
import os
import json
import shutil
import subprocess

REPO = "sduwcdd/YierPet-Windows"
BRANCH = "main"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
AUDIO_EXTS = (".wav", ".mp3", ".ogg", ".oga", ".m4a", ".flac", ".aac")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AUDIO = os.path.join(ROOT, "Assets", "Audio")


def curl(url, binary=False):
    cmd = ["curl", "-sL", "--max-time", "60", "-H", f"User-Agent: {UA}", url]
    return subprocess.run(cmd, capture_output=True)


def list_audio_paths():
    r = curl(f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1")
    d = json.loads(r.stdout)
    if "tree" not in d:
        raise RuntimeError(f"无法获取仓库文件树: {r.stdout[:300]}")
    return [t["path"] for t in d["tree"]
            if t["path"].lower().endswith(AUDIO_EXTS)]


def target_dir_for(name):
    low = name.lower()
    if low.startswith("yier"):
        return os.path.join(AUDIO, "yier")
    if low.startswith("bubu"):
        return os.path.join(AUDIO, "bubu")
    return None


def main():
    paths = list_audio_paths()
    print(f"仓库音频文件总数: {len(paths)}")

    ok = 0
    for p in paths:
        name = os.path.basename(p)
        td = target_dir_for(name)
        if td is None:
            print("SKIP (无对应角色目录):", p)
            continue
        os.makedirs(td, exist_ok=True)
        dest = os.path.join(td, name)
        rr = curl(f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{p}")
        data = rr.stdout
        if len(data) < 100 or data[:4] != b"RIFF":
            print(f"FAIL {p} (len={len(data)}, head={data[:4]!r})")
            continue
        with open(dest, "wb") as f:
            f.write(data)
        ok += 1
    print(f"下载完成: {ok}/{len(paths)}")

    # 复制 yier->classic, bubu->duo，保证所有角色都有完整语音
    for src_name, dst_name in (("yier", "classic"), ("bubu", "duo")):
        s = os.path.join(AUDIO, src_name)
        d = os.path.join(AUDIO, dst_name)
        os.makedirs(d, exist_ok=True)
        n = 0
        for f in os.listdir(s):
            if f.lower().endswith(AUDIO_EXTS):
                shutil.copy2(os.path.join(s, f), os.path.join(d, f))
                n += 1
        print(f"复制 {src_name}/* -> {dst_name}/ : {n} 个文件")


if __name__ == "__main__":
    main()
