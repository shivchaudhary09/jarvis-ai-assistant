"""Siri-style orange overlay used by the JARVIS wake-word session."""

import math
import os
import subprocess
import sys
import threading
from collections import deque

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QRadialGradient, QLinearGradient, QPen, QBrush, QFont, QFontMetrics
from PyQt6.QtWidgets import QApplication, QWidget


class SiriOrb(QWidget):
    """A premium Siri-style animated assistant overlay with voice waveform."""

    def __init__(self):
        super().__init__()
        self.state = "idle"  # idle, listening, thinking, speaking
        self.phase = 0.0
        self.waveform_data = deque(maxlen=64)
        self.target_waveform = deque([0.0] * 64, maxlen=64)
        self.waveform_phase = 0.0

        # Orb properties
        self.orb_radius = 48
        self.orb_pulse = 1.0
        self.orb_target_pulse = 1.0
        self.glow_radius = 0.0
        self.target_glow_radius = 0.0

        # Siri's distinctive luminous, multicolour palette.
        self.CYAN = QColor(72, 215, 255)
        self.BLUE = QColor(51, 102, 255)
        self.VIOLET = QColor(145, 91, 255)
        self.PINK = QColor(255, 83, 188)
        self.GLOW = QColor(103, 151, 255)

        # Window setup - frameless, always on top, translucent
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.NoDropShadowWindowHint |
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Size - larger to accommodate waveform
        self.setFixedSize(320, 210)

        # Position at top center like Siri
        self._position_at_top_center()

        # Animation timer (60fps)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)  # ~60fps

        self.hide()

    def _position_at_top_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.center().x() - self.width() // 2
        y = screen.top() + 32
        self.move(x, y)

    def animate(self):
        # Smooth phase progression
        self.phase += 0.08
        self.waveform_phase += 0.15

        # Smooth pulse interpolation
        self.orb_pulse += (self.orb_target_pulse - self.orb_pulse) * 0.15
        self.glow_radius += (self.target_glow_radius - self.glow_radius) * 0.12

        # Generate waveform based on state
        self._update_waveform()

        # Smooth waveform interpolation
        for i in range(len(self.waveform_data)):
            self.waveform_data[i] += (self.target_waveform[i] - self.waveform_data[i]) * 0.2

        self.update()

    def _update_waveform(self):
        """Generate waveform data based on current state."""
        if self.state == "listening":
            # Active listening - responsive waveform
            base_amplitude = 0.4 + 0.3 * math.sin(self.waveform_phase * 0.5)
            for i in range(64):
                # Multiple sine waves for organic feel
                wave = (
                    math.sin(self.waveform_phase + i * 0.3) * 0.5 +
                    math.sin(self.waveform_phase * 1.3 + i * 0.5) * 0.3 +
                    math.sin(self.waveform_phase * 0.7 + i * 0.2) * 0.2
                ) * base_amplitude
                # Envelope - stronger in middle
                envelope = 1.0 - abs(i - 31.5) / 31.5 * 0.4
                self.target_waveform[i] = wave * envelope
            self.orb_target_pulse = 1.0 + 0.15 * math.sin(self.phase * 2)
            self.target_glow_radius = 1.3

        elif self.state == "thinking":
            # Thinking - slow, contemplative pulse
            for i in range(64):
                wave = math.sin(self.waveform_phase * 0.5 + i * 0.4) * 0.15
                envelope = 1.0 - abs(i - 31.5) / 31.5 * 0.6
                self.target_waveform[i] = wave * envelope
            self.orb_target_pulse = 1.0 + 0.08 * math.sin(self.phase * 0.8)
            self.target_glow_radius = 1.1

        elif self.state == "speaking":
            # Speaking - dynamic waveform simulating voice
            amplitude = 0.5 + 0.4 * abs(math.sin(self.waveform_phase * 1.2))
            for i in range(64):
                wave = (
                    math.sin(self.waveform_phase * 2.0 + i * 0.25) * 0.6 +
                    math.sin(self.waveform_phase * 3.1 + i * 0.4) * 0.3 +
                    math.sin(self.waveform_phase * 1.5 + i * 0.15) * 0.2
                ) * amplitude
                envelope = 1.0 - abs(i - 31.5) / 31.5 * 0.3
                self.target_waveform[i] = wave * envelope
            self.orb_target_pulse = 1.0 + 0.2 * abs(math.sin(self.phase * 2.5))
            self.target_glow_radius = 1.5

        else:  # idle
            # Idle - gentle breathing
            for i in range(64):
                self.target_waveform[i] *= 0.95
            self.orb_target_pulse = 1.0 + 0.05 * math.sin(self.phase * 0.5)
            self.target_glow_radius = 0.8

    def set_state(self, state):
        if state not in {"idle", "listening", "thinking", "speaking"}:
            state = "idle"
        self.state = state

        # Set target values for smooth interpolation in animate()
        if state == "listening":
            self.orb_target_pulse = 1.15
            self.target_glow_radius = 1.3
        elif state == "thinking":
            self.orb_target_pulse = 1.0
            self.target_glow_radius = 1.1
        elif state == "speaking":
            self.orb_target_pulse = 1.25
            self.target_glow_radius = 1.5
        else:  # idle
            self.orb_target_pulse = 1.0
            self.target_glow_radius = 0.8

        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Clear
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

        cx = self.width() / 2
        cy = self.height() / 2 - 30

        # Draw glow layers (back to front)
        self._draw_glow_layers(painter, cx, cy)

        # Draw waveform
        self._draw_waveform(painter, cx, cy)

        # Draw main orb
        self._draw_orb(painter, cx, cy)

        # Draw state label
        self._draw_state_label(painter, cx, cy)

    def _draw_glow_layers(self, painter, cx, cy):
        """Draw a soft atmospheric bloom behind the orb."""
        base_radius = self.orb_radius * self.orb_pulse
        glow_extent = self.glow_radius * 60

        # Outer subtle glow
        for layer in range(8, 0, -1):
            radius = base_radius + glow_extent * (layer / 8) * 1.5
            alpha = int(14 * (1 - layer / 8) * self.glow_radius)
            color = QColor(self.GLOW)
            color.setAlpha(alpha)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                QPointF(cx, cy), radius, radius
            )

        # Middle glow ring
        for layer in range(6, 0, -1):
            radius = base_radius + glow_extent * (layer / 6) * 0.8
            alpha = int(22 * (1 - layer / 6) * self.glow_radius)
            color = QColor(self.VIOLET)
            color.setAlpha(alpha)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                QPointF(cx, cy), radius, radius
            )

    def _draw_waveform(self, painter, cx, cy):
        """Draw a compact, colour-shifting voice waveform."""
        if not any(abs(v) > 0.01 for v in self.waveform_data):
            return

        wave_y = cy + self.orb_radius * self.orb_pulse + 25
        bar_width = 3
        bar_spacing = 1
        total_width = 64 * (bar_width + bar_spacing)
        start_x = cx - total_width / 2

        # Gradient for waveform
        gradient = QLinearGradient(start_x, wave_y - 40, start_x, wave_y + 40)
        gradient.setColorAt(0, QColor(72, 215, 255, 200))
        gradient.setColorAt(0.45, QColor(145, 91, 255, 220))
        gradient.setColorAt(1, QColor(255, 83, 188, 190))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)

        for i, value in enumerate(self.waveform_data):
            if abs(value) < 0.005:
                continue

            x = start_x + i * (bar_width + bar_spacing)
            height = abs(value) * 50 * self.glow_radius
            y = wave_y - height / 2

            # Rounded bars
            rect = QRectF(x, y, bar_width, height)
            painter.drawRoundedRect(rect, 2, 2)

    def _draw_orb(self, painter, cx, cy):
        """Draw a liquid-glass Siri-inspired orb."""
        radius = self.orb_radius * self.orb_pulse

        # Fine glass rim gives the orb a crisp edge against any wallpaper.
        pen = QPen(QColor(233, 246, 255, 135), 1.25)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), radius + 2, radius + 2)

        # Clip animated colour pools into a single seamless glass sphere.
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), radius, radius)
        painter.save()
        painter.setClipPath(clip)
        base = QRadialGradient(cx - radius * 0.22, cy - radius * 0.28, radius * 1.3)
        base.setColorAt(0.0, QColor(106, 235, 255))
        base.setColorAt(0.34, QColor(69, 139, 255))
        base.setColorAt(0.72, QColor(100, 68, 222))
        base.setColorAt(1.0, QColor(37, 26, 111))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(base))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        pools = (
            (self.CYAN, 0.46, 0.20, 1.00),
            (self.PINK, 0.42, 0.66, 1.65),
            (self.VIOLET, 0.38, 1.26, 2.20),
        )
        for color, size, speed, offset in pools:
            x = cx + math.cos(self.phase * speed + offset) * radius * 0.42
            y = cy + math.sin(self.phase * speed * 1.17 + offset) * radius * 0.36
            pool = QRadialGradient(x, y, radius * size)
            pool_color = QColor(color)
            pool_color.setAlpha(185)
            pool.setColorAt(0.0, pool_color)
            edge = QColor(color)
            edge.setAlpha(0)
            pool.setColorAt(1.0, edge)
            painter.setBrush(QBrush(pool))
            painter.drawEllipse(QPointF(x, y), radius * size, radius * size)
        painter.restore()

        # Moving specular highlight sells the liquid-glass surface.
        highlight_gradient = QRadialGradient(cx - radius * 0.34, cy - radius * 0.40, radius * 0.68)
        highlight_gradient.setColorAt(0.0, QColor(255, 255, 255, 150))
        highlight_gradient.setColorAt(0.36, QColor(221, 247, 255, 48))
        highlight_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(highlight_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), radius * 0.9, radius * 0.9)

        # A restrained breathing core retains a clear assistant focal point.
        core_radius = radius * 0.19
        core_gradient = QRadialGradient(cx, cy, core_radius)
        pulse_intensity = 0.5 + 0.5 * math.sin(self.phase * 3)
        core_gradient.setColorAt(0.0, QColor(255, 255, 255, int(180 * pulse_intensity)))
        core_gradient.setColorAt(1.0, QColor(183, 226, 255, int(70 * pulse_intensity)))
        painter.setBrush(QBrush(core_gradient))
        painter.drawEllipse(QPointF(cx, cy), core_radius, core_radius)

    def _draw_state_label(self, painter, cx, cy):
        """Draw subtle state label below orb."""
        label_y = cy + self.orb_radius * self.orb_pulse + 75

        state_labels = {
            "listening": "Listening…",
            "thinking": "Thinking…",
            "speaking": "Speaking…",
            "idle": "JARVIS"
        }

        text = state_labels.get(self.state, "JARVIS")

        font = QFont("SF Pro Text", 11)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)

        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(text)

        # Subtle background pill
        pill_padding = 16
        pill_rect = QRectF(
            cx - text_width / 2 - pill_padding,
            label_y - metrics.ascent() - 6,
            text_width + pill_padding * 2,
            metrics.height() + 12
        )

        pill_color = QColor(12, 17, 38, 178)
        painter.setBrush(QBrush(pill_color))
        painter.setPen(QPen(QColor(182, 214, 255, 80), 1))
        painter.drawRoundedRect(pill_rect, 16, 16)

        # Text
        painter.setPen(QColor(255, 255, 255, 220))
        painter.drawText(
            QRectF(cx - text_width / 2, label_y - metrics.ascent(), text_width, metrics.height()),
            Qt.AlignmentFlag.AlignCenter,
            text
        )


class _CommandBridge(QObject):
    command = pyqtSignal(str)


def run_overlay():
    app = QApplication(sys.argv)

    # App as accessory - no Dock icon, no space switch
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except ImportError:
        pass

    bridge = _CommandBridge()
    orb = SiriOrb()

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
        environment.setdefault("QT_QUICK_BACKEND", "software")
        return subprocess.Popen(
            [sys.executable, __file__, "--server"],
            stdin=subprocess.PIPE,
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=environment,
            text=True,
            bufsize=1
        )

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
