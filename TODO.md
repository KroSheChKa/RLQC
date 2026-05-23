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

> **Status of the Windows-DPI axis (May 2026):** currently parked,
> NOT applied. Both `RLQuickChat.py` and `tuner.py` set
> `Qt.AA_DisableHighDpiScaling = True` before constructing their
> QApplication, so the overlay renders at physical pixel size on
> every machine regardless of the OS scale slider. This is the
> correct behaviour for now because Rocket League itself ignores
> the Windows scale — a preset has to be portable between users
> running 100% / 125% / 150%. The detected Windows scale is still
> recorded in every saved preset (`environment.windows_scale_percent`
> in `overlay_presets.json` / `presets/reference_presets.json`) so
> we can bring it back into the formula here once there's data
> showing it actually needs to participate. Until then: collect,
> don't apply.


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
- "First message of the session gets its opening letters chopped
  off" fixed by warming up the input plumbing during the F1-wait
  phase (`_input_subsystem_warmup` in `RLQuickChat.py`) and
  applying a longer cold-path sleep on the very first
  `paste_in_chat()`.
- Phrase / training-code picking switched from naive
  `random.choice()` to a `ShuffleBag` (`pseudo_random.py`) —
  shuffle, walk through the pool, reshuffle on exhaustion, guard
  the seam. Same statistical fairness, but no back-to-back
  repeats so the user perceives the variety they expected when
  they wrote N phrases for a single chord.

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

## 4. Frictionless first-run setup (auto-detect + warn)

Status: **shipped (read-only path)**. Phase A (discovery) and
Phase B (preflight checks + warnings + auto-apply detected key
bindings) are live. The "modify the user's game config" path
was scoped OUT — see "Why we don't modify game files" below.

### What's live today

  * `rl_config.py` — locates the RL Config folder
    (Documents → OneDrive fallback), parses `TAInput.ini`'s
    `PCBindings=( Action="…", Key="…" )` rows, picks the active
    preset section, translates UE3 key names to Win32 VK codes.
  * `preflight.py` — read-only checks built on top of the
    discovery layer:
      - display-mode warning (exclusive fullscreen detected),
      - quick-chat key-collision warning,
      - graceful "no config dir found" warning.
  * `RLQuickChat.py:main()` runs the preflight before the F1 wait:
    detected bindings get auto-applied to `key_bindings` (RL wins
    on conflict), warnings are shown both on stdout and via a
    QMessageBox with Continue / Quit buttons. The user is in
    control — we never force-exit on a warning.

### Why we don't modify game files

The original Phase B plan involved writing to `TAGame.ini` to
flip in-game Quick Chat to "Off" while RLQC ran, then restoring
it on exit. Three problems killed that idea:

  1. **`TAGame.ini` may not exist locally.** On the test machine
     it didn't, despite the user being a heavy player. Strong
     signal the Quick-Chat-permission setting is stored in the
     Psyonix cloud profile, not on disk. We can't touch that from
     outside the game.
  2. **Crash recovery is fiddly.** Writing → playing → restoring
     needs a marker file, RL-running detection, locked-file
     handling, etc. All survivable, but a lot of moving parts
     for a feature whose value is "saves the user one mouse
     click in RL's settings".
  3. **The warning path is better UX anyway.** A clear "your
     in-game Quick Chat overlaps with RLQC's keys — turn it off
     here: Settings → Chat → Quick Chat → Off" gives the user
     full context AND keeps them in charge of their own game.

So the scope of #4 now ends at "read, detect, warn". The
write-back path is intentionally not on this list — if a future
need surfaces (e.g. someone really wants automatic disable of
Quick Chat), the conversation starts from scratch.

