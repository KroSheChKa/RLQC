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

# ----------------------------------------------------------------------
# "Selected phrase" style — game-fixed constants
# ----------------------------------------------------------------------
# When the user picks a phrase from the quick-chat menu, the in-game
# overlay reacts in a very specific, non-customisable way:
#
#   * the text colour snaps to pure WHITE (#FFFFFF);
#   * the font weight becomes noticeably heavier than the default
#     (everything in the ~67-99 range looks correct in-game; 75 is
#     a safe middle that matches "Bold");
#   * there is NO glow / outline on the selected line itself — only
#     the category header has a glow halo.
#
# Both of those properties are dictated by the game itself, not by
# screen resolution, HUD scale or Windows DPI — so they are kept
# here as module-level constants instead of polluting DEFAULT_STYLE.
# The tuner deliberately does NOT expose sliders for them.
#
# The one selected-state value that DOES vary per pixel-density is
# `selected_letter_spacing`, which still lives in DEFAULT_STYLE (and
# in the tuner) because it has to be calibrated for each resolution
# / UI-scale combo; see TODO.md #2 — the auto-adaptation formula
# eventually scales it the same way it scales other geometry.
# ----------------------------------------------------------------------
SELECTED_COLOR  = "#FFFFFF"
SELECTED_WEIGHT = 75


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
        # Colour of the dark panel and how opaque it is.
        'bg_color': '#000000',
        'bg_alpha': 196,

        # gradient fade widths at the four edges (design px)
        'fade_top': 8,
        'fade_bottom': 8,
        'fade_left': 20,
        'fade_right': 190,

        # Edge-fade curve (shared across all four sides).
        # Quadratic Bezier control point: P0=(0,1), P1=(bx,by), P2=(1,0).
        #   (0.5, 0.5) -> pure linear fade (the historical look).
        #   bx<0.5    -> fade ramps up faster early, then plateaus.
        #   by>0.5    -> long opaque tail near the panel before fading.
        # See _build_fade_gradient() for the parametric sampling.
        'fade_bezier_x': 0.5,
        'fade_bezier_y': 0.5,

        # Per-side "offset": fraction of the fade region that stays
        # fully opaque before the curve starts. 0.0 = fade begins at
        # the inner edge (current behaviour). 0.4 = first 40% of the
        # fade strip is solid panel and only then the curve kicks in.
        'fade_top_offset':    0.0,
        'fade_bottom_offset': 0.0,
        'fade_left_offset':   0.0,
        'fade_right_offset':  0.0,

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
        'msgs_letter_spacing': 0.0,

        # Selected phrase: only the letter-spacing value lives here,
        # because that's the one part of the selection look that has
        # to be re-calibrated per resolution / UI scale (see
        # SELECTED_COLOR / SELECTED_WEIGHT module constants for the
        # rest, which are game-fixed).
        'selected_letter_spacing': 0.3,

        # vertical distance between consecutive numbered rows
        'line_offset': 40,

        # right-side padding used for eliding long phrases
        'right_padding': 26,

        # ------------------------------------------------------------
        # Per-text-region letter-spacing scaling exponents.
        # ------------------------------------------------------------
        # Almost every dimension here scales linearly with HUD scale
        # (size_eff = size × scale_factor). Empirically though,
        # Rocket League's in-game text does NOT scale its letter-
        # spacing uniformly with HUD scale, and the deviation from
        # linear is different for each text region (header, category,
        # phrases). We model each region with its own power-law
        # exponent:
        #
        #     LS_effective = LS_base × scale_factor ** exponent
        #
        #     exponent  > 1.0   →  LS shrinks FASTER than linear at
        #                          low HUD scales (text gets tighter)
        #     exponent == 1.0   →  linear (LS proportional to font)
        #     exponent  < 1.0   →  LS shrinks SLOWER than linear
        #     exponent == 0.0   →  LS is HUD-independent / constant
        #                          pixels regardless of font size.
        #                          This is the apparent model RL uses
        #                          for the phrase rows — letters keep
        #                          a fixed gap no matter the HUD.
        #
        # At scale_factor == 1.0 any exponent collapses to identity
        # (1**p == 1), so the HUD=100 calibration is preserved no
        # matter what value goes here.
        #
        # The defaults below were fit from a HUD=75 visual-match
        # calibration on a 3440x1440 / `_new_background` reference
        # preset (the HUD=50 first-pass values turned out to be
        # eyeball-noisy because the LS differences are sub-pixel at
        # that scale; HUD=75 gave a much sharper reading):
        #
        #     header1:  LS 2.3 (HUD=100) → rendered 1.99 @ HUD=75 → p ≈ 0.51
        #     header2:  LS 2.6           → rendered 1.84 @ HUD=75 → p ≈ 1.24
        #     msgs:     LS 0.8 (constant in px across HUDs)       → p = 0.0
        #     selected: LS 0.6 (constant in px across HUDs)       → p = 0.0
        #
        # Both phrase rows (msgs + selected) end up with p = 0.0:
        # RL apparently uses a fixed pixel kerning for the phrase
        # column, independent of HUD scale. The numeric value
        # differs (0.8 vs 0.6) because the selected line is bold,
        # so a slightly tighter spacing keeps letters from looking
        # squashed.
        #
        # If you collect a new measurement at HUD = h with rendered
        # letter-spacing LS_h, the matching exponent is:
        #
        #     p = log(LS_h / LS_base) / log(h / 100)
        'header1_ls_scale_exponent':  0.51,
        'header2_ls_scale_exponent':  1.24,
        'msgs_ls_scale_exponent':     0.0,
        'selected_ls_scale_exponent': 0.0,
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

    def set_selection(self, idx):
        """Backwards-compatible alias of set_selected_style()."""
        self.set_selected_style(idx)

    def set_selected_style(self, idx, **_ignored):
        """Mark the phrase at `idx` as selected.

        Visual style of the highlighted line is fixed by the game
        (see SELECTED_COLOR / SELECTED_WEIGHT module constants and
        the `selected_letter_spacing` style key). Extra kwargs are
        accepted and ignored for backwards compatibility with older
        call sites that used to pass weight= / color=.
        """
        self.selected_index = idx
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

    # ------------------------------------------------------------------
    # Edge fade — quadratic Bezier sampled into a multi-stop gradient.
    #
    # The gradient is used as a CompositionMode_DestinationOut mask, so
    # alpha=255 means "cut a hole here" and alpha=0 means "keep the
    # panel visible". We design the curve in that mask-alpha space:
    #
    #   * t = 0  ⇒  inner edge of the fade strip  ⇒  alpha 0
    #               (panel stays solid)
    #   * t = 1  ⇒  outer edge of the fade strip  ⇒  alpha 255
    #               (fully transparent)
    #
    # The Bezier P(t) = (1-t)²·(0,0) + 2(1-t)t·(bx,by) + t²·(1,1)
    # bows between those two corners. With (bx, by) = (0.5, 0.5) it
    # is the straight diagonal — i.e. the historical linear fade.
    #
    #   alpha ▲       P2=(1,1)
    #     1   │       ╱
    #         │      ╱       (bx,by) pulls the curve up/down or
    #         │     ╱        early/late within the strip
    #         │    ╱
    #     0   P0──╯
    #         └────────► position along the fade strip
    #
    # `offset` (0..0.95) is an opaque-panel "hold" of that fraction
    # near the INNER edge: the panel stays fully visible for the first
    # `offset` of the strip, then the Bezier curve starts. This matches
    # how RL's in-game chat falloff feels — late and then soft.
    # ------------------------------------------------------------------
    def _draw_glowing_text(self, painter, path, fill_color, glow_color,
                           outline_width, st):
        """Render a text `path` with a double outline + soft outer glow.

        Used for the category header (e.g. "COMPLIMENTS"):
          * stroke the glyph path twice with the fill colour — this
            is what visually thickens the header edge in-game;
          * draw a few concentric strokes of `glow_color` whose
            width grows from `outline_width` up to `glow_max_width`
            while alpha falls from `glow_base_alpha` to 0 (cheap
            fake-blur);
          * fill the path with `fill_color`.

        Intentionally NOT used for the selected-phrase line: in the
        real game the selected phrase has no glow / no outline, only
        a colour + weight change. See paintEvent() for that path.
        """
        pen_outline = QPen(QColor(fill_color))
        pen_outline.setWidthF(outline_width)
        pen_outline.setJoinStyle(Qt.RoundJoin)
        painter.strokePath(path, pen_outline)
        painter.strokePath(path, pen_outline)

        layers     = max(1, int(st['glow_layers']))
        max_glow_w = st['glow_max_width'] * self.scale_factor
        base_alpha = int(st['glow_base_alpha'])

        for i in range(layers):
            frac   = i / (layers - 1) if layers > 1 else 1.0
            w_glow = outline_width + (max_glow_w - outline_width) * frac
            a      = int(base_alpha * (1 - frac))
            if a <= 0:
                continue

            glow = QColor(glow_color)
            glow.setAlpha(a)
            pen = QPen(glow)
            pen.setWidthF(w_glow)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.strokePath(path, pen)

        painter.fillPath(path, QColor(fill_color))

    @staticmethod
    def _build_fade_gradient(grad, offset, bx, by, samples=24):
        offset = max(0.0, min(0.95, float(offset)))
        bx = max(0.0, min(1.0, float(bx)))
        by = max(0.0, min(1.0, float(by)))

        # Solid hold from 0 to `offset` (mask alpha = 0 -> panel visible)
        if offset > 0:
            grad.setColorAt(0.0,    QColor(0, 0, 0, 0))
            grad.setColorAt(offset, QColor(0, 0, 0, 0))

        span = 1.0 - offset
        for k in range(samples + 1):
            t = k / samples
            x = 2 * (1 - t) * t * bx + t * t
            y = 2 * (1 - t) * t * by + t * t
            pos   = offset + max(0.0, min(1.0, x)) * span
            alpha = int(round(255 * max(0.0, min(1.0, y))))
            grad.setColorAt(pos, QColor(0, 0, 0, alpha))

        # Force exact endpoints in case sampling rounded slightly.
        grad.setColorAt(0.0 if offset == 0 else offset, QColor(0, 0, 0, 0))
        grad.setColorAt(1.0, QColor(0, 0, 0, 255))

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
        def sf(v):  # float quantity (font sizes, pen widths, etc.)
            return v * s

        # Letter-spacing gets a per-region helper because RL's text
        # scales LS non-linearly with HUD scale, and the exponent is
        # different for headers vs. category vs. phrases (see the
        # *_ls_scale_exponent block in DEFAULT_STYLE for the data
        # and derivation). At scale_factor == 1.0 every exponent
        # collapses to identity, so the HUD=100 calibration is
        # preserved no matter what these are set to.
        def ls_for(value, exp_key):
            p = float(st.get(exp_key, 1.0))
            factor = (s ** p) if s > 0 else 1.0
            return value * factor

        blue  = st['color_blue']
        white = st['color_white']
        bx    = st['fade_bezier_x']
        by    = st['fade_bezier_y']

        # main background — colour is user-configurable now
        bg_qc = QColor(st['bg_color'])
        bg_qc.setAlpha(int(st['bg_alpha']))
        painter.fillRect(0, 0, w, h, bg_qc)

        # Carve transparent gradients out of the panel along each edge.
        painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)

        # top fade — strip runs from y=0 (outside) to y=fade (inside).
        # In our Bezier convention t=0 is the inner edge (opaque),
        # t=1 is the outer edge (transparent), hence the gradient
        # vector goes from (0, fade) -> (0, 0).
        fade = sx(st['fade_top'])
        if fade > 0:
            grad = QLinearGradient(0, fade, 0, 0)
            self._build_fade_gradient(grad, st['fade_top_offset'], bx, by)
            painter.fillRect(0, 0, w, fade, grad)
        # bottom fade
        fade = sx(st['fade_bottom'])
        if fade > 0:
            grad = QLinearGradient(0, h - fade, 0, h)
            self._build_fade_gradient(grad, st['fade_bottom_offset'], bx, by)
            painter.fillRect(0, h - fade, w, fade, grad)
        # left fade
        fade = sx(st['fade_left'])
        if fade > 0:
            grad = QLinearGradient(fade, 0, 0, 0)
            self._build_fade_gradient(grad, st['fade_left_offset'], bx, by)
            painter.fillRect(0, 0, fade, h, grad)
        # right fade
        fade = sx(st['fade_right'])
        if fade > 0:
            grad = QLinearGradient(w - fade, 0, w, 0)
            self._build_fade_gradient(grad, st['fade_right_offset'], bx, by)
            painter.fillRect(w - fade, 0, fade, h, grad)

        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # (text, color, (x, y), font_size, letter_spacing, ls_exp_key)
        # all in design pixels. ls_exp_key picks the right per-region
        # letter-spacing scaling exponent from the style dict.
        headers = [
            ('QUICK CHAT',       blue,  (st['header1_x'], st['header1_y']),
             st['header1_font_size'], st['header1_letter_spacing'],
             'header1_ls_scale_exponent'),
            (self.category_text, white, (st['header2_x'], st['header2_y']),
             st['header2_font_size'], st['header2_letter_spacing'],
             'header2_ls_scale_exponent'),
        ]

        outline_width = sf(st['outline_width'])

        for text, color, (x, y), size, spacing, ls_key in headers:
            font = QFont(self.header_family, max(1, int(round(sf(size)))))
            font.setLetterSpacing(QFont.AbsoluteSpacing, ls_for(spacing, ls_key))
            painter.setFont(font)

            path = QPainterPath()
            path.addText(sx(x), sx(y), font, text)

            # 'QUICK CHAT' is drawn as a single thin outlined+filled label.
            # The category header is the highlighted one — same outline,
            # second stroke pass, blue glow underneath, then filled.
            if text == self.category_text:
                self._draw_glowing_text(
                    painter, path, color, blue, outline_width, st
                )
            else:
                pen_outline = QPen(QColor(color))
                pen_outline.setWidthF(outline_width)
                pen_outline.setJoinStyle(Qt.RoundJoin)
                painter.strokePath(path, pen_outline)
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
        msg_font_size           = max(1, int(round(sf(st['msgs_font_size']))))
        msg_letter_spacing      = ls_for(st['msgs_letter_spacing'],
                                         'msgs_ls_scale_exponent')
        selected_letter_spacing = ls_for(st['selected_letter_spacing'],
                                         'selected_ls_scale_exponent')
        right_padding           = sx(st['right_padding'])
        for i in range(4):
            text = self.msgs[i]
            x = sx(st['msgs_left'])
            baseline_y = sx(st['nums_top'] + line_offset * i)

            is_selected = (self.selected_index is not None and i == self.selected_index)

            # Selected line: game-fixed white + heavier weight + a
            # per-scale letter-spacing bump. Unselected: regular blue
            # with the default weight / spacing from the style dict.
            # NO glow, NO outline on the selected line — both are
            # absent in the in-game quick-chat.
            font = QFont(self.number_family, msg_font_size)
            if is_selected:
                font.setLetterSpacing(QFont.AbsoluteSpacing, selected_letter_spacing)
                font.setWeight(SELECTED_WEIGHT)
            else:
                font.setLetterSpacing(QFont.AbsoluteSpacing, msg_letter_spacing)
                font.setWeight(int(st['msgs_font_weight']))
            painter.setFont(font)
            fm = painter.fontMetrics()
            max_width = self.width() - x - right_padding
            single_line = fm.elidedText(text, Qt.ElideRight, max_width)

            painter.setPen(QColor(SELECTED_COLOR) if is_selected else QColor(blue))
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
