"""ALICE overlay GUI using PyQt5.

Reads commands from `gui_command.txt` and displays images or plays videos
from `assets/<charDir>/`.

This is a single clean implementation.
"""

import sys
import os
import random
import ctypes
from pathlib import Path

from PyQt5 import QtWidgets, QtGui, QtCore
import cv2
import numpy as np

# Windows-specific constants for click-through
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20

user32 = None
try:
    user32 = ctypes.windll.user32
except Exception:
    user32 = None

# Basic configuration
SCREEN_WIDTH = 360
SCREEN_HEIGHT = 360
ASSETS_DIR = Path(os.path.join(os.getcwd(), "assets"))


def get_char_dir() -> str:
    try:
        with open("config.txt", "r") as f:
            cd = f.read().strip()
            if cd == "virgil":
                cd = "VRGL"
            return cd
    except Exception:
        return "VRGL"


def read_command() -> str:
    try:
        with open("gui_command.txt", "r") as f:
            return f.read().strip()
    except Exception:
        return ""


class OverlayWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setWindowTitle("ALICE Overlay")
        self.resize(SCREEN_WIDTH, SCREEN_HEIGHT)

        self.label = QtWidgets.QLabel(self)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("background: transparent;")
        self.label.setGeometry(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)

        self._char_dir = get_char_dir()
        self._video_capture = None
        self._video_path = None
        self._video_timer = QtCore.QTimer()
        self._video_timer.timeout.connect(self._video_frame)
        # Start interactive (opaque) by default
        self._click_through = False
        self._last_command = ""
        self._apply_click_through()

        # Poll for commands
        self._poll_timer = QtCore.QTimer()
        self._poll_timer.timeout.connect(self._poll_command)
        # Poll a bit faster so state changes feel snappier (120ms)
        self._poll_timer.start(120)

        # Start opaque and interactive; on hover become translucent
        self._normal_opacity = 0.98
        self._hover_opacity = 0.35
        self.setWindowOpacity(self._normal_opacity)
        # Enable mouse tracking to get hover events even without pressing
        self.setMouseTracking(True)

        # System tray icon to hide/show/exit
        self._tray_icon = None
        try:
            icon_path = ASSETS_DIR / self._char_dir / "icon.png"
            if not icon_path.exists():
                icon_path = None
            self._tray_icon = QtWidgets.QSystemTrayIcon(QtGui.QIcon(str(icon_path)) if icon_path else self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon))
            menu = QtWidgets.QMenu()
            show_action = menu.addAction("Show Overlay")
            hide_action = menu.addAction("Hide Overlay")
            exit_action = menu.addAction("Exit")
            show_action.triggered.connect(self._on_tray_show)
            hide_action.triggered.connect(self._on_tray_hide)
            exit_action.triggered.connect(QtWidgets.QApplication.quit)
            self._tray_icon.setContextMenu(menu)
            self._tray_icon.activated.connect(self._on_tray_activated)
            self._tray_icon.setToolTip("ALICE Overlay")
            self._tray_icon.show()
        except Exception:
            self._tray_icon = None

    def _apply_click_through(self) -> None:
        if user32 is None:
            return
        hwnd = int(self.winId())
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        # Ensure layered flag remains set (needed for translucency)
        if self._click_through:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (ex | WS_EX_LAYERED | WS_EX_TRANSPARENT))
            # Tell Qt to ignore mouse events as well
            try:
                self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            except Exception:
                pass
        else:
            # Remove transparent flag but keep layered for opacity
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (ex & ~WS_EX_TRANSPARENT) | WS_EX_LAYERED)
            try:
                self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
            except Exception:
                pass
        # Force Windows to reapply the window styles
        try:
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        except Exception:
            pass

    def toggle_click_through(self) -> None:
        self._click_through = not self._click_through
        self._apply_click_through()

    def _on_tray_show(self):
        self.show()
        self.raise_()

    def _on_tray_hide(self):
        self.hide()

    def _on_tray_activated(self, reason):
        # double-click toggles visibility
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()

    def _poll_command(self) -> None:
        cmd = read_command()
        if not cmd:
            return
        # Avoid re-applying the same command repeatedly (prevents video restarting)
        if cmd == self._last_command:
            return
        video_folder = ASSETS_DIR / self._char_dir / "video"
        mapping = {
            "idle": ["Idle Sway.mp4", "idle.mp4"],
            "listening": ["bored.mp4", "listening.mp4"],
            "speaking": ["talking.mp4", "talk.mp4"],
            "working": ["searching.mp4", "looking around.mp4"],
            "angry": ["Sassy.mp4"],
            "blink": ["Couch.mp4"],
            "hello": ["hello.mp4"],
        }
        if cmd == "exit":
            QtWidgets.QApplication.quit()
            return
        if cmd == "math":
            self.set_image_state("math")
            return

        candidates = mapping.get(cmd)
        if candidates:
            if not self.show_video_choice(video_folder, candidates):
                self.set_image_state(cmd if cmd in mapping.keys() else "idle")
        # remember the last processed command so repeated polls don't redo work
        self._last_command = cmd

    def show_video_choice(self, folder: Path, candidates: list) -> bool:
        if not folder.exists():
            return False
        for c in candidates:
            p = folder / c
            if p.exists():
                self.set_video(str(p))
                return True
        for p in folder.glob("*.mp4"):
            self.set_video(str(p))
            return True
        return False

    def set_image_state(self, state_name: str) -> None:
        folder = ASSETS_DIR / self._char_dir / state_name
        if not folder.exists():
            self.label.clear()
            return
        imgs = list(folder.glob("*.png")) + list(folder.glob("*.jpg")) + list(folder.glob("*.jpeg"))
        if not imgs:
            self.label.clear()
            return
        chosen = random.choice(imgs)
        pix = QtGui.QPixmap(str(chosen)).scaled(self.label.width(), self.label.height(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.label.setPixmap(pix)
        self._stop_video()

    def set_video(self, path: str) -> None:
        # If this path is already playing, do nothing to avoid restarting
        try:
            if self._video_path == path and self._video_capture is not None and getattr(self._video_capture, 'isOpened', lambda: True)():
                # already playing this video
                return
        except Exception:
            pass
        try:
            if self._video_capture:
                self._video_capture.release()
                self._video_capture = None
        except Exception:
            pass
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print(f"Failed to open video {path}")
            return
        self._video_capture = cap
        self._video_path = path
        fps = cap.get(cv2.CAP_PROP_FPS)
        try:
            fps = float(fps)
        except Exception:
            fps = 0.0
        if not fps or fps < 1.0:
            interval = 30
        else:
            interval = int(1000 / fps)
        # Allow slightly faster frame intervals for snappier animation, but keep safe bounds
        interval = max(12, min(150, interval))
        self._video_timer.start(interval)
        print(f"[GUI] Started video {path} with interval={interval}ms")

    def _video_frame(self) -> None:
        if not self._video_capture:
            return
        grabbed = self._video_capture.grab()
        if not grabbed:
            pos = int(self._video_capture.get(cv2.CAP_PROP_POS_FRAMES) or 0)
            print(f"[GUI] grab failed at pos={pos}, attempting restart")
            try:
                self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                grabbed = self._video_capture.grab()
            except Exception:
                self._video_timer.stop()
                return
        ret, frame = self._video_capture.retrieve()
        if not ret:
            try:
                self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._video_capture.read()
                if not ret:
                    self._video_timer.stop()
                    return
            except Exception:
                self._video_timer.stop()
                return
        try:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = np.ascontiguousarray(frame)
            h, w, ch = frame.shape
            bytes_per_line = frame.strides[0]
            qimg = QtGui.QImage(frame.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888).copy()
            pix = QtGui.QPixmap.fromImage(qimg).scaled(self.label.width(), self.label.height(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.label.setPixmap(pix)
        except Exception as e:
            print(f"[GUI] frame render error: {e}")

    def _stop_video(self) -> None:
        if self._video_timer.isActive():
            self._video_timer.stop()
        try:
            if self._video_capture:
                self._video_capture.release()
        except Exception:
            pass
        self._video_capture = None

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key_T:
            self.toggle_click_through()
        elif event.key() == QtCore.Qt.Key_Escape:
            QtWidgets.QApplication.quit()

    def enterEvent(self, event: QtGui.QEnterEvent) -> None:
        # user hovered over overlay: make it translucent (but keep interactivity)
        try:
            self.setWindowOpacity(self._hover_opacity)
        except Exception:
            pass
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        # user moved the mouse away: restore full opacity
        try:
            self.setWindowOpacity(self._normal_opacity)
        except Exception:
            pass
        super().leaveEvent(event)


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    w = OverlayWindow()
    screen = app.primaryScreen().availableGeometry()
    margin = 20
    x = max(0, screen.width() - w.width() - margin)
    y = max(0, screen.height() - w.height() - 120)
    w.move(int(x), int(y))
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
