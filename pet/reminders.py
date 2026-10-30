"""提醒中心：14 种提醒类型、语料与判定逻辑。

判定条件全部来自 config.conditions()，因此用户可在设置中自定义
（优化功能 3）。ReminderCenter 通过 delegate 把触发事件回传给宠物窗口。
"""
import random
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class ReminderKind(Enum):
    Sedentary = "sedentary"          # 久坐提醒
    Water = "water"                  # 喝水提醒
    LateNight = "latenight"          # 深夜关怀
    Slacking = "slacking"            # 摸鱼检测
    CpuHigh = "cpuhigh"              # CPU 红温
    MemoryPressure = "memory"        # 内存压力
    BatteryLow = "batterylow"        # 电量提醒
    BatteryFull = "batteryfull"      # 充满提醒
    DiskFull = "diskfull"            # 磁盘空间
    MorningGreet = "morning"         # 早晨问候
    LunchTime = "lunch"              # 午饭提醒
    AfternoonCoffee = "afternoon"    # 下午咖啡
    FridayEvening = "friday"         # 周五撒欢
    IdeOvertime = "ideovertime"      # 编码久战

    def title(self) -> str:
        return {
            ReminderKind.Sedentary: "久坐提醒",
            ReminderKind.Water: "喝水提醒",
            ReminderKind.LateNight: "深夜关怀",
            ReminderKind.Slacking: "摸鱼检测",
            ReminderKind.CpuHigh: "CPU 红温",
            ReminderKind.MemoryPressure: "内存压力",
            ReminderKind.BatteryLow: "电量提醒",
            ReminderKind.BatteryFull: "充满提醒",
            ReminderKind.DiskFull: "磁盘空间",
            ReminderKind.MorningGreet: "早晨问候",
            ReminderKind.LunchTime: "午饭提醒",
            ReminderKind.AfternoonCoffee: "下午咖啡",
            ReminderKind.FridayEvening: "周五撒欢",
            ReminderKind.IdeOvertime: "编码久战",
        }[self]

    def is_system(self) -> bool:
        return self in {
            ReminderKind.CpuHigh, ReminderKind.MemoryPressure,
            ReminderKind.BatteryLow, ReminderKind.BatteryFull,
            ReminderKind.DiskFull,
        }

    def is_companion(self) -> bool:
        return self in {
            ReminderKind.MorningGreet, ReminderKind.LunchTime,
            ReminderKind.AfternoonCoffee, ReminderKind.FridayEvening,
            ReminderKind.IdeOvertime,
        }

    @staticmethod
    def all() -> List["ReminderKind"]:
        return [k for k in ReminderKind]

    @staticmethod
    def health_cases() -> List["ReminderKind"]:
        return [k for k in ReminderKind if not k.is_system() and not k.is_companion()]

    @staticmethod
    def system_cases() -> List["ReminderKind"]:
        return [k for k in ReminderKind if k.is_system()]

    @staticmethod
    def companion_cases() -> List["ReminderKind"]:
        return [k for k in ReminderKind if k.is_companion()]


class IReminderDelegate:
    def reminder_fired(self, kind: ReminderKind, message: str):
        ...

    def sleepy_changed(self, sleepy: bool):
        ...

    def heat_changed(self, level: float):
        ...


