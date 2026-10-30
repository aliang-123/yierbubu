"""入口：启动桌面宠物。

运行：python main.py  （建议使用项目自带的 .venv）
依赖：PyQt6, Pillow, psutil
"""
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from pet import sprites
from pet.activity import ActivityMonitor
from pet.config import UserSettings
from pet.pet_window import PetWindow
from pet.reminders import ReminderCenter
from pet.systemmon import SystemMonitor


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("一二布布桌面宠物")

    sheet = sprites.SpriteSheet.load()
    if sheet is None:
        QMessageBox.critical(
            None, "无法加载精灵图集",
            "Assets/spritesheet.webp 缺失或解码失败。\n"
            "请确认 Assets 目录与程序在同一目录。")
        return 1

    monitor = ActivityMonitor()
    system = SystemMonitor()
    center = ReminderCenter(monitor, system)

    pet = PetWindow(sheet, center)
    center.delegate = pet
    center.start()
    pet.show()

    # 提醒周期判定（每 30 秒）
    tick_timer = QTimer()
    tick_timer.setInterval(ReminderCenter.TICK_SECONDS * 1000)
    tick_timer.timeout.connect(center.tick)
    tick_timer.start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
