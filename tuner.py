"""
Overlay tuner.

A standalone GUI utility for hand-calibrating the quick-chat overlay
against the in-game Rocket League chat at arbitrary screen resolutions
and HUD scale settings.

Usage:
    python tuner.py

What it does:
    * Spawns a live FramelessOverlay (the same widget the main script
      uses) at the position from config.OVERLAY_POSITION.
    * Opens a separate control panel with sliders + spin boxes for
      every visual parameter (window geometry, paddings, font sizes,
      glow, scale, ...). Every change is reflected in the overlay in
      real time.
    * Auto-detects the local "environment": screen resolution, Windows
      display scale, Qt's device pixel ratio, etc. These are stored
      alongside every saved preset so that you can later derive
      automatic adaptation formulas from a handful of presets taken at
      different (resolution, HUD scale) combinations.
    * Reads/writes presets to overlay_presets.json next to this file.

Workflow you are expected to follow:
    1. Open Rocket League. Set HUD scale to e.g. 100%.
    2. Run this tuner. The live overlay shows up where the main script
       would put it.
    3. Tweak sliders until the overlay matches the in-game quick chat
       pixel-by-pixel.
    4. Fill in "Game HUD scale" (the value you set in step 1), give the
       preset a name, hit "Save preset".
    5. Change HUD scale in the game, alt-tab back, tweak again, save
       another preset. Repeat for a few HUD-scale values.
    6. (Optional) change Windows display scale or run on another
       resolution and repeat. The more data points, the better the
       automatic adaptation formula can be.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from visuals import FramelessOverlay
from config import OVERLAY_POSITION, INTERFACE_SCALE as DEFAULT_INTERFACE_SCALE


PRESETS_PATH = os.path.join(os.path.dirname(__file__), "overlay_presets.json")


# -----------------------------------------------------------------------------
# Schema describing every editable parameter.
#
# (group, key, label, type, min, max, step)
#   group: section label in the control panel
#   key:   identifier used in self.style and JSON
#   type:  int  -> QSpinBox + integer-stepped QSlider
#          float-> QDoubleSpinBox + slider (scaled internally)
#   min/max/step: spin-box bounds. For floats the slider gets
#                 max((max-min)/step, 1) integer steps.
# -----------------------------------------------------------------------------
PARAMS = [
    # ---- Window geometry (NOT in self.style — handled separately) ----
    ("Window", "left",        "Window X (px)",          int, -8000, 8000, 1),
    ("Window", "top",         "Window Y (px)",          int, -8000, 8000, 1),
    ("Window", "width",       "Window width (px)",      int,    50, 3000, 1),
    ("Window", "height",      "Window height (px)",     int,    50, 3000, 1),

    # ---- Global scale (applies to every drawn dimension) ----
    ("Scale", "interface_scale", "INTERFACE_SCALE (%)", int,   30,  200, 1),

    # ---- Background panel & edge fade ----
    ("Background",  "bg_alpha",    "Background alpha (0..255)", int, 0, 255, 1),
    ("Background",  "fade_top",    "Fade top (px)",             int, 0, 200, 1),
    ("Background",  "fade_bottom", "Fade bottom (px)",          int, 0, 200, 1),
    ("Background",  "fade_left",   "Fade left (px)",            int, 0, 400, 1),
    ("Background",  "fade_right",  "Fade right (px)",           int, 0, 800, 1),

    # ---- 'QUICK CHAT' header ----
    ("Header 'QUICK CHAT'", "header1_x",              "X (px)",          int,   0,  400, 1),
    ("Header 'QUICK CHAT'", "header1_y",              "Y (px)",          int,   0,  400, 1),
    ("Header 'QUICK CHAT'", "header1_font_size",      "Font size (pt)",  float, 1.0, 80.0, 0.5),
    ("Header 'QUICK CHAT'", "header1_letter_spacing", "Letter spacing",  float, 0.0, 10.0, 0.1),

    # ---- Category header (e.g. COMPLIMENTS) ----
    ("Header category", "header2_x",              "X (px)",          int,   0,  400, 1),
    ("Header category", "header2_y",              "Y (px)",          int,   0,  400, 1),
    ("Header category", "header2_font_size",      "Font size (pt)",  float, 1.0, 80.0, 0.5),
    ("Header category", "header2_letter_spacing", "Letter spacing",  float, 0.0, 10.0, 0.1),

    # ---- Outline + glow around the category header ----
    ("Glow & outline", "outline_width",  "Outline width (px)", float, 0.0, 10.0, 0.1),
    ("Glow & outline", "glow_layers",    "Glow layers",        int,   1,   30,  1),
    ("Glow & outline", "glow_max_width", "Glow max width (px)",float, 0.0, 60.0, 0.5),
    ("Glow & outline", "glow_base_alpha","Glow base alpha",    int,   0,   255, 1),

    # ---- Numeric labels 1..4 on the left ----
    ("Numbers (1..4)", "nums_left",        "X (px)",          int,   0,  600, 1),
    ("Numbers (1..4)", "nums_top",         "First-row Y (px)",int,   0,  600, 1),
    ("Numbers (1..4)", "nums_font_size",   "Font size (pt)",  float, 1.0, 80.0, 0.5),
    ("Numbers (1..4)", "nums_font_weight", "Font weight",     int,   1,   99,  1),

    # ---- Phrase column ----
    ("Phrases", "msgs_left",        "X (px)",          int,   0,  600, 1),
    ("Phrases", "msgs_font_size",   "Font size (pt)",  float, 1.0, 80.0, 0.5),
    ("Phrases", "msgs_font_weight", "Font weight",     int,   1,   99,  1),
    ("Phrases", "right_padding",    "Right padding (px)", int, 0, 400, 1),

    # ---- Row spacing ----
    ("Rows", "line_offset", "Line offset (px)", int, 1, 200, 1),
]


# Keys that should NOT be merged into FramelessOverlay.style — they
# either live elsewhere (window geometry) or are meta-controls.
GEOMETRY_KEYS = {"left", "top", "width", "height"}
META_KEYS     = {"interface_scale"}


# -----------------------------------------------------------------------------
# Re-usable "slider + spin-box" widget
# -----------------------------------------------------------------------------
class ParamControl(QWidget):
    """Label + slider + spin box bound to the same numeric value.

    Emits the parent's `on_change(key, value)` whenever the value
    changes. Internally avoids feedback loops via blockSignals.
    """

    def __init__(self, key, label, vtype, vmin, vmax, step, value, on_change):
        super().__init__()
        self.key = key
        self.vtype = vtype
        self.vmin, self.vmax, self.step = vmin, vmax, step
        self.on_change = on_change

        # Slider works on ints. For floats we scale by 1/step.
        if vtype is float:
            self._scale = max(1, int(round(1.0 / step)))
        else:
            self._scale = 1

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.label = QLabel(label)
        self.label.setMinimumWidth(180)
        self.label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        layout.addWidget(self.label)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(int(round(vmin * self._scale)))
        self.slider.setMaximum(int(round(vmax * self._scale)))
        self.slider.setSingleStep(1)
        layout.addWidget(self.slider, 1)

        if vtype is float:
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(max(1, len(str(step).split('.')[-1])) if '.' in str(step) else 2)
            self.spin.setSingleStep(step)
        else:
            self.spin = QSpinBox()
            self.spin.setSingleStep(int(step))
        self.spin.setMinimum(vmin)
        self.spin.setMaximum(vmax)
        self.spin.setMinimumWidth(90)
        layout.addWidget(self.spin)

        self.set_value(value, emit=False)

        self.slider.valueChanged.connect(self._on_slider)
        self.spin.valueChanged.connect(self._on_spin)

    # ---- internal ----
    def _on_slider(self, raw):
        v = raw / self._scale if self.vtype is float else int(raw)
        self.spin.blockSignals(True)
        self.spin.setValue(v)
        self.spin.blockSignals(False)
        self.on_change(self.key, v)

    def _on_spin(self, v):
        raw = int(round(v * self._scale)) if self.vtype is float else int(v)
        self.slider.blockSignals(True)
        self.slider.setValue(raw)
        self.slider.blockSignals(False)
        self.on_change(self.key, v)

    # ---- public ----
    def set_value(self, value, emit=True):
        if value is None:
            return
        if self.vtype is float:
            value = float(value)
            raw = int(round(value * self._scale))
        else:
            value = int(value)
            raw = value

        self.slider.blockSignals(True)
        self.spin.blockSignals(True)
        self.slider.setValue(raw)
        self.spin.setValue(value)
        self.slider.blockSignals(False)
        self.spin.blockSignals(False)

        if emit:
            self.on_change(self.key, value)


# -----------------------------------------------------------------------------
# Environment detection
# -----------------------------------------------------------------------------
def detect_environment():
    """Collect everything we know about the current display setup.

    Stored alongside every preset so that the data is enough to later
    fit an adaptation formula across (resolution, HUD scale, DPI).
    """
    screen = QApplication.primaryScreen()
    geom = screen.geometry()
    size = screen.size()

    try:
        dpr = float(screen.devicePixelRatio())
    except Exception:
        dpr = 1.0

    try:
        logical_dpi  = float(screen.logicalDotsPerInch())
        physical_dpi = float(screen.physicalDotsPerInch())
    except Exception:
        logical_dpi = physical_dpi = 96.0

    windows_scale_percent = int(round(logical_dpi / 96.0 * 100))

    return {
        "resolution":           [geom.width(), geom.height()],
        "logical_size":         [size.width(), size.height()],
        "device_pixel_ratio":   dpr,
        "logical_dpi":          logical_dpi,
        "physical_dpi":         physical_dpi,
        "windows_scale_percent": windows_scale_percent,
    }


# -----------------------------------------------------------------------------
# Preset I/O
# -----------------------------------------------------------------------------
def load_presets():
    if not os.path.exists(PRESETS_PATH):
        return {"version": 1, "presets": {}}
    try:
        with open(PRESETS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "presets" not in data:
            data["presets"] = {}
        return data
    except Exception as exc:
        print(f"[tuner] failed to load presets: {exc}")
        return {"version": 1, "presets": {}}


def save_presets(data):
    with open(PRESETS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -----------------------------------------------------------------------------
# Main control window
# -----------------------------------------------------------------------------
class TunerWindow(QWidget):
    def __init__(self, overlay: FramelessOverlay):
        super().__init__()
        self.overlay = overlay
        self.setWindowTitle("RLQC overlay tuner")
        self.resize(620, 880)

        self.environment   = detect_environment()
        self.presets_db    = load_presets()
        self.param_widgets: "OrderedDict[str, ParamControl]" = OrderedDict()

        # Current values for everything the user can edit. Seeded from
        # the running overlay and the OVERLAY_POSITION constant.
        self.values = {
            "left":   OVERLAY_POSITION["left"],
            "top":    OVERLAY_POSITION["top"],
            "width":  OVERLAY_POSITION["width"],
            "height": OVERLAY_POSITION["height"],
            "interface_scale": int(DEFAULT_INTERFACE_SCALE),
        }
        self.values.update(self.overlay.style)

        # Snapshot of "factory defaults" so the Reset button works.
        self._defaults = dict(self.values)
        self._defaults.update(self.overlay.DEFAULT_STYLE)

        self._build_ui()
        self._apply_overlay_values(self.values)

    # ----- UI assembly -----
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        outer.addWidget(self._build_info_panel())
        outer.addWidget(self._build_preset_bar())
        outer.addWidget(self._build_scroll_area(), 1)
        outer.addWidget(self._build_metadata_panel())
        outer.addWidget(self._build_footer())

    def _build_info_panel(self):
        env = self.environment
        info_text = (
            f"<b>Resolution:</b> {env['resolution'][0]}×{env['resolution'][1]} px"
            f"   |   <b>Windows scale:</b> {env['windows_scale_percent']}% "
            f"(logical DPI {env['logical_dpi']:.0f})"
            f"   |   <b>Device pixel ratio:</b> {env['device_pixel_ratio']:.2f}"
        )
        lbl = QLabel(info_text)
        lbl.setStyleSheet("QLabel { padding: 6px; background: #f2f4f7; border-radius: 4px; }")
        lbl.setWordWrap(True)
        return lbl

    def _build_preset_bar(self):
        box = QGroupBox("Presets")
        lay = QHBoxLayout(box)

        self.preset_combo = QComboBox()
        self._refresh_preset_combo()
        lay.addWidget(self.preset_combo, 1)

        btn_load = QPushButton("Load")
        btn_load.clicked.connect(self._on_load_preset)
        lay.addWidget(btn_load)

        btn_save = QPushButton("Save / overwrite")
        btn_save.clicked.connect(self._on_save_preset)
        lay.addWidget(btn_save)

        btn_delete = QPushButton("Delete")
        btn_delete.clicked.connect(self._on_delete_preset)
        lay.addWidget(btn_delete)

        btn_reset = QPushButton("Reset to defaults")
        btn_reset.clicked.connect(self._on_reset)
        lay.addWidget(btn_reset)

        return box

    def _build_scroll_area(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(4, 4, 4, 4)
        host_layout.setSpacing(10)

        # Group params by their first column.
        groups: "OrderedDict[str, list]" = OrderedDict()
        for group, key, label, vtype, vmin, vmax, step in PARAMS:
            groups.setdefault(group, []).append((key, label, vtype, vmin, vmax, step))

        for gname, items in groups.items():
            gb = QGroupBox(gname)
            form = QVBoxLayout(gb)
            form.setSpacing(4)
            for key, label, vtype, vmin, vmax, step in items:
                ctrl = ParamControl(
                    key, label, vtype, vmin, vmax, step,
                    value=self.values.get(key, self._defaults.get(key, 0)),
                    on_change=self._on_param_changed,
                )
                self.param_widgets[key] = ctrl
                form.addWidget(ctrl)
            host_layout.addWidget(gb)

        host_layout.addStretch(1)
        scroll.setWidget(host)
        return scroll

    def _build_metadata_panel(self):
        box = QGroupBox("Preset metadata (saved with the preset)")
        form = QFormLayout(box)

        self.meta_name = QLineEdit()
        self.meta_name.setPlaceholderText("e.g. 3440x1440 hud100 winscale100")
        form.addRow("Name:", self.meta_name)

        self.meta_hud = QSpinBox()
        self.meta_hud.setMinimum(50)
        self.meta_hud.setMaximum(100)
        self.meta_hud.setValue(100)
        self.meta_hud.setSuffix(" %")
        form.addRow("Game HUD scale:", self.meta_hud)

        self.meta_notes = QPlainTextEdit()
        self.meta_notes.setFixedHeight(60)
        self.meta_notes.setPlaceholderText("Anything worth remembering (monitor, in-game resolution, etc.)")
        form.addRow("Notes:", self.meta_notes)

        # Suggest preset name automatically when HUD scale changes
        self.meta_hud.valueChanged.connect(self._suggest_preset_name)
        self._suggest_preset_name()

        return box

    def _build_footer(self):
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)

        self.live_apply = QCheckBox("Live apply to overlay (recommended)")
        self.live_apply.setChecked(True)
        lay.addWidget(self.live_apply)

        btn_repaint = QPushButton("Force repaint")
        btn_repaint.clicked.connect(self.overlay.update)
        lay.addWidget(btn_repaint)

        btn_dump = QPushButton("Copy current as JSON")
        btn_dump.clicked.connect(self._on_copy_json)
        lay.addWidget(btn_dump)

        btn_export = QPushButton("Export presets...")
        btn_export.clicked.connect(self._on_export)
        lay.addWidget(btn_export)

        return box

    # ----- value flow -----
    def _on_param_changed(self, key, value):
        self.values[key] = value
        if self.live_apply.isChecked():
            self._apply_overlay_values({key: value})

    def _apply_overlay_values(self, partial):
        """Apply a partial dict of values to the live overlay."""
        # geometry update
        geo_changed = any(k in partial for k in GEOMETRY_KEYS)
        if geo_changed:
            self.overlay.set_geometry_dict({k: self.values[k] for k in GEOMETRY_KEYS})

        if "interface_scale" in partial:
            self.overlay.set_scale(self.values["interface_scale"] / 100.0)

        style_updates = {
            k: v for k, v in partial.items()
            if k not in GEOMETRY_KEYS and k not in META_KEYS
        }
        if style_updates:
            self.overlay.update_style(**style_updates)

        if not self.overlay.isVisible():
            self.overlay.show()

    def _push_all_values_to_overlay(self):
        self._apply_overlay_values(self.values)

    def _push_all_values_to_widgets(self):
        for key, ctrl in self.param_widgets.items():
            ctrl.set_value(self.values.get(key, self._defaults.get(key)), emit=False)

    # ----- preset operations -----
    def _refresh_preset_combo(self):
        self.preset_combo.clear()
        for name in sorted(self.presets_db.get("presets", {}).keys()):
            self.preset_combo.addItem(name)

    def _suggest_preset_name(self):
        env = self.environment
        suggestion = (
            f"{env['resolution'][0]}x{env['resolution'][1]}"
            f"_hud{self.meta_hud.value()}"
            f"_winscale{env['windows_scale_percent']}"
        )
        if not self.meta_name.text().strip():
            self.meta_name.setText(suggestion)
        else:
            self.meta_name.setPlaceholderText(suggestion)

    def _current_preset_payload(self):
        return {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "environment": dict(self.environment),
            "metadata": {
                "game_hud_scale": int(self.meta_hud.value()),
                "notes": self.meta_notes.toPlainText().strip(),
            },
            "interface_scale": int(self.values["interface_scale"]),
            "window": {k: int(self.values[k]) for k in GEOMETRY_KEYS},
            "style": {
                k: self.values[k]
                for k in self.overlay.DEFAULT_STYLE.keys()
            },
        }

    def _on_save_preset(self):
        name = self.meta_name.text().strip() or self.meta_name.placeholderText().strip()
        if not name:
            QMessageBox.warning(self, "Save preset", "Preset name is empty.")
            return
        if name in self.presets_db["presets"]:
            ans = QMessageBox.question(
                self, "Overwrite?",
                f"A preset named '{name}' already exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if ans != QMessageBox.Yes:
                return

        self.presets_db["presets"][name] = self._current_preset_payload()
        save_presets(self.presets_db)
        self._refresh_preset_combo()
        idx = self.preset_combo.findText(name)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        QMessageBox.information(self, "Preset saved", f"Saved as '{name}' in\n{PRESETS_PATH}")

    def _on_load_preset(self):
        name = self.preset_combo.currentText()
        if not name:
            return
        preset = self.presets_db["presets"].get(name)
        if not preset:
            return

        # restore values
        self.values["interface_scale"] = int(preset.get("interface_scale", 100))
        for k in GEOMETRY_KEYS:
            self.values[k] = int(preset["window"].get(k, self._defaults[k]))
        for k, v in preset.get("style", {}).items():
            self.values[k] = v

        # restore metadata
        md = preset.get("metadata", {})
        self.meta_name.setText(name)
        if "game_hud_scale" in md:
            self.meta_hud.setValue(int(md["game_hud_scale"]))
        self.meta_notes.setPlainText(md.get("notes", ""))

        # push to UI + overlay
        self._push_all_values_to_widgets()
        self._push_all_values_to_overlay()

    def _on_delete_preset(self):
        name = self.preset_combo.currentText()
        if not name:
            return
        ans = QMessageBox.question(
            self, "Delete preset", f"Delete preset '{name}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return
        self.presets_db["presets"].pop(name, None)
        save_presets(self.presets_db)
        self._refresh_preset_combo()

    def _on_reset(self):
        for k, v in self._defaults.items():
            self.values[k] = v
        self._push_all_values_to_widgets()
        self._push_all_values_to_overlay()

    def _on_copy_json(self):
        payload = self._current_preset_payload()
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copied", "Current preset JSON copied to clipboard.")

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export presets", "rlqc_presets_export.json", "JSON (*.json)"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.presets_db, f, indent=2, ensure_ascii=False)
        QMessageBox.information(self, "Exported", f"Wrote {path}")

    # Make sure pressing the system close button shuts down everything
    def closeEvent(self, event):
        try:
            self.overlay.close()
        except Exception:
            pass
        super().closeEvent(event)
        QApplication.quit()


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------
def _force_topmost(qwidget):
    """Best-effort: keep `qwidget` on top via Win32 SetWindowPos.

    Same trick the main script uses for the boss-mode overlay so it
    sits above Rocket League / browsers / IDE etc.
    """
    try:
        import win32con
        import win32gui
        hwnd = int(qwidget.winId())
        win32gui.SetWindowPos(
            hwnd, win32con.HWND_TOPMOST,
            0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
        )
    except Exception as exc:
        print(f"[tuner] SetWindowPos failed: {exc}")


def main():
    # Build the application BEFORE creating any QScreen-dependent
    # things (e.g. detect_environment uses QApplication.primaryScreen).
    app = QApplication(sys.argv)

    # Live overlay positioned at the same coords as the main script.
    initial_scale = float(DEFAULT_INTERFACE_SCALE) / 100.0
    wp = {
        'left':   int(OVERLAY_POSITION['left']),
        'top':    int(OVERLAY_POSITION['top']),
        'width':  int(OVERLAY_POSITION['width']),
        'height': int(OVERLAY_POSITION['height']),
    }
    overlay = FramelessOverlay(wp, scale=initial_scale)
    overlay.set_content('COMPLIMENTS', [
        "Nice one!",
        "Great pass!",
        "Thanks for the save!",
        "What a save!",
    ])
    overlay.show()
    _force_topmost(overlay)

    # Control panel — dock it to the right edge of the primary screen
    # so it doesn't overlap the overlay being calibrated.
    tuner = TunerWindow(overlay)
    screen = app.primaryScreen().availableGeometry()
    tw, th = tuner.width(), tuner.height()
    tuner.move(max(screen.left(), screen.right() - tw - 20),
               max(screen.top(),  screen.top() + 20))
    tuner.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
