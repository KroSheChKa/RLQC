import sys
import os
import win32gui
import win32con
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import (
    QPainter, QColor, QFontDatabase, QFont,
    QLinearGradient, QPainterPath, QPen
)
from PyQt5.QtWidgets import QApplication, QWidget
import math

class FramelessOverlay(QWidget):
    def __init__(self, windows_params):
        super().__init__()
        # Qt.Tool - no selectable window
        flags = Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.Tool | Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(
            windows_params['left'],
            windows_params['top'],
            windows_params['width'],
            windows_params['height']
        )

        # dynamic content
        self.category_text = 'COMPLIMENTS'
        self.msgs = ["Nice one!", "Great pass!", "Thanks!", "What a save!"]
        self.fade_anim = None
        self.selected_index = None
        self.selected_weight = 65
        self.selected_color = "#FFFFFF"

        bour_path = os.path.join(os.path.dirname(__file__), "fonts\\menu\\Bourgeois-Light.otf")
        if os.path.exists(bour_path):
            fid = QFontDatabase.addApplicationFont(bour_path)
            fams = QFontDatabase.applicationFontFamilies(fid)
            self.header_family = fams[0] if fams else "Sans Serif"
        else:
            print(f"Warning: {bour_path} not found, using Sans Serif")
            self.header_family = "Sans Serif"

        db = QFontDatabase()
        if "Arial Narrow" in db.families():
            self.number_family = "Arial Narrow"
        else:
            arial_path = os.path.join(os.path.dirname(__file__), "fonts\\phrases\\arialnarrow.ttf")
            if os.path.exists(arial_path):
                fid2 = QFontDatabase.addApplicationFont(arial_path)
                fams2 = QFontDatabase.applicationFontFamilies(fid2)
                self.number_family = fams2[0] if fams2 else "Sans Serif"
            else:
                print(f"Warning: Arial Narrow not found in system or {arial_path}, using Sans Serif")
                self.number_family = "Sans Serif"

    def set_content(self, category_text, msgs):
        self.category_text = str(category_text) if category_text else ''
        # ensure exactly 4 lines, truncate or pad
        m = list(msgs)[:4] if msgs else []
        while len(m) < 4:
            m.append('')
        self.msgs = m
        self.update()

    def clear_selection(self):
        self.selected_index = None
        self.update()

    def set_selection(self, idx, weight=75):
        self.selected_index = idx
        self.selected_weight = weight
        self.update()

    def set_selected_style(self, idx, weight=75, color="#FFFFFF"):
        self.selected_index = idx
        self.selected_weight = weight
        self.selected_color = color
        self.update()

    # --- animations ---
    def _fade_to(self, target_opacity, duration_ms=200):
        if self.fade_anim is not None:
            try:
                self.fade_anim.stop()
            except Exception:
                pass
            self.fade_anim.deleteLater()
            self.fade_anim = None

        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(duration_ms)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(target_opacity)
        anim.setEasingCurve(QEasingCurve.InOutQuad)

        if target_opacity == 0.0:
            def _hide():
                self.hide()
            anim.finished.connect(_hide)

        anim.start()
        self.fade_anim = anim

    def fade_in(self, duration_ms=200):
        self.setWindowOpacity(0.0)
        self.show()
        self._fade_to(1.0, duration_ms)

    def fade_out(self, duration_ms=200):
        self._fade_to(0.0, duration_ms)

    def show_with_content(self, title, msgs, duration_ms=200):
        # Prepare invisible, set content, then fade-in to avoid flicker of stale content
        self.setWindowOpacity(0.0)
        self.set_content(title, msgs)
        self.clear_selection()
        self.show()
        self.repaint()
        self._fade_to(1.0, duration_ms)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # main background
        painter.fillRect(0, 0, w, h, QColor(0, 0, 0, 196))

        # cut mode
        painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        fade = 8
        # up
        grad = QLinearGradient(0, 0, 0, fade)
        grad.setColorAt(0, QColor(0,0,0,255))
        grad.setColorAt(1, QColor(0,0,0, 0))
        painter.fillRect(0, 0, w, fade, grad)
        # down
        grad = QLinearGradient(0, h, 0, h - fade)
        grad.setColorAt(0, QColor(0,0,0,255))
        grad.setColorAt(1, QColor(0,0,0, 0))
        painter.fillRect(0, h - fade, w, fade, grad)
        # left
        fade = 20
        grad = QLinearGradient(0, 0, fade, 0)
        grad.setColorAt(0, QColor(0,0,0,255))
        grad.setColorAt(1, QColor(0,0,0, 0))
        painter.fillRect(0, 0, fade, h, grad)
        # right
        fade = 190
        grad = QLinearGradient(w, 0, w - fade, 0)
        grad.setColorAt(0, QColor(0,0,0,255))
        grad.setColorAt(1, QColor(0,0,0, 0))
        painter.fillRect(w - fade, 0, fade, h, grad)

        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        blue = '#43B1FE'

        headers = [
            ('QUICK CHAT', blue, (35, 35), 15, 1.7),
            (self.category_text, '#FFFFFF', (35, 67), 19, 2)
        ]

        for text, color, (x, y), size, spacing in headers:
            font = QFont(self.header_family, size)
            font.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
            painter.setFont(font)

            path = QPainterPath()
            path.addText(x, y, font, text)

            pen_outline = QPen(QColor(color))
            pen_outline.setWidthF(1.3)
            pen_outline.setJoinStyle(Qt.RoundJoin)
            painter.strokePath(path, pen_outline)

            if text == self.category_text:

                pen_outline = QPen(QColor(color))
                pen_outline.setWidthF(1.3)
                pen_outline.setJoinStyle(Qt.RoundJoin)
                painter.strokePath(path, pen_outline)

                layers = 8
                max_glow_w = 14
                base_alpha = 32

                for i in range(layers):
                    frac = i / (layers - 1)
                    w    = 1.3 + (max_glow_w - 1.3) * frac
                    a    = int(base_alpha * (1 - frac))
                    if a <= 0:
                        continue

                    glow = QColor(blue)
                    glow.setAlpha(a)
                    pen = QPen(glow)
                    pen.setWidthF(w)
                    pen.setJoinStyle(Qt.RoundJoin)
                    painter.strokePath(path, pen)
                
            painter.fillPath(path, QColor(color))


        nums = {'left': 46, 'top': 108, 'font-size': 16, 'font-weight': 50, 'line-offset': 40}

        for i in range(1, 5):
            text = str(i)
            x = nums['left']
            y = nums['top'] + nums['line-offset'] * (i - 1)

            font = QFont(self.number_family, nums['font-size'], nums['font-weight'])
            painter.setFont(font)
            painter.setPen(QColor('#FFFFFF'))
            painter.drawText(x, y, text)

        chat_msgs = {'left': 82, 'top': nums['top'], 'font-size': 16, 'font-weight': 50, 'line-offset': 40}

        for i in range(4):
            text = self.msgs[i]
            x = chat_msgs['left']
            baseline_y = chat_msgs['top'] + chat_msgs['line-offset'] * (i)

            # Draw a single line per item, eliding if necessary. Shadow/background stays unchanged
            font = QFont(self.number_family, chat_msgs['font-size'])
            if self.selected_index is not None and i == self.selected_index:
                font.setWeight(int(self.selected_weight))
            else:
                font.setWeight(int(chat_msgs['font-weight']))
            painter.setFont(font)
            if self.selected_index is not None and i == self.selected_index:
                painter.setPen(QColor(self.selected_color))
            else:
                painter.setPen(QColor(blue))
            fm = painter.fontMetrics()
            max_width = self.width() - x - 26
            single_line = fm.elidedText(text, Qt.ElideRight, max_width)
            painter.drawText(x, baseline_y, single_line)


if __name__ == "__main__":
    INTERFACE_SCALE = 100
    default = {'left':16,'top':470,'width':395,'height':260}
    left = int(default['left'] * INTERFACE_SCALE/100)
    top = int(0.4*default['top'] * INTERFACE_SCALE/100)
    width = int(default['width'] * INTERFACE_SCALE/100)
    height = int(default['height'] * INTERFACE_SCALE/100)
    wp = {'left':left,'top':top,'width':width,'height':height}

    app = QApplication(sys.argv)
    overlay = FramelessOverlay(wp)
    overlay.set_content('COMPLIMENTS', ["Nice one!", "Great pass!", "Thanks!", "What a save!"])
    overlay.show()

    hwnd = int(overlay.winId())
    win32gui.SetWindowPos(
        hwnd, win32con.HWND_TOPMOST,
        0,0,0,0,
        win32con.SWP_NOMOVE|win32con.SWP_NOSIZE|win32con.SWP_SHOWWINDOW
    )

    sys.exit(app.exec_())
