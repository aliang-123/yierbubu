"""自定义提醒条件设置对话框（优化功能 3 的可视化入口）。

把 config.Conditions 里的全部触发条件（时长 / 时段 / 阈值 / 速度）以及
14 种提醒开关暴露给用户编辑，保存后提醒中心下次 tick 即生效。
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, QSpinBox,
    QDoubleSpinBox, QCheckBox, QDialogButtonBox, QLabel, QGroupBox,
    QApplication, QScrollArea,
)

from .config import UserSettings, Conditions
from .reminders import ReminderKind


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("一二布布 · 自定义提醒条件")
        self.setMinimumWidth(420)
        # 限高：对话框内容较多（约 28 项条件 + 分组），在小屏上会超出屏幕，
        # 导致底部「确定/取消」按钮或最后几项点不到。把窗口高度夹取到可视区内，
        # 超高时由标签页内的 QScrollArea 滚动而非裁切。
        screen = QApplication.primaryScreen()
        if screen is not None:
            self.setMaximumHeight(max(320, screen.availableGeometry().height() - 40))
        self._c = UserSettings.conditions()
        self._widgets = {}
        self._rem_toggles = {}

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(self._build_conditions_tab(), "提醒条件")
        tabs.addTab(self._build_toggles_tab(), "提醒开关")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            self._restore)
        layout.addWidget(buttons)

    def showEvent(self, event):
        super().showEvent(event)
        # 确保对话框完整落在屏幕可视区内：宠物常驻屏幕底部，对话框默认居中会偏下，
        # 叠加限高后若仍超高/偏出，这里把整体夹回可视区，保证「确定/取消」始终可达。
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            r = self.geometry()
            if r.bottom() > geo.bottom():
                r.moveBottom(geo.bottom())
            if r.top() < geo.top():
                r.moveTop(geo.top())
            if r.right() > geo.right():
                r.moveRight(geo.right())
            if r.left() < geo.left():
                r.moveLeft(geo.left())
            self.setGeometry(r)

    # ---------------- 条件页 ----------------
    def _build_conditions_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        form = QFormLayout(content)
        c = self._c

        # 健康类
        self._group(form, "健康类", [
            ("sedentary_minutes", "久坐提醒阈值（分钟）", "int", 1, 600),
            ("water_minutes", "喝水提醒间隔（分钟）", "int", 1, 600),
            ("slack_minutes", "摸鱼判定阈值（分钟）", "int", 1, 600),
            ("slack_repeat_minutes", "摸鱼提醒重复（分钟）", "int", 1, 600),
            ("presence_idle_minutes", "离开判定（分钟，无操作）", "int", 1, 120),
        ])
        # 深夜关怀
        self._group(form, "深夜关怀", [
            ("late_night_start_hour", "开始小时 (0-23)", "int", 0, 23),
            ("late_night_end_hour", "结束小时 (0-23)", "int", 0, 23),
            ("late_care_interval_minutes", "最小重复间隔（分钟）", "int", 1, 600),
        ])
        # 系统哨兵
        self._group(form, "系统哨兵", [
            ("cpu_threshold", "CPU 红温阈值 (0-1)", "float2", 0.1, 1.0),
            ("cpu_ticks_needed", "连续超阈值次数", "int", 1, 30),
            ("cpu_repeat_minutes", "CPU 提醒重复（分钟）", "int", 1, 600),
            ("mem_warning", "内存警告 (%)", "int", 50, 100),
            ("mem_critical", "内存严重 (%)", "int", 50, 100),
            ("mem_repeat_minutes", "内存提醒重复（分钟）", "int", 1, 600),
            ("disk_free_threshold", "磁盘剩余阈值 (0-1)", "float2", 0.01, 0.9),
            ("disk_repeat_hours", "磁盘提醒重复（小时）", "int", 1, 240),
        ])
        # 陪伴时段
        self._group(form, "陪伴模式时段（起/止小时）", [
            ("morning_start_hour", "早晨问候-起", "int", 0, 23),
            ("morning_end_hour", "早晨问候-止", "int", 0, 23),
            ("lunch_start_hour", "午饭提醒-起", "int", 0, 23),
            ("lunch_end_hour", "午饭提醒-止", "int", 0, 23),
            ("afternoon_start_hour", "下午咖啡-起", "int", 0, 23),
            ("afternoon_end_hour", "下午咖啡-止", "int", 0, 23),
            ("friday_start_hour", "周五撒欢-起", "int", 0, 23),
            ("friday_end_hour", "周五撒欢-止", "int", 0, 23),
        ])
        # 其它
        self._group(form, "其它 / 手感", [
            ("ide_overtime_minutes", "编码久战阈值（分钟）", "int", 10, 600),
            ("global_gap_seconds", "提醒最小间隔（秒）", "int", 10, 600),
            ("walk_speed", "自主散步速度", "float2", 0.2, 8.0),
            ("follow_speed", "鼠标跟随速度", "float2", 0.5, 12.0),
        ])
        scroll.setWidget(content)
        return scroll

    def _group(self, form, title, fields):
        box = QGroupBox(title)
        gf = QFormLayout(box)
        for key, label, kind, lo, hi in fields:
            w = self._make_widget(kind, self._c[key], lo, hi)
            self._widgets[key] = (w, kind)
            gf.addRow(QLabel(label), w)
        form.addRow(box)

    def _make_widget(self, kind, value, lo, hi):
        if kind == "int":
            w = QSpinBox()
            w.setRange(int(lo), int(hi))
            w.setValue(int(value))
        else:  # float2
            w = QDoubleSpinBox()
            w.setRange(float(lo), float(hi))
            w.setDecimals(2)
            w.setSingleStep(0.05)
            w.setValue(float(value))
        return w

    # ---------------- 开关页 ----------------
    def _build_toggles_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        form = QFormLayout(content)
        for kind in ReminderKind.all():
            cb = QCheckBox(kind.title())
            cb.setChecked(UserSettings.reminder_enabled(kind))
            self._rem_toggles[kind] = cb
            form.addRow(cb)
        note = QLabel("关闭后该提醒不再触发；「自定义提醒条件」页可进一步调整触发阈值与时段。")
        note.setWordWrap(True)
        note.setStyleSheet("color: #666; font-size: 11px;")
        form.addRow(note)
        scroll.setWidget(content)
        return scroll

    # ---------------- 保存 ----------------
    def _accept(self):
        for key, (w, kind) in self._widgets.items():
            val = w.value()
            UserSettings.set_condition(key, val)
        for kind, cb in self._rem_toggles.items():
            UserSettings.set_reminder_enabled(kind, cb.isChecked())
        # 鼠标跟随开关同步保存（若需）
        self.accept()

    def _restore(self):
        UserSettings.reset_conditions()
        self._c = UserSettings.conditions()
        # 重建条件页
        tabs = self.findChild(QTabWidget)
        if tabs is not None:
            tabs.removeTab(0)
            tabs.insertTab(0, self._build_conditions_tab(), "提醒条件")
            tabs.setCurrentIndex(0)