_MESSAGES: Dict[ReminderKind, List[str]] = {
    ReminderKind.Sedentary: [
        "坐了一个小时啦，起来动动嘛！", "屁股要生根啦～站起来伸个懒腰吧！",
        "陪我走两步？你都坐一小时了！", "久坐伤腰！起来倒杯水顺便活动一下～",
    ],
    ReminderKind.Water: [
        "咕噜咕噜～该喝水啦！", "你已经半小时没喝水了哦，抿一口嘛",
        "多喝水才有精神呀，去接杯水吧！", "我都替你渴了……喝口水好不好？",
    ],
    ReminderKind.LateNight: [
        "这么晚了还在忙呀，早点休息嘛……", "夜深了，工作再多也要爱惜自己哦",
        "我都困了 zzZ……你也快睡吧？", "熬夜会秃的！明天再做也来得及～",
        "夜深了，有我陪你呀，但也别熬太晚哦～",
        "再忙也有我在身边，加油之余记得休息～",
        "夜里静悄悄的，有我陪着你，忙完就去睡吧～",
    ],
    ReminderKind.Slacking: [
        "都摸鱼半小时了哦……我可什么都没看见",
        "视频好看吗？要不要考虑干点活？",
        "嘘——老板来了！（骗你的，但也该收心啦）",
        "摸鱼一时爽，一直摸鱼一直慌哦～",
    ],
    ReminderKind.CpuHigh: [
        "好烫好烫！CPU 都 {v} 了，是谁在偷偷挖矿！",
        "呼——风扇都要起飞啦，CPU 飙到 {v}！",
        "红温警告！我要被烤熟了……快看看哪个 App 在发疯！",
        "炫……烫烫烫！CPU {v}，快救救我！",
    ],
    ReminderKind.MemoryPressure: [
        "内存要被挤爆啦，关几个 App 让我喘口气～",
        "好挤呀……内存不够用了，清理一下嘛",
        "App 开太多啦，我都快被挤出屏幕了！",
    ],
    ReminderKind.BatteryLow: [
        "电量只剩 {v} 啦，快给我充电！",
        "肚子饿了……电池只有 {v} 了，插电插电！",
        "再不充电我们就要一起睡着了哦（{v}）",
    ],
    ReminderKind.BatteryFull: [
        "吃饱啦～电池充满了，可以拔线啦！",
        "满电出发！记得拔掉充电线哦～",
    ],
    ReminderKind.DiskFull: [
        "磁盘只剩 {v} 空位啦，该大扫除了！",
        "装不下啦……磁盘剩 {v}，删点东西嘛",
    ],
    ReminderKind.MorningGreet: [
        "早上好呀！今天也要元气满满哦～", "新的一天开始啦，冲鸭冲鸭！",
        "早安早安～今天想做点什么呀？", "太阳晒屁股啦，今天也请多指教！",
    ],
    ReminderKind.LunchTime: [
        "咕咕咕～到饭点啦，去吃点好的！", "十二点啦！干饭人干饭魂，走起走起～",
        "肚子是不是咕咕叫啦？该吃午饭咯！", "再忙也要好好吃饭呀，午饭时间到！",
    ],
    ReminderKind.AfternoonCoffee: [
        "下午三点啦，来杯咖啡提提神？", "下午茶时间到～来点咖啡或小点心嘛！",
        "有点困了吧？喝口咖啡满血复活！",
    ],
    ReminderKind.FridayEvening: [
        "周五啦！晚上要不要犒劳一下自己～", "耶！周五晚上到咯，尽情撒欢吧！",
        "辛苦一周啦，今晚好好放松一下嘛～", "周末近在眼前，先嗨一个再说！",
    ],
    ReminderKind.IdeOvertime: [
        "代码写两个小时啦，起来伸个懒腰嘛！", "敲了好久键盘啦，让眼睛休息一下下～",
        "连续奋战两小时！起来走走喝口水吧？", "卷了两个钟头啦……劳逸结合才高效哦！",
    ],
}

_TEST_DETAILS = {
    ReminderKind.CpuHigh: "97%",
    ReminderKind.BatteryLow: "18%",
    ReminderKind.DiskFull: "9GB",
}


