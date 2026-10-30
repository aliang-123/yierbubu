"""形象定义：经典一二（精灵图集）与 活力一二 / 活力布布 / 一二布布（贴纸包）。"""
from enum import Enum


class PetStyle(Enum):
    Classic = "classic"   # 经典一二（spritesheet.webp）
    Yier = "yier"         # 活力一二
    Bubu = "bubu"         # 活力布布
    Duo = "duo"           # 一二布布合体

    def display_name(self) -> str:
        return {
            PetStyle.Classic: "经典一二",
            PetStyle.Yier: "活力一二",
            PetStyle.Bubu: "活力布布",
            PetStyle.Duo: "一二布布",
        }[self]

    def is_sticker(self) -> bool:
        """非经典形象均以 PNG 帧序列贴纸包形式加载。"""
        return self != PetStyle.Classic

    def raw(self) -> str:
        return self.value

    @staticmethod
    def from_raw(raw):
        for s in PetStyle:
            if s.value == raw:
                return s
        return None

    @staticmethod
    def all():
        return [s for s in PetStyle]
