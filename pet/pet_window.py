"""宠物主窗口：透明置顶、帧动画、拖拽/抛掷物理、自主行为，
以及三项优化：
  1) 鼠标跟随奔跑（可开关）
  2) 修复「一二布布」拖拽时奔跑失效（两角色同框自然同跑）
  3) 提醒条件通过 config 自定义（由设置对话框编辑）
"""
import math
import random
from datetime import datetime
from enum import Enum

from PyQt6.QtCore import Qt, QTimer, QRect, QPoint
from PyQt6.QtGui import QPixmap, QImage, QCursor, QPainter, QColor, QPainterPath, QTransform
from PyQt6.QtWidgets import (QWidget, QLabel, QMenu, QApplication)

from . import sprites
from .config import UserSettings
from .states import PetState
from .styles import PetStyle
from .speech import SpeechBubble


# 显示盒子尺寸（与原版 PetWidth/Height 一致，帧按统一比例缩放）
PET_WIDTH = 154
PET_HEIGHT = 166

# 物理 / 手感常量
THROW_SPEED_THRESHOLD = 550   # px/s，超过即视为抛掷
GRAVITY = 3000               # px/s^2
FLOOR_BOUNCE = 0.45
WALL_BOUNCE = 0.6


class Mood(Enum):
    Normal = 0
    Angry = 1
    Happy = 2
    Love = 3
    Sad = 4


_RUN_TAG_PRIORITY = ["exercise", "happy", "idle"]


def pil_to_pixmap(im):
    im = im.convert("RGBA")
    data = im.tobytes("raw", "RGBA")
    qim = QImage(data, im.width, im.height, QImage.Format.Format_RGBA8888)
    # 关键：深拷贝，使 QImage 完全拥有像素数据，脱离上面的临时 bytes 缓冲区。
    # 否则在 PyQt6 某些构建下 fromImage 可能共享底层缓冲，缓冲区被回收后出现
    # 悬垂引用，第一次渲染某帧（如抛掷的 Jumping 帧）时引发原生崩溃
    # (0xC0000409 / 栈缓冲区溢出)。
    qim = qim.copy()
    return QPixmap.fromImage(qim)


