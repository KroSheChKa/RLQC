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

## 2. Automatic adaptation to non-Full-HD resolutions

Status: pending — design notes already in `config.py`. Implementation
deferred until enough tuner presets are collected (see
`overlay_presets.json`).

### Current state
The whole UI (window geometry + paint params in `visuals.py`) is
hand-calibrated against 1920×1080. It matches the in-game quick chat
pixel-perfect on Full HD regardless of `INTERFACE_SCALE`. On other
resolutions (3440×1440 ultrawide, 2560×1440 QHD, 3840×2160 4K) the
menu still draws but everything is slightly off because Rocket League
scales its HUD with screen **height**, while our coordinates are
fixed.

### Plan (dynamic, NOT presets per resolution)

1. At `overlay_init()` in `RLQuickChat.py`, query the target
   monitor's pixel height via
   `QApplication.primaryScreen().geometry().height()`.
2. Compute `resolution_factor = current_height / BASE_RESOLUTION[1]`.
   Height-based, because RL's HUD scales with height; on ultrawides
   the menu must NOT grow horizontally.
3. Final scale used by `FramelessOverlay`:
   ```
   final_scale = resolution_factor * (INTERFACE_SCALE / 100)
   ```
   `INTERFACE_SCALE` keeps its current meaning (the user's HUD-scale
   slider 50..100), the resolution multiplier is applied transparently
   underneath.
4. Apply the same factor to `OVERLAY_POSITION['top']`/`'left'` so the
   menu stays anchored to the same relative spot on screen.

### Data needed before implementing
Run `python tuner.py` on a few combinations and save presets:

- Full HD 1920×1080, HUD = 50 / 75 / 100, Windows scale = 100% / 125%
- QHD 2560×1440, HUD = 50 / 75 / 100, Windows scale = 100% / 125%
- Ultrawide 3440×1440, HUD = 50 / 75 / 100, Windows scale = 100% / 125%

With those points we can plot `(value vs HUD)` and `(value vs height)`
and confirm the formula above (or pick a slightly different one).

### Sanity checks when implementing
- Full HD 100%: no visual change vs. today.
- QHD 100%: menu grows ~1.33×, still aligned with in-game chat.
- Ultrawide 1440p: menu grows ~1.33× (height-based, NOT stretched
  horizontally).
- Any resolution × INTERFACE_SCALE ∈ {50, 75, 100}: matches the
  in-game quick chat at the same HUD-scale setting.

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

