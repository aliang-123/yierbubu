"""动画状态定义（与 mac/win 原版 8×9 图集契约一致）。

每一行（row）对应一种动作，每行的帧数由 durations_ms 的长度决定。
"""
from enum import Enum


class PetState(Enum):
    Idle = 0
    RunningRight = 1
    RunningLeft = 2
    Waving = 3
    Jumping = 4
    Failed = 5
    Waiting = 6
    Running = 7       # 工作中
    Review = 8        # 审阅

    # 行号 == 枚举值（Idle=0 ... Review=8），与 8×9 图集顺序一致
    @property
    def row(self) -> int:
        return self.value

    def durations_ms(self):
        """每一帧停留的毫秒数；列表长度即该状态的帧数。"""
        return {
            PetState.Idle: [280, 110, 110, 140, 140, 320],
            PetState.RunningRight: [120, 120, 120, 120, 120, 120, 120, 220],
            PetState.RunningLeft: [120, 120, 120, 120, 120, 120, 120, 220],
            PetState.Waving: [140, 140, 140, 280],
            PetState.Jumping: [140, 140, 140, 140, 280],
            PetState.Failed: [140, 140, 140, 140, 140, 140, 140, 240],
            PetState.Waiting: [150, 150, 150, 150, 150, 260],
            PetState.Running: [120, 120, 120, 120, 120, 220],
            PetState.Review: [150, 150, 150, 150, 150, 280],
        }[self]

    def display_name(self) -> str:
        return {
            PetState.Idle: "待机",
            PetState.RunningRight: "向右跑",
            PetState.RunningLeft: "向左跑",
            PetState.Waving: "挥手",
            PetState.Jumping: "跳跃",
            PetState.Failed: "沮丧",
            PetState.Waiting: "等待",
            PetState.Running: "工作中",
            PetState.Review: "审阅",
        }[self]

    def storage_key(self) -> str:
        return {
            PetState.Idle: "idle",
            PetState.RunningRight: "running-right",
            PetState.RunningLeft: "running-left",
            PetState.Waving: "waving",
            PetState.Jumping: "jumping",
            PetState.Failed: "failed",
            PetState.Waiting: "waiting",
            PetState.Running: "running",
            PetState.Review: "review",
        }[self]

    @staticmethod
    def from_storage_key(raw: str):
        table = {
            "idle": PetState.Idle,
            "running-right": PetState.RunningRight,
            "running-left": PetState.RunningLeft,
            "waving": PetState.Waving,
            "jumping": PetState.Jumping,
            "failed": PetState.Failed,
            "waiting": PetState.Waiting,
            "running": PetState.Running,
            "review": PetState.Review,
        }
        return table.get(raw)

    @staticmethod
    def all():
        return [s for s in PetState]