### Remaining work in this area

  * **First-run wizard for HUD scale (#2b).** The one input we
    can't auto-detect. Currently the user has to edit
    `INTERFACE_SCALE` in `config.py`. A 5-second one-time popup
    on first launch would solve this.
  * **Runtime borderless detection.** `TASystemSettings.ini` is
    read at script start, but the user might change RL's display
    mode mid-session. A more robust check is
    `GetWindowLong(rl_hwnd, GWL_STYLE)` once we know the RL HWND
    (find via `EnumWindows` + window-title match). Not urgent —
    the disk check catches 95% of cases.
  * **Verify the `TAGame.ini`-vs-profile hypothesis on more
    installs.** If somebody is reading this and they have a
    populated `TAGame.ini` with chat-permission settings inside,
    please open an issue. Current evidence is one-machine.

---

## 4b. Frictionless first-run setup (the OLD plan, archived)

Status: **abandoned**, kept here only so we don't reinvent it.

The original plan was to MODIFY the user's RL config files to
auto-disable in-game Quick Chat on start and restore on exit.
After Phase A discovery we replaced that with the read-only
warning approach above. See "Why we don't modify game files"
under #4 for the rationale. The full original spec is preserved
below in case the situation changes (e.g. RL starts persisting
chat settings to disk again).

### Goal

A new user clones the repo, runs `RLQuickChat.py`, and the script
just works — no manual editing of `config.py`, no hunting through
Rocket League settings, no "did I remap the right key?". The ONE
input we cannot avoid asking for is the in-game HUD scale (50..100);
everything else should be auto-detected, auto-applied on start,
and auto-restored on exit.

### Prerequisites the user still owns

These are real-world constraints we can't engineer around, only
clearly communicate (the wizard from #2b is a good home for the
warnings):

  * **Rocket League must run in Borderless Windowed mode.** True
    exclusive fullscreen swallows every other window on the
    monitor, including ours. Borderless is identical for the user
    visually and lets Qt's `WS_EX_TOPMOST | WS_EX_LAYERED |
    WS_EX_TRANSPARENT` window sit on top.
  * **In-game text chat must be enabled** (Settings → Chat →
    anything except "Off"). Without it our `paste_in_chat()` has
    nothing to open.

**Research item — CLOSED (May 2026).** Question was: does PowerToys
"Always on Top" (Win+Ctrl+T) actually beat exclusive fullscreen so
we could drop the borderless requirement? Verdict: **no, the trick
isn't a trick** — PowerToys just sets `WS_EX_TOPMOST` on the target
HWND, which is *exactly* what our overlay already does via
`Qt.WindowStaysOnTopHint`.

What that flag actually does:

  * **Borderless fullscreen** (DWM-composed maximised window, no
    borders): `WS_EX_TOPMOST` wins. The pinned window draws above
    the "fullscreen" content. This is the case PowerToys users
    report in microsoft/PowerToys#15391 (where they expected
    fullscreen to take precedence over Always-on-Top, but it
    didn't). It's also the case we rely on for our overlay today.
  * **Exclusive fullscreen** (DXGI/D3D swap chain in fullscreen
    mode, bypasses the desktop compositor): no extended-style flag
    helps. The GPU swap chain owns the scanout and the compositor
    is out of the picture. PowerToys can't draw on top of this
    either — its docs even ship a "Do not activate when Game Mode
    is on" toggle precisely because it's a hopeless case.

Consequence for us: Rocket League's `Settings → Video → Display
Mode → Fullscreen` is exclusive fullscreen and IS a hard wall.
`Borderless` works because it's DWM-composed underneath. The
borderless requirement at the top of this section is therefore
a real constraint, not laziness — keep it in the README, surface
it in the first-run wizard.

### Inputs we can — and should — auto-detect

The Rocket League config files live at a fixed, install-method-
agnostic path on every machine:

```
%USERPROFILE%\Documents\My Games\Rocket League\TAGame\Config\
```

That's the same path whether the game came from Steam, Epic or any
other launcher — Unreal Engine writes per-user config there. We
expand it with `os.path.expanduser("~/Documents/My Games/...")` and
also try the OneDrive-redirected `~/OneDrive/Documents/...` as a
fallback.

Files of interest inside that folder:

  * **`TASystemSettings.ini`** — video / system settings. Tells us
    the user's current resolution and (indirectly) whether they're
    in borderless / fullscreen mode. Read-only for us.
  * **`TAGame.ini`** — gameplay settings, including the in-game
    Quick Chat permission level (Off / Friends / Teammates /
    Everyone) and text-chat permission. The pair of keys we need
    to flip on start and restore on exit. Read **and** write.
  * **`TAInput.ini`** — input bindings. We can read out which
    physical keys the user has currently mapped to Rocket League's
    own quick chat (the `Chat*` and `ChatPreset*` actions) and to
    text chat. Useful for two reasons:
      1. Show the right key glyph in our overlay automatically
         (no more "you must rebind to 1234 manually").
      2. Detect collisions: if the user's RL bindings clash with
         our `key_bindings` in `config.py`, warn them or auto-pick
         a non-conflicting set.

### What the script must do at start / exit

1. **Pre-flight (script start, before F1)**
   * Locate the Config folder. If missing → assume RL never ran
     once; show a clear error, abort.
   * Make timestamped backups of every file we plan to write:
     `TAGame.ini.bak-YYYYMMDD-HHMMSS`. Keep at most N backups (5?).
   * Snapshot the original values of the keys we'll modify into a
     small marker file next to the script (`config_backup.json`).
     This is what we restore from. Surviving a crash matters here.
   * Verify Rocket League is **not** currently running (it caches
     config in memory and won't pick up our changes mid-session).
     If running → either ask the user to close it or downgrade to
     "we'll apply on the next launch".

2. **Modify the user's game config**
   * `TAGame.ini` → set Quick Chat permission to **Off** so that
     pressing the category keys does NOT trigger BOTH the
     in-game quick chat AND our script.
   * `TAGame.ini` → ensure text chat permission is **not Off** so
     our typing path works.
   * That's it. No other writes for the MVP.

3. **Auto-fill `config.py` runtime values**
   * Read `TAInput.ini`, find the binds for `ChatPreset1..4`
     (category) and any sub-category actions; convert from
     Unreal's key names to Win32 VK codes; populate
     `key_bindings` in memory (do NOT write to `config.py` —
     keep the user's editable file untouched).
   * Same for `TEXT_CHAT_ALL` / `TEXT_CHAT_PARTY`.
   * If parsing fails for any reason, fall back to the values
     currently in `config.py`.

4. **Exit (safe_exit and crash path)**
   * Restore every modified value from `config_backup.json`.
   * Delete `config_backup.json`.
   * On the next launch, if `config_backup.json` is still present
     it means we crashed last time — auto-restore before doing
     anything else.

### Findings from the Phase A discovery pass (May 2026)

Ran `rl_config.py` against a real Steam-version install. What we
learned the hard way:

  * `TAInput.ini` does NOT use the generic UE3
    `Bindings=(Name=…,Command=…)` syntax. RL uses
    `PCBindings=( Action="…", Key="…" )` with field names that no
    UE3 doc mentions. Already handled in the parser.
  * There are MULTIPLE preset sections in `TAInput.ini`:
    `[ProjectX.ControlPreset_X]`, `[Standard ControlPreset_X]`,
    `[Legacy ControlPreset_X]`, `[OldClassic ControlPreset_X]`.
    The user-customised one is `[ProjectX.ControlPreset_X]`; the
    others are factory defaults shipped with the game. Picker
    priority is in `_PRESET_SECTIONS_PRIORITY`.
  * **`TAGame.ini` did NOT exist on the test machine** even though
    that user has been playing RL for years. Strong signal that the
    in-game "Quick Chat Off / Friends / Teammates / Everyone"
    setting is stored in the Psyonix profile (cloud), not in any
    local .ini. If that's the case across installs, the
    "auto-disable Quick Chat by editing TAGame.ini" plan above is
    dead in the water — we'd have to fall back to telling the user
    to either rebind RL's quick-chat keys (we can READ the
    current bindings, so we can at least *detect* the collision)
    or turn the in-game setting off themselves.
  * Phase B must FIRST verify on ≥ 3 installs whether anyone has a
    populated `TAGame.ini` containing chat-permission settings
    before we commit to writing to it. If profile-only confirmed,
    the writeable scope of #4 shrinks to "nothing on disk" and
    the feature becomes purely discovery-side.

### Open questions remaining

  * Borderless vs fullscreen detection: probably easier to do at
    runtime via `GetWindowLong(rl_hwnd, GWL_STYLE)` than by parsing
    `TASystemSettings.ini`, because the on-disk values can lag
    behind the live setting. Need to find the RL HWND first
    (`EnumWindows` + match by process name / window title).
  * Auto-fill of `key_bindings` from `discover_quick_chat_bindings()`:
    when do we apply the overrides? Easiest: at the top of
    `RLQuickChat.py:main()`, mutate the imported `key_bindings`
    dict in place, log what changed. Open question: should the
    user's existing `config.py` value take precedence over RL's,
    or the other way around? Initial gut feel: RL wins (because
    that's what the user actually presses in the game and the
    whole point of auto-detection is to remove the need to keep
    `config.py` in sync). Surface the override list on startup
    so it's never invisible.

### Safety / UX rules (non-negotiable)

  * Never write to a game config without making a backup first.
  * Never overwrite the user's `config.py` — auto-detected values
    live only in memory.
  * Surface every change in the README + a one-screen summary on
    first launch ("here's what I'm about to change in your game,
    [Cancel] / [Continue]"). The user has to actively opt in.
  * On crash → restore. On exit → restore. Period.

---

## 5. Pending small things (not urgent)

- Tuner: add an "auto-fit window to scaled content" toggle so
  changing INTERFACE_SCALE in the panel also resizes the overlay
  window proportionally. Currently width/height are independent
  knobs.
- Tuner: keyboard shortcuts to nudge `left/top/width/height` by 1 px
  (arrow keys when a window-group widget has focus). Faster than the
  slider for the last pixel.
- Once **#2** is implemented, drop the `BASE_RESOLUTION` constant
  from `config.py` if it's no longer referenced.

---

## 6. Gamepad support (input + preflight)

Status: **planned**, not started. Larger than the open items
above; comparable in scope to #4.

### Why

A lot of Rocket League is played on gamepad. Right now RLQC is
keyboard-and-mouse only: we read keys via `GetAsyncKeyState`,
emulate keystrokes via `keybd_event` + `pynput`, and the
preflight collision check only inspects the `PCBindings=(...)`
rows in `TAInput.ini`. Anyone using a controller is silently
unsupported — both functionally (the script doesn't respond to
controller input) and at the preflight layer (no warning if RL's
controller-side quick chat collides with whatever buttons we'd
choose to listen on).

### Scope (everything that has to land for this to feel finished)

1. **Input reading.**
   * Replace / parallel the `is_key_pressed()` helper with a
     gamepad equivalent. Options: built-in `ctypes` against
     XInput (`Xinput1_4.dll` — cleanest, no third-party dep),
     or `inputs` / `pygame.joystick` / `pyxinput` (more types
     of controllers, extra dependency).
   * Poll the controller in the same `sleep_key()`-driven loop
     `main()` already uses — no extra thread needed for a 500 Hz
     poll on a single gamepad.
   * Handle reconnects (controller unplugged mid-session must
     not crash the script).

2. **Action mapping (controller).**
   * Categories are normally bound to D-pad on Xbox controllers
     in RL: `XboxTypeS_DPad_Up/Left/Right/Down` → ChatPreset1..4.
     `rl_config.py::parse_pc_bindings()` currently SKIPS
     `GamepadBindings=(...)` rows; needs a sibling function
     `parse_gamepad_bindings()` (same regex with the prefix
     swapped) plus a UE-gamepad-name → XInput-button-mask map
     analogous to `UNREAL_KEY_TO_VK`.
   * `Steam Input` is a separate beast — Steam virtualises the
     controller and the `SteamInputBindings=(...)` rows in
     `TAInput.ini` reflect that. Phase 1 can ignore Steam Input;
     document the limitation in the preflight dialog.

3. **Text-chat emulation on gamepad.**
   * Pressing the chat key (`T` / `Y` / `U`) is trivial via
     `keybd_event`, but RL's gamepad text-chat is opened by a
     different button entirely (consult `TAInput.ini` — the
     `Chat`/`TeamChat`/`PartyChat` actions have their own
     `GamepadBindings=(...)` rows). Emulating a controller
     button press is *much* harder than a keystroke — XInput
     doesn't have a "send button" API, you have to virtualise
     a controller via ViGEm (a kernel-mode driver). Significant
     dependency.
   * **Pragmatic alternative**: still emit a keyboard `T` even
     when reading controller input — RL accepts keystrokes
     regardless of the active input device. Sidesteps ViGEm
     entirely. Drawback: a real `T` key has to exist (works
     even on Steam-Deck handhelds because the OS-level keyboard
     emulation already exists). Probably the right MVP.

4. **Preflight extension — gamepad collision warning.**
   * Mirror `_check_quickchat_collision()` for the controller
     side: if the user's RL `GamepadBindings` for ChatPreset1..4
     overlap with whatever XInput buttons RLQC listens on, emit
     a `gamepad_quickchat_collision` warning with the same
     "Don't show again" support that the keyboard one has.
   * Also: if BOTH a controller is connected AND keyboard
     bindings would collide, surface both warnings.

5. **First-run question: "do you play with keyboard or gamepad?"**
   * Closely related to the wizard in #2b. The wizard already
     has to collect HUD scale; while we're at it, ask the user
     to declare their input mode (auto-detection is theoretically
     possible — "is there an XInput controller attached?" — but
     unreliable because most desktops have a controller plugged
     in even when the user plays on KB+M). Persist the answer
     to `.rlqc_state.json` and let them change it later from a
     small menu.

6. **Mixed mode.**
   * Some players switch between gamepad and KB+M mid-session.
     The polling loop already does "check every input source
     each tick", so handling both at once is mostly free once
     #1 lands. The thing to be careful about is preflight
     warnings — only show what's actually applicable to the
     declared / detected input mode.

### Discovery work already done (Phase A leftovers)

The Phase A pass for #4 already proved that gamepad bindings ARE
present and parseable:

```
GamepadBindings=( Action="ChatPreset1", Key="XboxTypeS_DPad_Up"    )
GamepadBindings=( Action="ChatPreset2", Key="XboxTypeS_DPad_Left"  )
GamepadBindings=( Action="ChatPreset3", Key="XboxTypeS_DPad_Right" )
GamepadBindings=( Action="ChatPreset4", Key="XboxTypeS_DPad_Down"  )
```

…and identical rows under `SteamInputBindings=(...)` for the
Steam-virtualised flavour. `rl_config.py` already iterates the
file but filters to PC bindings; relaxing that filter is a
one-line change once we have something to do with the data.

### Open questions

  * Which XInput abstraction to commit to? Built-in `ctypes` is
    zero-dep but only supports XInput controllers (no DualShock
    without DS4Windows). A library like `pygame` adds startup
    cost but covers everything. Probably ctypes for now, escape
    hatch via a `requirements-gamepad.txt` extra later.
  * ViGEm or not? Affects whether we can emulate gamepad
    button presses to open the in-game chat, or have to fall
    back to a hidden keyboard press. Strong preference for the
    keyboard fallback initially — ViGEm needs admin/driver
    install and is a non-starter for "just clone and run".
  * How to know the user's controller-side actually-mapped
    keys? Reading `TAInput.ini` works the same as for keyboard,
    but only for the "active" preset section, and on Steam
    the controller binding can be Steam-Input-virtualised in
    a way that doesn't show up in `GamepadBindings=(...)` at
    all. Phase 1: trust `GamepadBindings`; document Steam
    Input as "may give false positives in the collision check".

