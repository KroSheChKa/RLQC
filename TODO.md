# RLQC — TODO / Notes

Living document. Add new entries to the top.

---

## 1. Make the overlay pixel-perfectly match the in-game quick chat

Status: pending — won't tackle right now, but worth doing properly.

### What's wrong today
The current edge fades in `visuals.py` (`paintEvent`) are simple
**linear** `QLinearGradient`s: alpha goes from 255 → 0 in a straight
line. In Rocket League's real quick chat the falloff is visibly
**softer / non-linear** — it stays nearly opaque longer near the
content area and then ramps off more gently. The right-edge fade is
the most noticeable: starts quite abruptly, whereas in the game it
breathes in much more smoothly.

### Why this is fixable cheaply
The overlay's background is **static** as long as the window size and
the style don't change. So we can pay an expensive one-off render
cost and then blit a cached pixmap on every `paintEvent`. There is no
per-frame cost.

### Plan

1. **Switch from linear to a non-linear falloff curve.**

   Options, from cheapest to nicest:

   - Multi-stop `QLinearGradient` with hand-tuned stops. E.g. for
     the right edge instead of `(0.0, 255), (1.0, 0)` use something
     like `(0.0, 255), (0.45, 255), (0.65, 180), (0.85, 60), (1.0, 0)`
     so the panel stays solid for the first 45% of the fade region
     before easing out.
   - **Smootherstep** curve sampled into 16–32 gradient stops:
     ```
     def smootherstep(t):  # 6t^5 - 15t^4 + 10t^3
         return t * t * t * (t * (t * 6 - 15) + 10)
     ```
     Build a `QLinearGradient` whose `setColorAt(t, alpha=255*(1-smootherstep(t)))`
     for `t = 0, 1/N, 2/N, ..., 1`. This already matches the eye much
     better than linear.
   - **Gaussian-blurred mask.** Render a fully-opaque black rectangle
     of the design size into an off-screen `QPixmap`, apply a
     `QGraphicsBlurEffect` along the edges (e.g. radius 20 on the
     right, 8 on top/bottom, 20 on the left). The blurred image *is*
     the panel — paintEvent just draws this cached pixmap. Closest to
     "natural" RL falloff because the game itself basically does a
     blurred-edge sprite.

2. **Cache the result.** Invalidate the cached pixmap only when
   `self.style` keys involved in the background change (`bg_alpha`,
   `fade_*`, geometry). Otherwise reuse — paintEvent becomes a single
   `drawPixmap` for the panel.

