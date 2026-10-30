"""头顶气泡：独立置顶的透明无交互窗口，圆角带小尾巴，跟随宠物位置。"""
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath
from PyQt6.QtWidgets import QWidget, QLabel


class SpeechBubble(QWidget):
    MAX_TEXT_WIDTH = 220
    PADDING = 10
    TAIL_HEIGHT = 8
    OVERLAP_INTO_PET = 88  # 气泡底部压住宠物顶部，使尾巴落在头部附近

    def __init__(self, parent: QWidget):
        super().__init__(parent, Qt.WindowType.Tool |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        # 气泡不拦截鼠标，点击穿透到下层宠物
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._label = QLabel(self)
        self._label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            "color: #262626; font-size: 12px; font-weight: 500; "
            "font-family: 'Microsoft YaHei UI', 'PingFang SC', 'Segoe UI';"
        )
        self._label.setMinimumWidth(0)
        self._parent = parent
        self._hide_timer = QTimer(self)
        self._hide_timer.timeout.connect(self.hide)
        self._width = 0
        self._height = 0

    def sync_position(self):
        """由宠物窗口在自身移动后调用，使气泡跟随。"""
        self._sync_position()

    def say(self, text: str, duration_seconds: float = 4.0):
        self._label.setText(text)
        self._label.setMaximumWidth(self.MAX_TEXT_WIDTH)
        self._label.adjustSize()
        tw = min(self._label.sizeHint().width(), self.MAX_TEXT_WIDTH)
        th = self._label.sizeHint().height()
        w = max(tw + self.PADDING * 2, 40)
        h = th + self.PADDING * 2 + self.TAIL_HEIGHT
        self._width = w
        self._height = h
        self.setFixedSize(int(w), int(h))
        self._label.setGeometry(
            self.PADDING, self.TAIL_HEIGHT + self.PADDING,
            int(w - self.PADDING * 2), int(th))
        self._sync_position(w, h)
        self.show()
        self.raise_()
        self._hide_timer.stop()
        self._hide_timer.setInterval(int(duration_seconds * 1000))
        self._hide_timer.start()

    def hide(self):
        self._hide_timer.stop()
        super().hide()

    def _sync_position(self, width=None, height=None):
        w = width if width is not None else self._width
        h = height if height is not None else self._height
        if w <= 0 or h <= 0:
            return
        pw = self._parent.width()
        px = self._parent.x()
        py = self._parent.y()
        self.move(int(px + (pw - w) / 2), int(py + self.OVERLAP_INTO_PET - h))

    def paintEvent(self, event):
        if self._width < 4 or self._height < 4:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = 10.0
        tail_w = 14.0
        min_x = 1.0
        max_x = self._width - 1
        min_y = self.TAIL_HEIGHT + 1
        max_y = self._height - 1
        mid_x = self._width / 2

        path = QPainterPath()
        path.moveTo(mid_x - tail_w / 2, min_y)
        path.lineTo(mid_x, 1)
        path.lineTo(mid_x + tail_w / 2, min_y)
        path.lineTo(max_x - r, min_y)
        path.arcTo(max_x - r, min_y, r, r, 0, 90)
        path.lineTo(max_x, max_y - r)
        path.arcTo(max_x - r, max_y - r, r, r, 0, 90)
        path.lineTo(min_x + r, max_y)
        path.arcTo(min_x, max_y - r, r, r, 0, 90)
        path.lineTo(min_x, min_y + r)
        path.arcTo(min_x, min_y, r, r, 0, 90)
        path.closeSubpath()

        painter.setPen(QPen(QColor(0xB8, 0xB8, 0xB8), 1))
        painter.setBrush(QBrush(QColor(0xF5, 0xFF, 0xFF, 0xFF)))
        painter.drawPath(path)
        painter.end()
