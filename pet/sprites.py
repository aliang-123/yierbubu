"""精灵图集切片 + 贴纸包加载。

- SpriteSheet：把 8×9 的 spritesheet.webp 按状态行切片为各帧（PIL 图像）。
- PackLibrary / Sticker：加载 Packs/<pack>/ 下的 frame_*.png 帧序列与 meta.json。

本模块不依赖 PyQt，返回的均为 PIL.Image（RGBA），由上层转换为 QPixmap。
"""
import json
import os
from typing import Dict, List, Optional

from PIL import Image

from .states import PetState
from .styles import PetStyle

# 与原版 8×9 图集契约一致
COLUMNS = 8
CELL_WIDTH = 192
CELL_HEIGHT = 208
ROWS = 9


def _asset_dir() -> str:
    # 资源相对可执行入口的 Assets 目录；同时兼容开发态
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "Assets"),
        os.path.join(os.getcwd(), "Assets"),
    ]
    for c in candidates:
        if os.path.isdir(os.path.abspath(c)):
            return os.path.abspath(c)
    return os.path.abspath(candidates[0])


class SpriteSheet:
    """经典一二精灵图集。"""

    def __init__(self, image: Image.Image):
        w, h = image.size
        scale_x = w / (COLUMNS * CELL_WIDTH)
        scale_y = h / (ROWS * CELL_HEIGHT)
        self._frames: Dict[PetState, List[Image.Image]] = {}
        for state in PetState.all():
            durations = state.durations_ms()
            row = state.row
            frames: List[Image.Image] = []
            for col in range(len(durations)):
                x = int(col * CELL_WIDTH * scale_x)
                y = int(row * CELL_HEIGHT * scale_y)
                cw = int(CELL_WIDTH * scale_x)
                ch = int(CELL_HEIGHT * scale_y)
                crop = image.crop((x, y, x + cw, y + ch)).convert("RGBA")
                # 稳定缓存键：精灵图集按 状态+列 唯一定位，避免按对象 id 缓存
                # （对象 id 会变，导致 _pixmap_cache 无限增长）。
                crop._key = f"classic:{state.name}:{col}"
                frames.append(crop)
            self._frames[state] = frames

    @classmethod
    def load(cls) -> Optional["SpriteSheet"]:
        path = os.path.join(_asset_dir(), "spritesheet.webp")
        if not os.path.exists(path):
            return None
        try:
            with Image.open(path) as im:
                return cls(im.convert("RGBA"))
        except Exception:
            return None

    def frames_for(self, state: PetState) -> List[Image.Image]:
        return self._frames.get(state, [])


class Sticker:
    def __init__(self, sid: str, fps: float, frame_count: int,
                 tags: List[str], directory: str):
        self.id = sid
        self.fps = fps
        self.frame_count = frame_count
        self.tags = tags
        self.directory = directory
        self._frames_cache: Optional[List[Image.Image]] = None

    def load_frames(self) -> List[Image.Image]:
        # 懒加载并缓存：贴纸帧只解码一次，后续拖拽/循环复用，
        # 既降低 CPU 抖动，也避免每次重新构造 QPixmap 重新进入缓冲区窗口。
        if self._frames_cache is not None:
            return self._frames_cache
        frames: List[Image.Image] = []
        for i in range(self.frame_count):
            p = os.path.join(self.directory, f"frame_{i:03d}.png")
            if not os.path.exists(p):
                continue
            try:
                with Image.open(p) as im:
                    im = im.convert("RGBA")
                    im._key = f"{self.id}:{i}"  # 稳定缓存键
                    frames.append(im)
            except Exception:
                pass
        self._frames_cache = frames
        return frames


class PackLibrary:
    def __init__(self, style: PetStyle):
        self._stickers: List[Sticker] = []
        if not style.is_sticker():
            return
        pack_dir = os.path.join(_asset_dir(), "Packs", style.raw())
        if not os.path.isdir(pack_dir):
            return
        meta_path = os.path.join(pack_dir, "meta.json")
        if not os.path.exists(meta_path):
            return
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            return
        entries = meta.get("stickers", [])
        if not entries:
            return
        self._stickers = [
            Sticker(
                sid=e.get("id", ""),
                fps=float(e.get("fps", 8)),
                frame_count=int(e.get("frames", 0)),
                tags=list(e.get("tags", [])),
                directory=os.path.join(pack_dir, e.get("id", "")),
            )
            for e in entries
            if e.get("id")
        ]

    @property
    def is_valid(self) -> bool:
        return len(self._stickers) > 0

    def random_sticker_any_of(self, tags: List[str]) -> Optional[Sticker]:
        for tag in tags:
            pool = [s for s in self._stickers if tag in s.tags]
            if pool:
                import random
                return random.choice(pool)
        if self._stickers:
            import random
            return random.choice(self._stickers)
        return None

    def stickers(self) -> List[Sticker]:
        return self._stickers
