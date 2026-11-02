"""系统托盘（右下角通知区）。

宠物主窗口是 Qt.Tool（无边框置顶工具窗），默认不出现在任务栏，仅靠右键菜单操作，
不够直观且容易“找不到退出入口”。本模块提供一个常驻托盘图标：

  - 左键单击：显示 / 隐藏宠物（隐藏后仍有托盘可恢复，不会“丢宠物”）。
  - 右键单击：弹出与宠物右键菜单完全一致的应用菜单（形象 / 跟随 / 自启动 /
    提醒子菜单 / 自定义提醒条件 / 退出）。
  - 每次弹出菜单都重建，保证勾选状态（跟随、自启动、形象等）实时反映最新值。
  - 打开菜单期间复用 PetWindow 的 _popup_open 守卫，避免移动 owner 工具窗触发原生崩溃。
"""
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtWidgets import QSystemTrayIcon

from . import pet_window
from .states import PetState


def _icon_from_sheet(sheet) -> QIcon:
    """用经典待机首帧生成托盘图标（宠物的标志性形象）。"""
    frames = sheet.frames_for(PetState.Idle) if sheet is not None else []
    if not frames:
        return QIcon()
    pm = pet_window.pil_to_pixmap(frames[0])
    pm = pm.scaled(
        32, 32,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation)
    return QIcon(pm)


class SystemTray:
    def __init__(self, pet, sheet):
        self._pet = pet
        self._icon = QSystemTrayIcon()
        self._icon.setIcon(_icon_from_sheet(sheet))
        self._icon.setToolTip("一二布布桌面宠物\n左键：显示/隐藏　右键：菜单")
        self._icon.activated.connect(self._on_activated)
        self._icon.show()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # 左键：切换宠物可见性（隐藏后仍有托盘可恢复）
            if self._pet.isVisible():
                self._pet.hide()
            else:
                self._pet.show()
        elif reason in (QSystemTrayIcon.ActivationReason.Context,
                        QSystemTrayIcon.ActivationReason.MiddleClick):
            self._show_menu()

    def _show_menu(self):
        # 复用与右键菜单一致的守卫，避免菜单打开期间移动 owner 工具窗触发原生崩溃。
        pet = self._pet
        pet._popup_open = True
        pet._follow_timer.stop()
        pet._stop_walk()
        pet._stop_throw()

        menu = pet._build_app_menu()
        menu.aboutToHide.connect(
            lambda: self._on_menu_hidden(menu))
        menu.exec(QCursor.pos())
        menu.deleteLater()

    def _on_menu_hidden(self, menu):
        pet = self._pet
        pet._popup_open = False
        if pet._follow_enabled:
            pet._follow_timer.start(1000 // 30)

    def hide(self):
        self._icon.hide()
