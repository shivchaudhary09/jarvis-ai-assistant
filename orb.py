"""Siri-style orange overlay used by the JARVIS wake-word session."""

import math
import os
import subprocess
import sys
import threading

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QRadialGradient
from PyQt6.QtWidgets import QApplication, QWidget


class OrangeOrb(QWidget):
    """A small, borderless, always-on-top animated assistant overlay."""

    def __init__(self):
        super().__init__()
        self.state = "listening"
        self.phase = 0.0
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(260, 150)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2, screen.top() + 70)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(30)
        self.hide()

    def animate(self):
        self.phase = (self.phase + 0.12) % math.tau
        self.update()

    def set_state(self, state):
        self.state = state if state in {"listening", "thinking", "speaking"} else "listening"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        cx, cy = self.width() / 2, self.height() / 2
        strength = {"listening": 1.0, "thinking": 0.72, "speaking": 1.35}[self.state]
        pulse = (1.0 + 0.12 * math.sin(self.phase * (1.4 if self.state == "speaking" else 1.0))) * strength

        for layer in range(18, 0, -1):
            radius = (24 + layer * 4.5) * pulse
            alpha = int(5 + (18 - layer) * 4)
            painter.setBrush(QColor(255, 112, 20, alpha))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))

        core = 29 * pulse
        gradient = QRadialGradient(cx, cy, core)
        gradient.setColorAt(0.0, QColor(255, 244, 214, 255))
        gradient.setColorAt(0.35, QColor(255, 184, 74, 255))
        gradient.setColorAt(1.0, QColor(242, 75, 7, 220))
        painter.setBrush(gradient)
        painter.drawEllipse(int(cx - core), int(cy - core), int(core * 2), int(core * 2))

        bar_height = {"listening": 10, "thinking": 6, "speaking": 15}[self.state]
        painter.setBrush(QColor(255, 205, 125, 220))
        for index in range(3):
            height = bar_height * (0.7 + 0.3 * abs(math.sin(self.phase + index)))
            painter.drawRoundedRect(int(cx - 18 + index * 18), int(cy + 46 - height), 8, int(height), 4, 4)


class _CommandBridge(QObject):
    command = pyqtSignal(str)


def run_overlay():
    app = QApplication(sys.argv)

    # App ko background-utility bana do — Dock icon nahi aayega,
    # aur Space/Desktop switch nahi hoga jab orb show ho.
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except ImportError:
        pass

    bridge = _CommandBridge()
    orb = OrangeOrb()

    def handle(command):
        if command == "show":
            orb.show()
            orb.raise_()
            orb.update()
        elif command == "hide":
            orb.hide()
        elif command.startswith("state:"):
            orb.set_state(command.split(":", 1)[1])
        elif command == "quit":
            orb.close()
            app.quit()

    bridge.command.connect(handle)

    def read_commands():
        for line in sys.stdin:
            bridge.command.emit(line.strip())

    threading.Thread(target=read_commands, daemon=True).start()
    app.exec()


class OrbController:
    """Non-blocking controller for the separate Qt overlay process."""

    def __init__(self):
        self.closed = False
        self.process = self._start_process()

    def _start_process(self):
        environment = os.environ.copy()
        environment.setdefault("QT_MAC_WANTS_LAYER", "1")
        # Keep the overlay's diagnostics visible. If Qt/macOS rejects the
        # window, the parent process must show the actual reason in Terminal.
        return subprocess.Popen([sys.executable, __file__, "--server"], stdin=subprocess.PIPE,
                                stdout=sys.stdout, stderr=sys.stderr, env=environment,
                                text=True, bufsize=1)

    def _send(self, command):
        process_status = self.process.poll()
        if process_status is not None:
            if not self.closed:
                print(f"[Orange UI process stopped with code {process_status}; restarting]")
                self.process = self._start_process()
            else:
                return
        if self.process.poll() is None and self.process.stdin:
            try:
                self.process.stdin.write(command + "\n")
                self.process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass

    def show(self): self._send("show")
    def hide(self): self._send("hide")
    def set_state(self, state): self._send(f"state:{state}")

    def close(self):
        if self.closed:
            return
        self.closed = True
        self._send("hide")
        self._send("quit")
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()


if __name__ == "__main__" and "--server" in sys.argv:
    run_overlay()