class PetWindow(QWidget):
    def __init__(self, sheet: sprites.SpriteSheet, reminder_center):
        super().__init__()
        self._sheet = sheet
        self._reminder_center = reminder_center

        self._state = PetState.Idle
        self._frame_index = 0
        self._frames: list = []          # 当前活动的 PIL 帧序列
        self._frame_ms: list = []         # 对应每帧毫秒
        self._loops_remaining = 0
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._step_animation)

        self._style = PetStyle.Classic
        self._pack = None
        self._sticker_frames: list = []
        self._sticker_ms = 120
        self._sticker_loops = 0
        self._current_sticker_id = None
        self._flip = False
        self._pixmap_cache: dict = {}

        self._behavior_timer = QTimer(self)
        self._behavior_timer.timeout.connect(self._on_behavior_tick)
        self._walk_timer = None
        self._walk_direction = 1
        self._random_behavior = True

        self._follow_timer = QTimer(self)
        self._follow_timer.timeout.connect(self._follow_step)
        self._follow_enabled = UserSettings.mouse_follow()

        # 抛掷物理
        self._physics_timer = QTimer(self)
        self._physics_timer.timeout.connect(self._step_physics)
        self._throw_vx = 0.0
        self._throw_vy = 0.0
        self._max_impact = 0.0
        self._throwing = False

        # 心情 / 状态
        self._mood = Mood.Normal
        self._mood_set_at = datetime.min
        self._last_interaction = datetime.now()
        self._was_away = False
        self._sleepy = False
        self._heat = 0.0
        self._heat_pixmap = None  # 复用的红温叠加层 Pixmap，避免每帧新建

        # 拖拽
        self._dragged = False
        self._drag_samples: list = []
        self._last_mouse = QPoint()
        self._popup_open = False  # 右键菜单是否打开（打开期间禁止移动本窗口）
        # 拖拽位移合并：mouseMove 只累计目标位置，由定时器以约 60fps 实际移动窗口，
        # 避免快速拖拽时每个 WM_MOUSEMOVE 都触发分层窗口 UpdateLayeredWindow（风暴），
        # 持续快速拖拽会在一段时间后耗尽/碎片化桌面堆导致原生崩溃 0xC0000409。
        self._drag_target = QPoint()
        self._drag_move_timer = QTimer(self)
        self._drag_move_timer.timeout.connect(self._apply_drag_move)

        self._build_ui()
        self._apply_style(UserSettings.saved_style())
        self._schedule_behavior()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(PET_WIDTH, PET_HEIGHT)

        area = self._working_area()
        self.move(int(area.left() + (area.width() - PET_WIDTH) / 2),
                 int(area.bottom() - PET_HEIGHT - 40))

        self._label = QLabel(self)
        self._label.setGeometry(0, 0, PET_WIDTH, PET_HEIGHT)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setScaledContents(False)
        # 让鼠标事件穿透到宠物窗口本身（否则子 Label 会吞掉拖拽/点击）
        self._label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._heat_label = QLabel(self)
        self._heat_label.setGeometry(0, 0, PET_WIDTH, PET_HEIGHT)
        self._heat_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._heat_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._heat_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._heat_label.setPixmap(QPixmap())
        self._heat_label.setStyleSheet("background: transparent;")

        self._bubble = SpeechBubble(self)

    def moveEvent(self, event):
        self._bubble.sync_position()
        super().moveEvent(event)

    # ---------------- 工具 ----------------
    def _working_area(self) -> QRect:
        screen = QApplication.primaryScreen()
        if screen is not None:
            return screen.availableGeometry()
        return QRect(0, 0, 1280, 720)

    def _pixmap_for(self, film, flip: bool) -> QPixmap:
        # 用稳定来源键（精灵图集/贴纸帧的 _key）而非对象 id 作缓存键，
        # 这样即使贴纸帧被重新解码，QPixmap 也只构建一次，缓存不会无限增长。
        key = (getattr(film, "_key", id(film)), flip)
        cached = self._pixmap_cache.get(key)
        if cached is not None:
            return cached
        pm = pil_to_pixmap(film)
        if flip:
            pm = pm.transformed(QTransform().scale(-1, 1))
        self._pixmap_cache[key] = pm
        return pm

    def _show_pixmap(self, pm: QPixmap):
        self._label.setPixmap(pm.scaled(
            PET_WIDTH, PET_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        if self._heat > 0:
            self._update_heat_overlay(pm)

    def _update_heat_overlay(self, pm: QPixmap):
        # 复用同一张 Pixmap，避免每帧新建；只在状态切换时 show/raise。
        if self._heat_pixmap is None or self._heat_pixmap.size() != pm.size():
            self._heat_pixmap = QPixmap(pm.size())
        res = self._heat_pixmap
        res.fill(Qt.GlobalColor.transparent)
        p = QPainter(res)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.drawPixmap(0, 0, pm)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(res.rect(), QColor(255, 0, 0, int(self._heat * 0.5 * 255)))
        p.end()
        self._heat_label.setPixmap(res.scaled(
            PET_WIDTH, PET_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        if not self._heat_label.isVisible():
            self._heat_label.show()
            self._heat_label.raise_()

    def _hide_heat(self):
        self._heat_label.setPixmap(QPixmap())
        self._heat_label.hide()

    # ---------------- 动画 ----------------
    def _set_state(self, state: PetState, loops: int = 0):
        if self._style.is_sticker():
            return
        self._state = state
        self._frame_index = 0
        self._frames = self._sheet.frames_for(state)
        self._frame_ms = state.durations_ms()
        self._loops_remaining = loops
        self._sticker_frames = []
        self._step_animation()

    def _step_animation(self):
        self._anim_timer.stop()
        if self._style.is_sticker():
            self._step_sticker()
            return
        if not self._frames:
            return
        if self._frame_index >= len(self._frames):
            self._frame_index = 0
            if self._loops_remaining > 0:
                self._loops_remaining -= 1
                if self._loops_remaining == 0:
                    self._state = PetState.Idle
                    self._frames = self._sheet.frames_for(PetState.Idle)
                    self._frame_ms = PetState.Idle.durations_ms()
        film = self._frames[self._frame_index]
        pm = self._pixmap_for(film, self._flip)
        self._show_pixmap(pm)
        ms = self._frame_ms[self._frame_index]
        if self._sleepy and self._state == PetState.Idle:
            ms = int(ms * 2.5)
        self._frame_index += 1
        self._anim_timer.setInterval(ms)
        self._anim_timer.start()

    # ---- 贴纸 ----
    def _play_sticker(self, sticker, loops: int):
        frames = sticker.load_frames()
        if not frames:
            return
        self._current_sticker_id = sticker.id
        self._sticker_frames = frames
        self._sticker_ms = int(1000.0 / max(1.0, sticker.fps))
        self._sticker_loops = loops
        self._frame_index = 0
        self._frames = []
        self._step_sticker()

    def _step_sticker(self):
        self._anim_timer.stop()
        if not self._sticker_frames:
            return
        if self._frame_index >= len(self._sticker_frames):
            self._frame_index = 0
            if self._sticker_loops > 0:
                self._sticker_loops -= 1
                if self._sticker_loops == 0:
                    self._sticker_idle()
                    return
        film = self._sticker_frames[self._frame_index]
        pm = self._pixmap_for(film, self._flip)
        self._show_pixmap(pm)
        self._frame_index += 1
        interval = self._sticker_ms
        if self._sleepy and self._sticker_loops == 0:
            interval = int(interval * 2)
        self._anim_timer.setInterval(interval)
        self._anim_timer.start()

    def _sticker_idle(self):
        self._frames = []
        if self._pack is None:
            return
        st = self._pack.random_sticker_any_of(self._context_tags())
        if st is not None:
            self._play_sticker(st, 0)

    def _run_sticker(self):
        """为贴纸风格选取一个「奔跑感」贴纸并循环播放。"""
        if self._pack is None:
            return
        st = None
        for tag in _RUN_TAG_PRIORITY:
            st = self._pack.random_sticker_any_of([tag])
            if st is not None:
                break
        if st is None:
            st = self._pack.random_sticker_any_of(["idle"])
        if st is not None:
            self._play_sticker(st, 9999)  # 大循环，直到停止

    def _context_tags(self) -> list:
        return self._reminder_center.front_emotion_tags or ["idle", "lazy", "happy"]

    def _play_once(self, state: PetState, loops: int = 2):
        self._stop_walk()
        self._set_state(state, loops)

    # ---------------- 形象 ----------------
    def _apply_style(self, style: PetStyle):
        self._stop_walk()
        self._stop_throw()
        self._anim_timer.stop()
        self._frames = []
        self._sticker_frames = []
        self._current_sticker_id = None

        if style.is_sticker():
            lib = sprites.PackLibrary(style)
            if lib.is_valid:
                self._style = style
                self._pack = lib
                self._sticker_idle()
            else:
                self._style = PetStyle.Classic
                self._pack = None
                self._set_state(PetState.Idle)
        else:
            self._style = PetStyle.Classic
            self._pack = None
            self._set_state(PetState.Idle)
        UserSettings.set_saved_style(self._style)

    # ---------------- 自主行为 ----------------
    def _schedule_behavior(self):
        self._behavior_timer.stop()
        delay = random.uniform(7, 15)
        self._behavior_timer.setInterval(int(delay * 1000))
        self._behavior_timer.setSingleShot(True)
        self._behavior_timer.start()

    def _on_behavior_tick(self):
        self._perform_random_behavior()
        self._schedule_behavior()

    def _perform_random_behavior(self):
        if not self._random_behavior or self._throwing or self._follow_enabled or self._popup_open:
            return
        idle = self._reminder_center._monitor.idle_seconds()
        if idle >= 30 * 60:
            self._was_away = True
            return
        if self._was_away:
            self._was_away = False
            self._last_interaction = datetime.now()
            if self._style.is_sticker() and self._current_sticker_id is not None:
                st = self._pack.random_sticker_any_of(["love", "happy"])
                if st is not None:
                    self._play_sticker(st, 2)
                    self.say("你回来啦！我好想你呀～")
                    return

        if (datetime.now() - self._last_interaction).total_seconds() >= 30 * 60 and \
                self._mood == Mood.Normal:
            self._mood = Mood.Sad

        if self._style.is_sticker():
            if self._current_sticker_id is not None:
                r = random.randint(0, 9)
                if r <= 2:
                    self._start_walk()
                elif r <= 6:
                    self._sticker_idle()
            return

        if self._state != PetState.Idle:
            return
        r = random.randint(0, 9)
        if r <= 3:
            self._start_walk()
        elif r == 4:
            self._play_once(PetState.Waving)
        elif r == 5:
            self._play_once(PetState.Jumping)
        elif r == 6:
            self._play_once(PetState.Waiting)
        elif r == 7:
            self._play_once(PetState.Review)
        elif r == 8:
            self._play_once(PetState.Running)

    def _start_walk(self):
        self._stop_walk()
        self._walk_direction = random.choice([-1, 1])
        if self._style.is_sticker():
            self._run_sticker()
        else:
            self._set_state(PetState.RunningRight if self._walk_direction > 0
                            else PetState.RunningLeft)
        deadline = datetime.now().timestamp() + random.uniform(2, 4)
        self._walk_timer = QTimer(self)
        self._walk_timer.timeout.connect(
            lambda: self._walk_tick(deadline))
        self._walk_timer.start(1000 // 60)

    def _walk_tick(self, deadline: float):
        if self._popup_open:
            return
        area = self._working_area()
        c = UserSettings.conditions()
        speed = c["walk_speed"]
        left = self.x() + self._walk_direction * speed
        if left < area.left():
            left = area.left()
            self._walk_direction = 1
            if not self._style.is_sticker():
                self._set_state(PetState.RunningRight)
            self._flip = False
        elif left + PET_WIDTH > area.right():
            left = area.right() - PET_WIDTH
            self._walk_direction = -1
            if not self._style.is_sticker():
                self._set_state(PetState.RunningLeft)
            self._flip = True
        self.move(int(left), self.y())
        if datetime.now().timestamp() >= deadline:
            self._stop_walk()
            if not self._style.is_sticker():
                self._set_state(PetState.Idle)
            else:
                self._sticker_idle()

    def _stop_walk(self):
        if self._walk_timer is not None:
            self._walk_timer.stop()
            self._walk_timer = None

    def _walk_to(self, target_x: int, completion):
        self._stop_walk()
        if abs(target_x - self.x()) < 8:
            completion()
            return
        self._walk_direction = 1 if target_x > self.x() else -1
        if self._style.is_sticker():
            self._run_sticker()
        else:
            self._set_state(PetState.RunningRight if self._walk_direction > 0
                            else PetState.RunningLeft)
        self._walk_timer = QTimer(self)
        self._walk_timer.timeout.connect(
            lambda: self._walk_to_tick(target_x, completion))
        self._walk_timer.start(1000 // 60)

    def _walk_to_tick(self, target_x: int, completion):
        if self._popup_open:
            return
        speed = 2.2
        left = self.x() + self._walk_direction * speed
        arrived = (self._walk_direction > 0 and left >= target_x) or \
                  (self._walk_direction < 0 and left <= target_x)
        if arrived:
            left = target_x
        self.move(int(left), self.y())
        if arrived:
            self._stop_walk()
            completion()

    # ---------------- 鼠标拖拽 / 抛掷 ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragged = False
            self._drag_samples.clear()
            self._last_mouse = event.globalPosition().toPoint()
            self._drag_target = self.pos()  # 以当前窗口位置为位移累计基准
            if not self._drag_move_timer.isActive():
                self._drag_move_timer.start(1000 // 60)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._dragged = True
            cur = event.globalPosition().toPoint()
            dx = cur.x() - self._last_mouse.x()
            dy = cur.y() - self._last_mouse.y()
            # 仅累计目标位置，真实移动交由 _apply_drag_move（约 60fps 合并），
            # 避免每个鼠标移动事件都触发分层窗口的 UpdateLayeredWindow。
            self._drag_target += QPoint(dx, dy)
            self._drag_samples.append((datetime.now().timestamp(), dx, dy))
            if len(self._drag_samples) > 8:
                self._drag_samples.pop(0)
            self._handle_drag(dx)
            self._last_mouse = cur
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._dragged:
                self._apply_drag_move()  # 应用最后一次累计位置
                self._handle_drag_end(self._release_velocity())
            else:
                self._handle_click()
            self._dragged = False
            self._drag_samples.clear()
            self._drag_move_timer.stop()
        super().mouseReleaseEvent(event)

    def _handle_drag(self, dx: float):
        """拖拽时让宠物朝拖动方向奔跑（优化 2：贴纸/合体形象也能跑）。"""
        self._stop_walk()
        self._stop_throw()
        if dx >= 0:
            self._flip = False
            target = PetState.RunningRight
        else:
            self._flip = True
            target = PetState.RunningLeft
        if self._style.is_sticker():
            # 合体/单角色贴纸：用奔跑感贴纸循环，画面随窗口一起移动，
            # 一二布布（duo）两张角色在同一帧内自然同步奔跑。
            if self._current_sticker_id is None or self._sticker_loops < 1000:
                self._run_sticker()
        else:
            if self._state != target:
                self._set_state(target)

    def _apply_drag_move(self):
        """以约 60fps 合并执行拖拽位移，并把坐标夹取在工作区内。"""
        if not self._dragged:
            return
        area = self._working_area()
        x = max(area.left(),
                min(area.right() - PET_WIDTH, self._drag_target.x()))
        y = max(area.top(),
                min(area.bottom() - PET_HEIGHT, self._drag_target.y()))
        if x != self.x() or y != self.y():
            self.move(x, y)

    def _release_velocity(self):
        now = datetime.now().timestamp()
        recent = [s for s in self._drag_samples if now - s[0] < 0.12]
        if len(recent) < 2:
            return (0.0, 0.0)
        first = recent[0]
        dt = now - first[0]
        if dt < 0.005:
            return (0.0, 0.0)
        dx = sum(s[1] for s in recent)
        dy = sum(s[2] for s in recent)
        return (dx / dt, dy / dt)

    def _handle_drag_end(self, velocity):
        vx, vy = velocity
        # 保护：丢弃非有限值，并把抛掷速度限制在合理上限，避免极端物理数值
        if not (math.isfinite(vx) and math.isfinite(vy)):
            vx = vy = 0.0
        MAX_THROW_SPEED = 6000.0
        speed = math.hypot(vx, vy)
        if speed > MAX_THROW_SPEED:
            scale = MAX_THROW_SPEED / speed
            vx *= scale
            vy *= scale
            speed *= scale
        if speed > THROW_SPEED_THRESHOLD:
            self._start_throw(vx, vy)
        elif self._style.is_sticker():
            self._last_interaction = datetime.now()
            st = self._pack.random_sticker_any_of(["happy", "love"])
            if st is not None:
                self._play_sticker(st, 1)
        else:
            self._last_interaction = datetime.now()
            self._set_state(PetState.Jumping, 1)

    def _handle_click(self):
        self._last_interaction = datetime.now()
        if self._mood == Mood.Angry:
            if self._style.is_sticker():
                st = self._pack.random_sticker_any_of(["angry"])
                if st:
                    self._play_sticker(st, 1)
            else:
                self._play_once(PetState.Failed)
            self.say("哼！还在生气呢！")
        else:
            self._mood = Mood.Happy
            self.say("你终于来陪我啦！")
            if self._style.is_sticker():
                st = self._pack.random_sticker_any_of(["happy", "love"])
                if st:
                    self._play_sticker(st, 1)
            else:
                self._play_once(PetState.Waving)

    # ---------------- 抛掷物理 ----------------
    def _start_throw(self, vx: float, vy: float):
        self._stop_walk()
        if not self._style.is_sticker():
            self._anim_timer.stop()
        self._throwing = True
        self._throw_vx = vx
        self._throw_vy = vy
        self._max_impact = 0.0
        self._physics_timer.stop()
        self._physics_timer.start(1000 // 60)

    def _step_physics(self):
        if self._popup_open:
            return
        dt = 1.0 / 60.0
        self._throw_vy += GRAVITY * dt
        left = self.x() + self._throw_vx * dt
        top = self.y() + self._throw_vy * dt
        # 保护：若出现非有限值，立即终止抛掷，避免向系统传入非法窗口坐标
        if not (math.isfinite(left) and math.isfinite(top)
                and math.isfinite(self._throw_vx) and math.isfinite(self._throw_vy)):
            self._finish_throw()
            return
        area = self._working_area()
        floor = area.bottom() - PET_HEIGHT
        landed = False

        if left < area.left():
            left = area.left()
            self._throw_vx = abs(self._throw_vx) * WALL_BOUNCE
        elif left + PET_WIDTH > area.right():
            left = area.right() - PET_WIDTH
            self._throw_vx = -abs(self._throw_vx) * WALL_BOUNCE
        if top < area.top():
            top = area.top()
            self._throw_vy = abs(self._throw_vy) * WALL_BOUNCE
        if top >= floor:
            top = floor
            impact = abs(self._throw_vy)
            self._max_impact = max(self._max_impact, impact)
            self._throw_vy = impact * FLOOR_BOUNCE
            self._throw_vx *= 0.8
            if self._throw_vy < 220 and abs(self._throw_vx) < 60:
                landed = True

        # 再次夹取，确保落在工作区内，杜绝任何越界坐标传入 SetWindowPos
        left = max(area.left(), min(area.right() - PET_WIDTH, int(left)))
        top = max(area.top(), min(area.bottom() - PET_HEIGHT, int(top)))
        self.move(left, top)
        if not self._style.is_sticker():
            frames = self._sheet.frames_for(PetState.Jumping)
            if len(frames) >= 5:
                idx = 1 if self._throw_vy < -80 else 3 if self._throw_vy > 80 else 2
                self._show_pixmap(self._pixmap_for(frames[idx], self._flip))
        if landed:
            self._finish_throw()

    def _finish_throw(self):
        self._stop_throw()
        if self._max_impact > 1600:
            self._mood = Mood.Angry
            self.say("请轻拿轻放！")
            if self._style.is_sticker():
                st = self._pack.random_sticker_any_of(["angry", "sad"])
                if st:
                    self._play_sticker(st, 2)
            else:
                self._set_state(PetState.Failed, 1)
        elif self._style.is_sticker():
            st = self._pack.random_sticker_any_of(["happy"])
            if st:
                self._play_sticker(st, 1)
        else:
            self._set_state(PetState.Jumping, 1)

    def _stop_throw(self):
        self._physics_timer.stop()
        self._throwing = False

    # ---------------- 优化 1：鼠标跟随奔跑 ----------------
    def set_follow_enabled(self, enabled: bool):
        self._follow_enabled = enabled
        UserSettings.set_mouse_follow(enabled)
        if enabled:
            self._stop_walk()
            self._follow_timer.start(1000 // 30)
        else:
            self._follow_timer.stop()
            if not self._style.is_sticker():
                self._set_state(PetState.Idle)
            else:
                self._sticker_idle()

    def _stop_follow(self):
        if self._follow_enabled:
            self._follow_timer.stop()
            if not self._style.is_sticker():
                self._set_state(PetState.Idle)
            else:
                self._sticker_idle()
            self._follow_timer.start(1000 // 30)

    def _follow_step(self):
        if not self._follow_enabled or self._throwing or self._dragged or self._popup_open:
            return
        c = UserSettings.conditions()
        target = QCursor.pos()
        dx = target.x() - (self.x() + PET_WIDTH / 2)
        dy = target.y() - (self.y() + PET_HEIGHT / 2)
        dist = math.hypot(dx, dy)
        speed = c["follow_speed"]
        if dist < 6:
            # 已贴近且鼠标静止：回到待机
            if self._state not in (PetState.Idle,) or \
                    (self._style.is_sticker() and self._current_sticker_id is not None
                     and self._sticker_loops >= 1000):
                if not self._style.is_sticker():
                    self._set_state(PetState.Idle)
                else:
                    self._sticker_idle()
            return
        step = min(speed, dist)
        ux = dx / dist if dist else 0
        uy = dy / dist if dist else 0
        area = self._working_area()
        nx = max(area.left(), min(area.right() - PET_WIDTH, self.x() + ux * step))
        ny = max(area.top(), min(area.bottom() - PET_HEIGHT, self.y() + uy * step))
        self.move(int(nx), int(ny))
        # 奔跑动画：根据水平方向
        if dx >= 0:
            self._flip = False
            if not self._style.is_sticker() and self._state != PetState.RunningRight:
                self._set_state(PetState.RunningRight)
            elif self._style.is_sticker() and \
                    (self._current_sticker_id is None or self._sticker_loops < 1000):
                self._run_sticker()
        else:
            self._flip = True
            if not self._style.is_sticker() and self._state != PetState.RunningLeft:
                self._set_state(PetState.RunningLeft)
            elif self._style.is_sticker() and \
                    (self._current_sticker_id is None or self._sticker_loops < 1000):
                self._run_sticker()

    # ---------------- 心情 / 提醒回调 ----------------
    @property
    def _current_mood(self) -> Mood:
        age = (datetime.now() - self._mood_set_at).total_seconds()
        if self._mood == Mood.Angry and age > 180 or \
                self._mood == Mood.Happy and age > 300 or \
                self._mood == Mood.Love and age > 600:
            self._mood = Mood.Normal
        return self._mood

    def _set_mood(self, m: Mood):
        self._mood = m
        self._mood_set_at = datetime.now()

    def say(self, text: str, duration: float = 4.0):
        self._bubble.say(text, duration)

    def heat_changed(self, level: float):
        self._heat = max(0.0, min(1.0, level))
        if self._heat <= 0.001:
            self._hide_heat()
        else:
            # 重新叠加到当前帧
            if self._style.is_sticker() and self._sticker_frames:
                film = self._sticker_frames[
                    (self._frame_index - 1) % len(self._sticker_frames)]
            elif self._frames:
                film = self._frames[(self._frame_index - 1) % len(self._frames)]
            else:
                return
            self._update_heat_overlay(self._pixmap_for(film, self._flip))

    def sleepy_changed(self, sleepy: bool):
        self._sleepy = sleepy

    def reminder_fired(self, kind, message):
        if self._throwing:
            return
        self._stop_walk()
        self.say(message, 6)
        if self._style.is_sticker():
            self._handle_sticker_reminder(kind)
            return
        from .reminders import ReminderKind
        if kind == ReminderKind.Sedentary:
            area = self._working_area()
            self._walk_to(int(area.left() + (area.width() - PET_WIDTH) / 2),
                          lambda: self._set_state(PetState.Jumping, 3))
        elif kind == ReminderKind.Water:
            self._play_once(PetState.Waiting, 3)
        elif kind == ReminderKind.LateNight:
            self._play_once(PetState.Review, 3)
        elif kind == ReminderKind.Slacking:
            self._play_once(PetState.Review, 5)
        elif kind == ReminderKind.CpuHigh:
            self.heat_changed(max(self._heat, 0.9))
            self._play_once(PetState.Running, 3)
        elif kind == ReminderKind.MemoryPressure:
            self._play_once(PetState.Waiting, 3)
        elif kind == ReminderKind.BatteryLow:
            self._play_once(PetState.Failed, 2)
        elif kind == ReminderKind.BatteryFull:
            self._play_once(PetState.Waving, 2)
        elif kind == ReminderKind.DiskFull:
            self._play_once(PetState.Review, 3)
        elif kind == ReminderKind.MorningGreet:
            self._play_once(PetState.Waving, 2)
        elif kind == ReminderKind.LunchTime:
            self._play_once(PetState.Waiting, 2)
        elif kind == ReminderKind.AfternoonCoffee:
            self._play_once(PetState.Review, 2)
        elif kind == ReminderKind.FridayEvening:
            self._play_once(PetState.Jumping, 2)
        elif kind == ReminderKind.IdeOvertime:
            self._play_once(PetState.Jumping, 3)

    def _handle_sticker_reminder(self, kind):
        from .reminders import ReminderKind
        tag_map = {
            ReminderKind.Sedentary: (["exercise", "idle"], 3),
            ReminderKind.Slacking: (["exercise", "idle"], 3),
            ReminderKind.Water: (["eat", "idle"], 3),
            ReminderKind.LateNight: (["love", "sleep", "lazy"], 3),
            ReminderKind.CpuHigh: (["hot", "angry", "tired"], 3),
            ReminderKind.MemoryPressure: (["tired", "sad"], 3),
            ReminderKind.BatteryLow: (["eat", "sad"], 2),
            ReminderKind.BatteryFull: (["happy"], 2),
            ReminderKind.DiskFull: (["work", "tired"], 3),
            ReminderKind.MorningGreet: (["happy", "love"], 2),
            ReminderKind.LunchTime: (["eat", "happy"], 2),
            ReminderKind.AfternoonCoffee: (["tired", "lazy"], 2),
            ReminderKind.FridayEvening: (["happy", "exercise"], 3),
            ReminderKind.IdeOvertime: (["exercise", "tired"], 3),
        }
        if kind == ReminderKind.CpuHigh:
            self.heat_changed(max(self._heat, 0.9))
        tags, loops = tag_map.get(kind, (["idle"], 2))
        st = self._pack.random_sticker_any_of(tags)
        if st is not None:
            self._play_sticker(st, loops)

    # ---------------- 右键菜单 ----------------
    def contextMenuEvent(self, event):
        # 打开右键菜单期间，停止一切会“移动本窗口”的定时器，并标记 _popup_open。
        # 原因：本窗口是置顶无边框工具窗(Qt.Tool)，若在其弹出菜单仍打开时移动
        # owner 窗口（跟随/散步/抛掷定时器触发），Windows 的 TrackPopupMenu 与
        # SetWindowPos 交互会触发原生崩溃 0xC0000409。
        self._popup_open = True
        self._follow_timer.stop()
        self._stop_walk()
        self._stop_throw()

        # 菜单不挂到置顶工具窗上，作为独立顶层弹出菜单，规避 owner 样式导致的原生崩溃。
        menu = QMenu()
        style_menu = menu.addMenu("形象")
        for s in PetStyle.all():
            act = style_menu.addAction(s.display_name())
            act.setCheckable(True)
            act.setChecked(s == self._style)
            act.triggered.connect(
                lambda _checked, cap=s: self._apply_style(cap))

        if not self._style.is_sticker():
            state_menu = menu.addMenu("动作")
            for st in PetState.all():
                act = state_menu.addAction(st.display_name())
                act.setCheckable(True)
                act.setChecked(st == self._state)
                act.triggered.connect(
                    lambda _c, cap=st: (self._stop_walk(),
                                       self._set_state(cap)
                                       if cap in (PetState.Idle, PetState.RunningRight,
                                                  PetState.RunningLeft)
                                       else self._set_state(cap, 3)))

        rand_act = menu.addAction(
            "暂停随机行为" if self._random_behavior else "开启随机行为")
        rand_act.triggered.connect(
            lambda _: setattr(self, "_random_behavior", not self._random_behavior))

        follow_act = menu.addAction(
            "关闭鼠标跟随" if self._follow_enabled else "开启鼠标跟随")
        follow_act.triggered.connect(
            lambda _: self.set_follow_enabled(not self._follow_enabled))

        from .reminders import (ReminderKind, ReminderCenter)
        menu.addMenu(self._build_reminder_submenu(
            menu, "提醒设置", ReminderKind.health_cases()))
        menu.addMenu(self._build_reminder_submenu(
            menu, "系统哨兵", ReminderKind.system_cases()))
        menu.addMenu(self._build_reminder_submenu(
            menu, "陪伴模式", ReminderKind.companion_cases()))

        settings_act = menu.addAction("自定义提醒条件…")
        settings_act.triggered.connect(self._open_settings)

        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier:
            test_menu = menu.addMenu("测试提醒")
            for kind in ReminderKind.all():
                a = test_menu.addAction("触发" + kind.title())
                a.triggered.connect(
                    lambda _c, k=kind: self._reminder_center.fire(k))

        menu.addSeparator()
        quit_act = menu.addAction("退出")
        quit_act.triggered.connect(QApplication.quit)
        menu.exec(event.globalPos())
        menu.deleteLater()

        # 菜单关闭后，恢复跟随（若原先开启）。
        self._popup_open = False
        if self._follow_enabled:
            self._follow_timer.start(1000 // 30)

    def _build_reminder_submenu(self, parent, title, kinds):
        from .reminders import ReminderKind
        sub = QMenu(title, parent)
        for kind in kinds:
            act = sub.addAction(kind.title())
            act.setCheckable(True)
            act.setChecked(self._reminder_center.is_enabled(kind))
            act.triggered.connect(
                lambda _c, k=kind: self._reminder_center.set_enabled(
                    k, not self._reminder_center.is_enabled(k)))
        return sub

    def _open_settings(self):
        # 延迟导入，避免循环依赖
        from .settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.exec()
