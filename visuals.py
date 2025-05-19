import sys
import os
import win32gui
import win32con
from PyQt5.QtCore import Qt
from PyQt5.QtGui import (
    QPainter, QColor, QFontDatabase, QFont,
    QLinearGradient, QPainterPath, QPen
)
from PyQt5.QtWidgets import QApplication, QWidget

class FramelessOverlay(QWidget):
    def __init__(self, windows_params):
        super().__init__()

        flags = Qt.FramelessWindowHint | Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(
            windows_params['left'],
            windows_params['top'],
            windows_params['width'],
            windows_params['height']
        )

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
            ('COMPLIMENTS', '#FFFFFF', (35, 67), 19, 2)
        ]

        for text, color, (x, y), size, spacing in headers:

            font = QFont(self.header_family, size)

            font.setLetterSpacing(QFont.AbsoluteSpacing, spacing)

            painter.setFont(font)
            path = QPainterPath()
            path.addText(x, y, font, text)
            painter.fillPath(path, QColor(color))

            pen = QPen(QColor(color))
            pen.setWidthF(1.3)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.strokePath(path, pen)

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

        msgs = ["Nice one!", "Great pass!", "Thanks!", "What a save!"]

        for i in range(4):
            text = msgs[i]
            x = chat_msgs['left']
            y = chat_msgs['top'] + chat_msgs['line-offset'] * (i)

            font = QFont(self.number_family, chat_msgs['font-size'], chat_msgs['font-weight'])
            painter.setFont(font)
            painter.setPen(QColor(blue))
            painter.drawText(x, y, text)


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
    overlay.show()

    hwnd = int(overlay.winId())
    win32gui.SetWindowPos(
        hwnd, win32con.HWND_TOPMOST,
        0,0,0,0,
        win32con.SWP_NOMOVE|win32con.SWP_NOSIZE|win32con.SWP_SHOWWINDOW
    )

    sys.exit(app.exec_())
