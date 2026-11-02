"""用户设置持久化（JSON）。

路径：%AppData%/YierBubu/settings.json
相比原版新增：
  - conditions.*  可自定义的提醒触发条件（时长 / 时段 / 阈值）
  - mouse_follow  鼠标跟随奔跑开关（优化功能 1）
"""
import json
import os
import time
from typing import Any

from .states import PetState
from .styles import PetStyle


class Conditions:
    """所有可被用户自定义的提醒条件，附带合理默认值。

    单位约定：分钟用于时长类条件，小时用于固定时段，比例为 0~1。
    """

    # 默认值表：(key, 默认值, 说明)
    DEFAULTS = {
        # —— 健康类 ——
        "sedentary_minutes": (60, "连续使用多少分钟后触发久坐提醒"),
        "water_minutes": (30, "距上次喝水多少分钟后提醒喝水"),
        "slack_minutes": (30, "摸鱼（前台为视频/娱乐进程）多少分钟后提醒"),
        "slack_repeat_minutes": (15, "摸鱼提醒的重复间隔"),
        "presence_idle_minutes": (5, "无输入操作多少分钟后视为离开"),
        # —— 深夜关怀 ——
        "late_night_start_hour": (23, "深夜关怀开始小时（含）"),
        "late_night_end_hour": (5, "深夜关怀结束小时（不含）"),
        "late_care_interval_minutes": (30, "深夜关怀最小重复间隔"),
        # —— 系统哨兵 ——
        "cpu_threshold": (0.85, "CPU 使用率超过该比例视为红温"),
        "cpu_ticks_needed": (3, "连续多少次采样超阈值后才提醒"),
        "cpu_repeat_minutes": (10, "CPU 红温提醒重复间隔"),
        "mem_warning": (85, "内存负载达到该比例视为警告"),
        "mem_critical": (92, "内存负载达到该比例视为严重"),
        "mem_repeat_minutes": (10, "内存压力提醒重复间隔"),
        "disk_free_threshold": (0.10, "磁盘剩余空间低于该比例提醒"),
        "disk_repeat_hours": (6, "磁盘空间提醒重复间隔（小时）"),
        # —— 陪伴模式时段（起止小时，闭区间由 start<=hour<=end 判定）——
        "morning_start_hour": (6, "早晨问候时段-起"),
        "morning_end_hour": (10, "早晨问候时段-止"),
        "lunch_start_hour": (12, "午饭提醒时段-起"),
        "lunch_end_hour": (12, "午饭提醒时段-止"),
        "afternoon_start_hour": (15, "下午咖啡时段-起"),
        "afternoon_end_hour": (15, "下午咖啡时段-止"),
        "friday_start_hour": (17, "周五撒欢时段-起"),
        "friday_end_hour": (19, "周五撒欢时段-止"),
        # —— 编码久战 ——
        "ide_overtime_minutes": (120, "连续编码/终端多少分钟后提醒休息"),
        # —— 通用 ——
        "global_gap_seconds": (90, "任意两条提醒之间的最小间隔（秒）"),
        # —— 速度手感 ——
        "walk_speed": (1.4, "自主散步速度（像素/帧@60fps）"),
        "follow_speed": (3.0, "鼠标跟随速度（像素/帧@30fps）"),
    }

    def defaults_dict(self) -> dict:
        return {k: v[0] for k, v in self.DEFAULTS.items()}


class UserSettings:
    _path = None
    _conditions_cache = None
    _conditions_cache_at = 0.0
    _CACHE_TTL = 2.0  # 条件字典缓存有效期（秒），避免每帧读盘 + json 解析

    @classmethod
    def path(cls) -> str:
        if cls._path is None:
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
            folder = os.path.join(base, "YierBubu")
            os.makedirs(folder, exist_ok=True)
            cls._path = os.path.join(folder, "settings.json")
        return cls._path

    # ---------- 底层读写 ----------
    @classmethod
    def _load(cls) -> dict:
        try:
            if os.path.exists(cls.path()):
                with open(cls.path(), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception:
            pass
        return {}

    @classmethod
    def _save(cls, data: dict):
        cls._conditions_cache = None  # 任何写盘都令条件缓存失效
        try:
            with open(cls.path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- 形象 ----------
    @classmethod
    def saved_style(cls) -> PetStyle:
        data = cls._load()
        return PetStyle.from_raw(data.get("pet.style")) or PetStyle.Classic

    @classmethod
    def set_saved_style(cls, style: PetStyle):
        data = cls._load()
        data["pet.style"] = style.raw()
        cls._save(data)

    # ---------- 提醒开关 ----------
    @classmethod
    def reminder_enabled(cls, kind) -> bool:
        key = f"reminder.{kind.name.lower()}.enabled"
        data = cls._load()
        if key not in data:
            return True
        return data[key] is True or data[key] == "1"

    @classmethod
    def set_reminder_enabled(cls, kind, enabled: bool):
        key = f"reminder.{kind.name.lower()}.enabled"
        data = cls._load()
        data[key] = bool(enabled)
        cls._save(data)

    # ---------- 鼠标跟随开关（优化 1）----------
    @classmethod
    def mouse_follow(cls) -> bool:
        data = cls._load()
        return bool(data.get("mouse_follow", False))

    @classmethod
    def set_mouse_follow(cls, enabled: bool):
        data = cls._load()
        data["mouse_follow"] = bool(enabled)
        cls._save(data)

    # ---------- 自定义条件（优化 3）----------
    @classmethod
    def conditions(cls) -> dict:
        """返回合并了默认值的完整条件字典（带 2s TTL 缓存，避免每帧读盘）。"""
        now = time.monotonic()
        if cls._conditions_cache is not None and \
                (now - cls._conditions_cache_at) < cls._CACHE_TTL:
            return cls._conditions_cache
        data = cls._load()
        merged = Conditions().defaults_dict()
        merged.update(data.get("conditions", {}) or {})
        # 类型兜底
        for k, (default, _desc) in Conditions.DEFAULTS.items():
            if k not in merged:
                merged[k] = default
            else:
                try:
                    merged[k] = type(default)(merged[k])
                except (TypeError, ValueError):
                    merged[k] = default
        cls._conditions_cache = merged
        cls._conditions_cache_at = now
        return merged

    @classmethod
    def set_condition(cls, key: str, value: Any):
        if key not in Conditions.DEFAULTS:
            raise KeyError(f"未知条件：{key}")
        data = cls._load()
        conditions = data.get("conditions", {}) or {}
        default = Conditions.DEFAULTS[key][0]
        try:
            conditions[key] = type(default)(value)
        except (TypeError, ValueError):
            conditions[key] = default
        data["conditions"] = conditions
        cls._save(data)

    @classmethod
    def reset_conditions(cls):
        data = cls._load()
        data.pop("conditions", None)
        cls._save(data)

    # ---------- 通用键值 ----------
    @classmethod
    def get(cls, key: str, default=None):
        return cls._load().get(key, default)

    @classmethod
    def set(cls, key: str, value):
        data = cls._load()
        data[key] = value
        cls._save(data)