3. **Calibration workflow** (the user's idea, written down):
   - Open Rocket League on a uniform-colour map (e.g. workshop room
     with a flat green/grey wall) and press `T` to bring up the
     real quick-chat panel.
   - Take a 1:1 screenshot. Sample alpha across the right edge at a
     fixed Y row. Plot.
   - Fit one of the curves above to that sample (linear regression in
     `1 - alpha`, or just visual tuning of the multi-stop gradient).
   - Save the fitted curve as the default `style` entry (e.g.
     `fade_right_curve = "smootherstep"` plus a few coefficients).

4. **Make the curve switchable from the tuner.** Add a combo box
   "Right fade curve: linear / smootherstep / multi-stop / blurred"
   so future calibration is a few clicks, not a rebuild.

5. **Side benefit:** once the static panel is a cached pixmap, the
   already-redundant double `strokePath` pass on the category header
   and the 8-layer glow can also be baked into a per-category pixmap,
   only redrawing the phrase text on each repaint. Big perf win at
   high INTERFACE_SCALE.

### Files involved
- `visuals.py` — `paintEvent`, new helper `_render_background()`.
- `tuner.py` — `PARAMS` and a new combo box for the curve type.

---

## 2. Automatic adaptation to arbitrary (resolution × HUD scale × Windows DPI)

Status: pending — collecting calibration data. Reference points live
in `presets/reference_presets.json` (committed). User-generated working
presets live in `overlay_presets.json` (gitignored).

### Current state
The whole UI (window geometry + paint params in `visuals.py`) is
hand-calibrated against 1920×1080. It matches the in-game quick chat
pixel-perfect on Full HD regardless of `INTERFACE_SCALE`. On other
resolutions (3440×1440 ultrawide, 2560×1440 QHD, 3840×2160 4K) the
menu still draws but everything is slightly off because Rocket League
scales its HUD with screen **height**, while our coordinates are
fixed.

### THREE independent inputs we must combine

The final scale depends on three knobs that the user (or the OS)
controls separately. Conflating them is what bit us before:

  1. **Screen resolution** — comes from `QApplication.primaryScreen()
     .geometry().height()`. Auto-detected, no user input needed.
     RL's HUD scales with height; ultrawides do NOT widen the menu.
  2. **Windows display scale** — comes from
     `screen.logicalDotsPerInch() / 96`. Auto-detected.
     A 1920×1200 laptop running at 125% Windows scale draws a smaller
     "logical" canvas than the same panel at 100%, so the menu must
     compensate.
  3. **In-game HUD scale** (50..100, integer percent) — CANNOT be
     read from RL at all. Must be provided by the user. This is the
     reason we need the first-run wizard in #2b below.

### Plan (dynamic, NOT presets per resolution)

1. Read the auto-detectable inputs at `overlay_init()` time:
   ```
   h_px         = QApplication.primaryScreen().geometry().height()
   win_scale_pc = round(screen.logicalDotsPerInch() / 96 * 100)
   ```
2. Read the user-provided HUD scale from config / wizard output:
   `hud_pc` (integer in 50..100).
3. Compute the final per-axis multipliers:
   ```
   resolution_factor = h_px / BASE_RESOLUTION[1]   # 1080
   windows_factor    = win_scale_pc / 100
   hud_factor        = hud_pc / 100
   final_scale       = resolution_factor * hud_factor * windows_factor
   ```
   (May need a separate horizontal factor if data shows ultrawides
   need an explicit horizontal correction — see Data points below.)
4. Apply `final_scale` to BOTH window geometry (left / top / width /
   height in OVERLAY_POSITION) AND every value inside
   `FramelessOverlay.DEFAULT_STYLE`. This is what `scale_factor`
   already does for `style` — we just need to also stretch the
   window box and the anchor.

   Note: `selected_letter_spacing` is one of the keys that **does**
   scale (it's a per-pixel-density value, calibrated by eye in the
   tuner). The other two parts of the "selected" look — colour
   (`SELECTED_COLOR = #FFFFFF`) and weight (`SELECTED_WEIGHT = 75`)
   — are intentionally NOT in the style dict because they are
   game-fixed; the auto-adaptation formula must leave them alone.

### Data points (calibration log)

Each new tuner-saved preset that we deem "pixel-perfect" should also
be added to `presets/reference_presets.json` so the file accumulates
real measurements. Once we have ≥ 3 points spanning different
resolutions and HUD scales at the same Windows DPI, we can plot
each style key against (height, hud) and verify (or correct) the
formula above. Already-calibrated:

  - **3440×1440 / HUD 100 / WinScale 100** — saved 2026-05-22, see
    `presets/reference_presets.json`. Pixel-perfect except for the
    right-edge fade (linear gradient — known issue, see #1).

Still needed (priority order):

  - 1920×1080 / HUD 100 / WinScale 100 (the original baseline that the
    code claims to match — verify, sanity check).
  - 1920×1200 / HUD 100 / WinScale 125 (laptop case; the +120 px in
    height combined with Windows 125% scaling is exactly the case
    that's most likely to expose a bug in the formula).
  - 3440×1440 / HUD 75 and HUD 50, WinScale 100 (varies only HUD).
  - 1920×1080 / HUD 75 and HUD 50, WinScale 100 (cross-check HUD axis
    on the baseline resolution).

### Sanity checks when implementing

  - 1920×1080 / HUD 100 / WinScale 100: no visual change vs. today.
  - 3440×1440 / HUD 100 / WinScale 100: matches the saved preset
    `3440x1440_hud100_winscale100` byte-for-byte.
  - Any resolution × HUD ∈ {50, 75, 100} × WinScale ∈ {100, 125, 150}:
    matches the in-game quick chat at the same HUD-scale setting.

---

## 2b. First-run wizard — collect inputs we can't auto-detect

Status: pending. Blocks #2 from being usable for end-users.

`hud_scale` (the in-game HUD slider) is impossible to read from
outside the game. We need a tiny one-time UI to ask the user. The
absence of this is the single reason #2 is currently a "developer
tool" only.

### Plan

1. On every script start (or only when no `user_settings.json` exists
   yet), check for the saved HUD value. If missing → spawn the
   wizard before `main()` continues.
2. Wizard window (PyQt5, small, modal-ish):
   - Friendly explainer: "We need to know your in-game HUD scale.
     Open Rocket League, Settings → Display → HUD scale. Enter the
     value you see below."
   - `QSpinBox` 50..100, default 100.
   - Optional toggle "I never change my HUD scale — remember this".
   - "Save & continue" button → writes the value to e.g.
     `user_settings.json` next to the script.
3. Add a manual entry point — keystroke / CLI flag / menu item —
   to re-open the wizard later when the user changes their HUD.
4. Plug the result into the formula in #2 above. If a saved value is
   present we skip the wizard silently.

### Where to store
`user_settings.json` (gitignored, like `overlay_presets.json`):
```json
{
  "hud_scale": 100,
  "saved_at": "..."
}
```

---

## 3. Bugs / nice-to-haves from earlier review (already fixed unless noted)

All of these were addressed earlier — kept here as a changelog:

- `VkKeyScan_` was used without masking modifier bits → fixed
  (`& 0xFF`) in `paste_in_chat`.
- `sleep_key` was a busy-loop pegging the CPU → replaced with a
  high-precision interruptible sleep using `winmm.timeBeginPeriod(1)`
  and `time.perf_counter`.
- `keyboard = Controller()` was created only under `__main__` → moved
  to module scope.
- Pseudo `while ... return` loop in `paste_in_chat` → cleaned up.
- Dead CapsLock toggle code → removed.
- `safe_exit` now releases only the keys actually held down.
- Random training-map codes restored via `{shooting_code}` /
  `{defence_code}` placeholders.
- Comment trail explaining why INFORMATIONAL goes to party chat.
- `shift_symbols` was missing `|`.
- Font paths normalised through `os.path.join`.
- `INTERFACE_SCALE` now propagates to fonts/paddings/glow inside
  `paintEvent` (was previously only scaling the window box).
- `FramelessOverlay.DEFAULT_STYLE` introduced so all magic numbers
  are editable at runtime (used by `tuner.py`).

---

## 3b. Slim down DEFAULT_STYLE — extract truly-constant values

Status: pending. Wait until enough reference presets are collected.

Once we have several `presets/reference_presets.json` entries we can
diff them and see which `style` keys are **identical across every
preset** (i.e. they don't actually depend on resolution / HUD scale /
Windows DPI — the user never touched them in the tuner either).

Those keys should leave `FramelessOverlay.DEFAULT_STYLE` and become
plain module-level constants in `visuals.py`. Benefits:

- `style` dict shrinks → tuner only shows knobs that actually matter.
- The auto-adaptation formula in #2 needs to scale fewer values.
- Less noise in saved presets — JSON stays small and meaningful.

Likely candidates already, based on the first preset (untouched
fields):
  * `color_blue`, `color_white`
  * `outline_width`, `glow_layers`, `glow_max_width`, `glow_base_alpha`
  * `bg_alpha`
  * `nums_font_weight`, `msgs_font_weight`

Don't act on the list above yet — confirm against ≥ 2 more presets
before removing them. The whole point is to base the decision on
real data, not guesses.

---

## 4. Pending small things (not urgent)

- Tuner: add an "auto-fit window to scaled content" toggle so
  changing INTERFACE_SCALE in the panel also resizes the overlay
  window proportionally. Currently width/height are independent
  knobs.
- Tuner: keyboard shortcuts to nudge `left/top/width/height` by 1 px
  (arrow keys when a window-group widget has focus). Faster than the
  slider for the last pixel.
- Once **#2** is implemented, drop the `BASE_RESOLUTION` constant
  from `config.py` if it's no longer referenced.

