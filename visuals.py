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
    # ------------------------------------------------------------------
    # DEFAULT_STYLE
    # ------------------------------------------------------------------
    # All numbers controlling the look of the overlay live here so they
    # can be tweaked at runtime (see tuner.py) and so that the boring
    # paintEvent stays just "draw these things at these positions".
    # Coordinates and sizes are in DESIGN PIXELS (i.e. they describe the
    # layout at scale == 1.0). The painter multiplies them by
    # self.scale_factor at draw time, so the overlay matches the user
    # INTERFACE_SCALE from config.py.
    #
    # Changing values here changes the BUILT-IN default for everyone.
    # To experiment without touching this dict, pass `style=` to
    # __init__() or call update_style(...) at runtime — what the tuner
    # does. The runtime style is layered ON TOP of these defaults, so
    # any key not provided falls back here.
    DEFAULT_STYLE = {
        # background opacity (0..255) of the dark panel behind text
        'bg_alpha': 196,

        # gradient fade widths at the four edges (design px)
        'fade_top': 8,
        'fade_bottom': 8,
        'fade_left': 20,
        'fade_right': 190,

        # primary blue used by header and message text
        'color_blue': '#43B1FE',
        'color_white': '#FFFFFF',

        # 'QUICK CHAT' header
        'header1_x': 35,
        'header1_y': 35,
        'header1_font_size': 15,
        'header1_letter_spacing': 1.7,

        # category header (e.g. 'COMPLIMENTS')
        'header2_x': 35,
        'header2_y': 67,
        'header2_font_size': 19,
        'header2_letter_spacing': 2.0,

        # text outline + glow around the category header
        'outline_width': 1.3,
        'glow_layers': 8,
        'glow_max_width': 14,
        'glow_base_alpha': 32,

        # numeric labels (1..4) on the left
        'nums_left': 46,
        'nums_top': 108,
        'nums_font_size': 16,
        'nums_font_weight': 50,

        # phrases column
        'msgs_left': 82,
        'msgs_font_size': 16,
        'msgs_font_weight': 50,

        # vertical distance between consecutive numbered rows
        'line_offset': 40,

        # right-side padding used for eliding long phrases
        'right_padding': 26,
    }

    def __init__(self, windows_params, scale=1.0, style=None):
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

        # UI scale factor (1.0 == 100%). All hard-coded sizes inside
        # paintEvent are multiplied by this so that the overlay always
        # matches the user-defined INTERFACE_SCALE from config.py.
        self.scale_factor = float(scale) if scale else 1.0

        # Effective style is DEFAULT_STYLE with any caller overrides
        # merged on top. Editable in place via update_style().
        self.style = dict(self.DEFAULT_STYLE)
        if style:
            self.style.update(style)

        # dynamic content
        self.category_text = 'COMPLIMENTS'
        self.msgs = ["Nice one!", "Great pass!", "Thanks!", "What a save!"]
        self.fade_anim = None
        self.selected_index = None
        self.selected_weight = 65
        self.selected_color = "#FFFFFF"

        bour_path = os.path.join(os.path.dirname(__file__), "fonts", "menu", "Bourgeois-Light.otf")
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
            arial_path = os.path.join(os.path.dirname(__file__), "fonts", "phrases", "arialnarrow.ttf")
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

    # --- runtime tweaking helpers (used by tuner.py) ---
    def update_style(self, **kwargs):
        """Merge `kwargs` into self.style and force a repaint."""
        self.style.update(kwargs)
        self.update()

    def set_scale(self, scale):
        """Change the global multiplier for sizes/positions in paintEvent."""
        self.scale_factor = float(scale) if scale else 1.0
        self.update()

    def set_geometry_dict(self, params):
        """Convenience: change window left/top/width/height in one call."""
        self.setGeometry(
            int(params['left']),
            int(params['top']),
            int(params['width']),
            int(params['height']),
        )

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
        st = self.style

        # Scale helpers. Style values are expressed in "design pixels"
        # (the layout at scale_factor == 1.0). At draw time we multiply
        # by self.scale_factor so a single INTERFACE_SCALE knob in
        # config.py controls the whole UI.
        s = self.scale_factor
        def sx(v):  # integer pixel coordinate / length
            return int(round(v * s))
        def sf(v):  # float quantity (font sizes, pen widths, letter spacing)
            return v * s

        blue  = st['color_blue']
        white = st['color_white']

        # main background
        painter.fillRect(0, 0, w, h, QColor(0, 0, 0, int(st['bg_alpha'])))

        # Carve transparent gradients out of the panel along each edge.
        painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)

        # top fade
        fade = sx(st['fade_top'])
        if fade > 0:
            grad = QLinearGradient(0, 0, 0, fade)
            grad.setColorAt(0, QColor(0, 0, 0, 255))
            grad.setColorAt(1, QColor(0, 0, 0,   0))
            painter.fillRect(0, 0, w, fade, grad)
        # bottom fade
        fade = sx(st['fade_bottom'])
        if fade > 0:
            grad = QLinearGradient(0, h, 0, h - fade)
            grad.setColorAt(0, QColor(0, 0, 0, 255))
            grad.setColorAt(1, QColor(0, 0, 0,   0))
            painter.fillRect(0, h - fade, w, fade, grad)
        # left fade
        fade = sx(st['fade_left'])
        if fade > 0:
            grad = QLinearGradient(0, 0, fade, 0)
            grad.setColorAt(0, QColor(0, 0, 0, 255))
            grad.setColorAt(1, QColor(0, 0, 0,   0))
            painter.fillRect(0, 0, fade, h, grad)
        # right fade
        fade = sx(st['fade_right'])
        if fade > 0:
            grad = QLinearGradient(w, 0, w - fade, 0)
            grad.setColorAt(0, QColor(0, 0, 0, 255))
            grad.setColorAt(1, QColor(0, 0, 0,   0))
            painter.fillRect(w - fade, 0, fade, h, grad)

        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # (text, color, (x, y), font_size, letter_spacing) in design pixels
        headers = [
            ('QUICK CHAT',       blue,  (st['header1_x'], st['header1_y']),
             st['header1_font_size'], st['header1_letter_spacing']),
            (self.category_text, white, (st['header2_x'], st['header2_y']),
             st['header2_font_size'], st['header2_letter_spacing']),
        ]

        outline_width = sf(st['outline_width'])

        for text, color, (x, y), size, spacing in headers:
            font = QFont(self.header_family, max(1, int(round(sf(size)))))
            font.setLetterSpacing(QFont.AbsoluteSpacing, sf(spacing))
            painter.setFont(font)

            path = QPainterPath()
            path.addText(sx(x), sx(y), font, text)

            pen_outline = QPen(QColor(color))
            pen_outline.setWidthF(outline_width)
            pen_outline.setJoinStyle(Qt.RoundJoin)
            painter.strokePath(path, pen_outline)

            if text == self.category_text:
                # Second stroke pass (kept identical to original logic).
                pen_outline = QPen(QColor(color))
                pen_outline.setWidthF(outline_width)
                pen_outline.setJoinStyle(Qt.RoundJoin)
                painter.strokePath(path, pen_outline)

                layers     = max(1, int(st['glow_layers']))
                max_glow_w = sf(st['glow_max_width'])
                base_alpha = int(st['glow_base_alpha'])

                for i in range(layers):
                    frac = i / (layers - 1) if layers > 1 else 1.0
                    w_glow = outline_width + (max_glow_w - outline_width) * frac
                    a      = int(base_alpha * (1 - frac))
                    if a <= 0:
                        continue

                    glow = QColor(blue)
                    glow.setAlpha(a)
                    pen = QPen(glow)
                    pen.setWidthF(w_glow)
                    pen.setJoinStyle(Qt.RoundJoin)
                    painter.strokePath(path, pen)

            painter.fillPath(path, QColor(color))

        # Numeric labels (1..4) on the left
        nums_font_size = max(1, int(round(sf(st['nums_font_size']))))
        line_offset    = st['line_offset']
        for i in range(1, 5):
            text = str(i)
            x = sx(st['nums_left'])
            y = sx(st['nums_top'] + line_offset * (i - 1))
            font = QFont(self.number_family, nums_font_size, int(st['nums_font_weight']))
            painter.setFont(font)
            painter.setPen(QColor(white))
            painter.drawText(x, y, text)

        # Phrase column
        msg_font_size = max(1, int(round(sf(st['msgs_font_size']))))
        right_padding = sx(st['right_padding'])
        for i in range(4):
            text = self.msgs[i]
            x = sx(st['msgs_left'])
            baseline_y = sx(st['nums_top'] + line_offset * i)

            font = QFont(self.number_family, msg_font_size)
            if self.selected_index is not None and i == self.selected_index:
                font.setWeight(int(self.selected_weight))
            else:
                font.setWeight(int(st['msgs_font_weight']))
            painter.setFont(font)
            if self.selected_index is not None and i == self.selected_index:
                painter.setPen(QColor(self.selected_color))
            else:
                painter.setPen(QColor(blue))
            fm = painter.fontMetrics()
            max_width = self.width() - x - right_padding
            single_line = fm.elidedText(text, Qt.ElideRight, max_width)
            painter.drawText(x, baseline_y, single_line)


if __name__ == "__main__":
    # Standalone preview. Lets you eyeball the overlay without launching
    # the rest of the script. Try changing INTERFACE_SCALE to see how
    # the menu scales — both the window and the contents grow together.
    INTERFACE_SCALE = 100
    default = {'left': 16, 'top': 470, 'width': 395, 'height': 260}
    s = INTERFACE_SCALE / 100.0
    wp = {
        'left':   int(default['left']   * s),
        'top':    int(0.4 * default['top'] * s),  # shifted up so the preview fits a typical desktop
        'width':  int(default['width']  * s),
        'height': int(default['height'] * s),
    }

    app = QApplication(sys.argv)
    overlay = FramelessOverlay(wp, scale=s)
    overlay.set_content('COMPLIMENTS', ["Nice one!", "Great pass!", "Thanks!", "What a save!"])
    overlay.show()

    hwnd = int(overlay.winId())
    win32gui.SetWindowPos(
        hwnd, win32con.HWND_TOPMOST,
        0,0,0,0,
        win32con.SWP_NOMOVE|win32con.SWP_NOSIZE|win32con.SWP_SHOWWINDOW
    )

    sys.exit(app.exec_())
