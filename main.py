"""入口：启动桌面宠物。

运行：python main.py  （建议使用项目自带的 .venv）
依赖：PyQt6, Pillow, psutil
"""
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from pet import sprites
from pet.activity import ActivityMonitor
from pet.config import UserSettings
from pet.pet_window import PetWindow
from pet.reminders import ReminderCenter
from pet.systemmon import SystemMonitor
from pet.tray import SystemTray


def main():
    # 早期安装崩溃诊断（捕获原生崩溃故障模块），便于排查 0xC0000409 等问题
    try:
        from pet.crash_report import install as install_crash_report
        install_crash_report()
    except Exception:
        pass

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

    # 系统托盘（右下角）：提供常驻入口与退出通道。无任务栏图标时尤为重要。
    # 仅在系统提供托盘时创建；无托盘环境（如部分无桌面会话）则退回仅右键菜单操作。
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = SystemTray(pet, sheet)
        # 托盘存在时，最后一个窗口关闭不应退出程序（标准托盘常驻模式），
        # 退出统一由菜单「退出」触发 QApplication.quit。
        app.setQuitOnLastWindowClosed(False)
        app.aboutToQuit.connect(tray.hide)

    # 提醒周期判定（每 30 秒）
    tick_timer = QTimer()
    tick_timer.setInterval(ReminderCenter.TICK_SECONDS * 1000)
    tick_timer.timeout.connect(center.tick)
    tick_timer.start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
