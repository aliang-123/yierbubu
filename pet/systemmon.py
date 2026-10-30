"""系统监视：CPU / 内存 / 电量 / 磁盘（跨平台，Windows 重点支持）。

优先使用 psutil；电量在无电池的设备上返回 None。
"""
import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None


@dataclass
class BatteryState:
    percent: int
    is_charging: bool
    on_ac_power: bool


class SystemMonitor:
    def __init__(self):
        self._cpu_primed = False
        self._last_cpu = 0.0
        self.memory_pressure_warning = False
        self.memory_pressure_critical = False

    def cpu_usage(self) -> float:
        """返回 0~1 的 CPU 总使用率；首次调用返回 0（需预热）。"""
        if psutil is None:
            return 0.0
        try:
            v = psutil.cpu_percent(interval=None) / 100.0
            if not self._cpu_primed:
                self._cpu_primed = True
                self._last_cpu = v
                return 0.0
            self._last_cpu = v
            return max(0.0, min(1.0, v))
        except Exception:
            return self._last_cpu

    def prime_cpu(self):
        if psutil is not None:
            try:
                psutil.cpu_percent(interval=None)
            except Exception:
                pass

    def sample_memory_pressure(self, warning: float = 85.0, critical: float = 92.0):
        if psutil is None:
            self.memory_pressure_warning = False
            self.memory_pressure_critical = False
            return
        try:
            load = psutil.virtual_memory().percent
            self.memory_pressure_warning = load >= warning
            self.memory_pressure_critical = load >= critical
        except Exception:
            self.memory_pressure_warning = False
            self.memory_pressure_critical = False

    def query_battery_state(self) -> Optional[BatteryState]:
        if psutil is None:
            return None
        try:
            b = psutil.sensors_battery()
            if b is None:
                return None
            on_ac = bool(b.power_plugged)
            charging = bool(b.power_plugged) and b.percent < 100
            return BatteryState(
                percent=int(b.percent),
                is_charging=charging,
                on_ac_power=on_ac,
            )
        except Exception:
            return None

    def disk_free(self) -> Optional[Tuple[float, float]]:
        """返回 (剩余比例, 剩余GB)。"""
        if psutil is None:
            return None
        try:
            root = os.path.splitdrive(os.environ.get("SystemRoot", "C:\\"))[0] + "\\"
            du = psutil.disk_usage(root)
            if du.total <= 0:
                return None
            free = du.free
            total = du.total
            return (free / total, free / 1_000_000_000.0)
        except Exception:
            return None