class ReminderCenter:
    TICK_SECONDS = 30  # 与 config.global_gap 配合的最小判定粒度

    def __init__(self, monitor, system_monitor):
        self._monitor = monitor
        self._system = system_monitor
        self.delegate: Optional[IReminderDelegate] = None

        self.sleepy = False
        # 计时累加器
        self._active_seconds = 0.0
        self._water_seconds = 0.0
        self._ide_work_seconds = 0.0
        # 各类上次触发时间
        self._last_slack_fire = datetime.min
        self._last_late_fire = datetime.min
        self._last_any_fire = datetime.min
        self._last_cpu_fire = datetime.min
        self._last_mem_fire = datetime.min
        self._last_disk_fire = datetime.min
        self._cpu_high_ticks = 0
        self._battery_stage = 0
        self._pending_battery_stage = 0
        self._battery_full_fired = False
        self._fired_today = set()
        self._last_reset_day = datetime.now().day
        self._friday_fired_week = -1
        self._pending_detail: Dict[ReminderKind, str] = {}

    @property
    def front_emotion_tags(self):
        from .activity import category_emotion_tags
        return category_emotion_tags(self._monitor.front_category)

    # ---------- 控制 ----------
    def start(self):
        from .config import UserSettings
        self._system.prime_cpu()
        self._system.cpu_usage()
        self._update_sleepy(UserSettings.conditions())

    def is_enabled(self, kind: ReminderKind) -> bool:
        from .config import UserSettings
        return UserSettings.reminder_enabled(kind)

    def set_enabled(self, kind: ReminderKind, enabled: bool):
        from .config import UserSettings
        UserSettings.set_reminder_enabled(kind, enabled)

    def fire(self, kind: ReminderKind):
        from .config import UserSettings
        # 重置对应计时，避免立刻重复触发
        if kind == ReminderKind.Sedentary:
            self._active_seconds = 0
        elif kind == ReminderKind.Water:
            self._water_seconds = 0
        elif kind == ReminderKind.Slacking:
            self._last_slack_fire = datetime.now()
        elif kind == ReminderKind.LateNight:
            self._last_late_fire = datetime.now()
        elif kind == ReminderKind.CpuHigh:
            self._last_cpu_fire = datetime.now()
            self._cpu_high_ticks = 0
        elif kind == ReminderKind.MemoryPressure:
            self._last_mem_fire = datetime.now()
        elif kind == ReminderKind.BatteryLow:
            self._battery_stage = max(self._battery_stage, self._pending_battery_stage)
        elif kind == ReminderKind.BatteryFull:
            self._battery_full_fired = True
        elif kind == ReminderKind.DiskFull:
            self._last_disk_fire = datetime.now()
        elif kind in (ReminderKind.MorningGreet, ReminderKind.LunchTime,
                     ReminderKind.AfternoonCoffee):
            self._fired_today.add(kind)
        elif kind == ReminderKind.FridayEvening:
            self._friday_fired_week = self._iso_week(datetime.now())
        elif kind == ReminderKind.IdeOvertime:
            self._ide_work_seconds = 0

        self._last_any_fire = datetime.now()
        pool = _MESSAGES.get(kind, [])
        message = random.choice(pool) if pool else ""
        detail = self._pending_detail.get(kind) or _TEST_DETAILS.get(kind, "")
        if "{v}" in message and detail:
            message = message.replace("{v}", detail)
        if self.delegate:
            self.delegate.reminder_fired(kind, message)

    # ---------- 周期性 tick（由主窗口 QTimer 每 30s 调用）----------
    def tick(self):
        from .config import UserSettings
        c = UserSettings.conditions()
        today = datetime.now().day
        if today != self._last_reset_day:
            self._fired_today.clear()
            self._last_reset_day = today

        idle = self._monitor.idle_seconds()
        present = idle < c["presence_idle_minutes"] * 60

        if present:
            self._active_seconds += self.TICK_SECONDS
            self._water_seconds += self.TICK_SECONDS
        else:
            self._active_seconds = 0

        cat = self._monitor.front_category
        if present and cat is not None and cat.value in ("ide", "terminal"):
            self._ide_work_seconds += self.TICK_SECONDS
        if not present:
            self._ide_work_seconds = 0

        self._update_sleepy(c)

        sys_candidates = self._sample_system(c)

        if (datetime.now() - self._last_any_fire).total_seconds() < c["global_gap_seconds"]:
            return

        candidates: List[ReminderKind] = list(sys_candidates)
        if self.is_enabled(ReminderKind.Sedentary) and \
                self._active_seconds >= c["sedentary_minutes"] * 60:
            candidates.append(ReminderKind.Sedentary)
        if self.is_enabled(ReminderKind.LateNight) and self.sleepy and present and \
                (datetime.now() - self._last_late_fire).total_seconds() >= \
                c["late_care_interval_minutes"] * 60:
            candidates.append(ReminderKind.LateNight)
        if self.is_enabled(ReminderKind.Water) and \
                self._water_seconds >= c["water_minutes"] * 60:
            candidates.append(ReminderKind.Water)
        if self.is_enabled(ReminderKind.Slacking) and \
                self._monitor.slacking_seconds >= c["slack_minutes"] * 60 and \
                (datetime.now() - self._last_slack_fire).total_seconds() >= \
                c["slack_repeat_minutes"] * 60:
            candidates.append(ReminderKind.Slacking)

        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()  # Monday=0 .. Sunday=6
        week = self._iso_week(now)
        if self.is_enabled(ReminderKind.MorningGreet) and present and \
                self._in_window(hour, c["morning_start_hour"], c["morning_end_hour"]) and \
                ReminderKind.MorningGreet not in self._fired_today:
            candidates.append(ReminderKind.MorningGreet)
        if self.is_enabled(ReminderKind.LunchTime) and present and \
                self._in_window(hour, c["lunch_start_hour"], c["lunch_end_hour"]) and \
                ReminderKind.LunchTime not in self._fired_today:
            candidates.append(ReminderKind.LunchTime)
        if self.is_enabled(ReminderKind.AfternoonCoffee) and present and \
                self._in_window(hour, c["afternoon_start_hour"], c["afternoon_end_hour"]) and \
                ReminderKind.AfternoonCoffee not in self._fired_today:
            candidates.append(ReminderKind.AfternoonCoffee)
        if self.is_enabled(ReminderKind.FridayEvening) and present and weekday == 4 and \
                self._in_window(hour, c["friday_start_hour"], c["friday_end_hour"]) and \
                self._friday_fired_week != week:
            candidates.append(ReminderKind.FridayEvening)
        if self.is_enabled(ReminderKind.IdeOvertime) and \
                self._ide_work_seconds >= c["ide_overtime_minutes"] * 60:
            candidates.append(ReminderKind.IdeOvertime)

        if candidates:
            self.fire(candidates[0])

    # ---------- 内部 ----------
    def _in_window(self, hour: int, start: int, end: int) -> bool:
        if start <= end:
            return start <= hour <= end
        # 跨午夜窗口（此处陪伴时段不跨午夜，保留兼容）
        return hour >= start or hour <= end

    @staticmethod
    def _iso_week(d: datetime) -> int:
        return d.isocalendar()[1]

    def _update_sleepy(self, c):
        hour = datetime.now().hour
        night = hour >= c["late_night_start_hour"] or hour < c["late_night_end_hour"]
        if night != self.sleepy:
            self.sleepy = night
            if self.delegate:
                self.delegate.sleepy_changed(night)

    def _sample_system(self, c):
        candidates: List[ReminderKind] = []
        cpu = self._system.cpu_usage()
        heat = max(0.0, min(1.0, (cpu - 0.6) / 0.4))
        if self.delegate:
            self.delegate.heat_changed(heat if self.is_enabled(ReminderKind.CpuHigh) else 0.0)

        if cpu >= c["cpu_threshold"]:
            self._cpu_high_ticks += 1
        else:
            self._cpu_high_ticks = 0

        if self.is_enabled(ReminderKind.CpuHigh) and \
                self._cpu_high_ticks >= c["cpu_ticks_needed"] and \
                (datetime.now() - self._last_cpu_fire).total_seconds() >= \
                c["cpu_repeat_minutes"] * 60:
            self._pending_detail[ReminderKind.CpuHigh] = f"{int(cpu * 100)}%"
            candidates.append(ReminderKind.CpuHigh)

        self._system.sample_memory_pressure(c["mem_warning"], c["mem_critical"])
        if self.is_enabled(ReminderKind.MemoryPressure) and \
                self._system.memory_pressure_critical and \
                (datetime.now() - self._last_mem_fire).total_seconds() >= \
                c["mem_repeat_minutes"] * 60:
            candidates.append(ReminderKind.MemoryPressure)

        battery = self._system.query_battery_state()
        if battery is not None:
            if battery.on_ac_power:
                self._battery_stage = 0
                if self.is_enabled(ReminderKind.BatteryFull) and \
                        battery.percent >= 98 and not self._battery_full_fired:
                    candidates.append(ReminderKind.BatteryFull)
            else:
                self._battery_full_fired = False
                if battery.percent > 25:
                    self._battery_stage = 0
                self._pending_battery_stage = 2 if battery.percent <= 10 else \
                    1 if battery.percent <= 20 else 0
                if self.is_enabled(ReminderKind.BatteryLow) and \
                        self._pending_battery_stage > self._battery_stage:
                    self._pending_detail[ReminderKind.BatteryLow] = f"{battery.percent}%"
                    candidates.append(ReminderKind.BatteryLow)

        disk = self._system.disk_free()
        if self.is_enabled(ReminderKind.DiskFull) and disk is not None and \
                disk[0] < c["disk_free_threshold"] and \
                (datetime.now() - self._last_disk_fire).total_seconds() >= \
                c["disk_repeat_hours"] * 3600:
            self._pending_detail[ReminderKind.DiskFull] = f"{disk[1]:.0f}GB"
            candidates.append(ReminderKind.DiskFull)

        return candidates
