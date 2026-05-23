# RLQC

## Make your quick chat unique!

❌ ~~What a save!~~\
❌ ~~Nice shot!~~\
✔️ Here's the code for practicing saves: 2E68-0A19-F54F-D41F\
✔️ Nice shot! If you were aiming for the bleachers!

![image](https://github.com/user-attachments/assets/76cdd253-cb88-4a70-8841-8b1074a8791e)
> Guess where is the real **chat menu**

RLQC replaces Rocket League's built-in quick chat with your own
messages, sent the same familiar way (one key for the category,
another for the phrase). It also draws a pixel-matched overlay so
the menu looks like it was always part of the game.

### Highlights

- **Custom messages.** Edit `config.py`, write whatever you want.
- **Same input as the game.** 4-button system + reset-on-delay,
  so muscle memory carries over.
- **Multiple variants per shortcut.** A given chord (e.g. `1-1`)
  can hold any number of phrases; one is picked at random.
- **Randomised in-message tokens.** Training-map codes etc. are
  substituted from a pool at send time so the same message looks
  fresh every time.
- **Pixel-matched overlay.** The on-screen quick-chat menu is
  rendered by us, calibrated against the in-game UI down to the
  edge fades and the selected-line highlight. Fully tunable —
  see `tuner.py`.
- **CapsLock fuse.** Won't accidentally SHOUT mid-message; LED
  state stays in sync.
- **Safe shutdown.** No keys left stuck pressed when you quit.
- **Layout-safe typing.** Detects keyboard layout, switches to
  English on chat open, restores on exit.
- **Start / stop with a hotkey.** F1 to arm, F2 to quit.

> Gamepad support: not yet (see roadmap below).

#### Warning: modify text messages at your own risk. You may be banned for obscene language.

---

## Installation

You don't need to be a programmer to set this up — there are no
terminal commands to remember. There's a one-time Python install,
then a single double-click.

### Step 1 — Install Python (once per PC)

Download Python 3.10 or newer from the official site and run the
installer:

<https://www.python.org/downloads/>

> **Important.** On the very first screen of the installer, tick
> the checkbox **"Add python.exe to PATH"** *before* clicking
> *Install Now*. If you forget this, the next step won't find
> Python.

If Python is already installed on your PC, you can skip this step.

### Step 2 — Download RLQC

- Easiest: click the green **Code** button at the top of
  [the GitHub page](https://github.com/KroSheChKa/RLQC) →
  **Download ZIP**, then unzip it anywhere you like
  (Desktop is fine).
- Or, if you use git:
  ```
  git clone https://github.com/KroSheChKa/RLQC.git
  ```

### Step 3 — Install the required packages

Open the RLQC folder and **double-click `install.bat`**.

A black console window will open and start downloading the three
packages RLQC needs (`pynput`, `pywin32`, `PyQt5`). When it's done
you'll see:

```
   Done! All packages are installed.

   You can now launch RLQC by double-clicking  run.bat
   This window can be closed.
```

Press any key to close the window.

> Windows may show a SmartScreen prompt the first time
> ("Windows protected your PC"). Click **More info → Run anyway** —
> the file is the small batch script you can see in this folder,
> not a binary. Nothing is being downloaded or executed besides
> the official Python packages listed in `requirements.txt`.

That's it for installation. You only do steps 1–3 once.

---

## Required Rocket League setup

Until the auto-setup feature in TODO.md #4 lands, the user is
responsible for two RL-side prerequisites. Both are one-time
clicks inside RL's settings:

1. **Display mode: Borderless Windowed.**
   `Settings → Video → Display Mode → Borderless`.
   We cannot draw the overlay on top of exclusive fullscreen.
   Borderless is identical visually, with no performance cost.

2. **Built-in Quick Chat: Off** (or rebound away from 1-4 keys).
   `Settings → Chat → Quick Chat → Off`.
   Otherwise pressing `1..4` triggers BOTH the real quick chat AND
   our script — you'll spam two different messages at once. Either
   turn it off entirely, or remap RL's quick-chat keys to
   something out of the way.

3. **Text chat: enabled.**
   `Settings → Chat → Match Chat → Friends / Teammates / Everyone`
   (anything except Off). The script types messages into the
   regular chat field, so it must be open-able.

---

## Configure the script

Open `config.py`. Most of it is comments — the few values you'll
actually touch:

#### Match your in-game HUD scale

```python
INTERFACE_SCALE = 100   # 50..100, same number as RL's HUD scale
```

This is the **only** scale knob you need to touch. The overlay
window AND everything inside it (fonts, paddings, line offsets,
glow) are scaled by `INTERFACE_SCALE / 100`. Set it to whatever
your in-game HUD scale slider is and the overlay should line up.

> Windows display scale (100% / 125% / 150% in OS settings) is
> deliberately ignored — see the comment block next to
> `INTERFACE_SCALE` and TODO.md #2 for the rationale.

#### Overlay position

```python
OVERLAY_POSITION = {'left': 16, 'top': 470, 'width': 395, 'height': 260}
```

Hand-calibrated for a 1920×1080 / HUD 100 / WinScale 100 setup.
For other configurations you'll currently want to recalibrate
with the tuner (below) until TODO.md #2 ships.

#### Hotkeys / chat keys

```python
key_bindings = {
    'RLAC_START': 0x70,   # F1
    'RLAC_END':   0x71,   # F2
    'TEXT_CHAT_ALL':   0x54,
    'TEXT_CHAT_PARTY': 0x59,
    'INFORMATION(TEAM)': 0x31,
    'COMPLIMENTS':       0x32,
    'REACTIONS':         0x33,
    'APOLOGIES':         0x34,
    ...
}
```

Values are Win32 [virtual-key codes](https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes).
Keep these in sync with whatever you set inside Rocket League.

#### The messages themselves

```python
quick_chat_1_1 = [
    "Dear mate, let me take that kickoff!",
    ...
]
quick_chat_1_2 = [
    "Ooh, I have no hands to take that :(",
    ...
]
```

Each list is one chord (`category × phrase`). Add as many lines
as you want — one is picked at random per send.

---

## Calibrate the overlay (`tuner.py`)

If the overlay doesn't sit pixel-perfect on your machine
(different resolution, ultrawide, custom HUD scale...), use the
bundled tuner. **Double-click `tune.bat`** in the RLQC folder
(or run `python tuner.py` from a terminal if you prefer).

It opens the live overlay plus a control panel with sliders for
every visual parameter — window geometry, paddings, fonts,
background fade curve, the selected-phrase letter-spacing, you
name it. Tweak until the overlay matches the in-game quick chat,
then save the result as a preset.

Presets are stored in `overlay_presets.json` (your local working
file, kept under version control so we can collect data points).
Pixel-perfect ones that we want to keep around as references
across resolutions live under `presets/reference_presets.json`.

Detected environment info (resolution, real Windows scale, DPR)
is recorded with every preset so the future auto-adaptation
formula in TODO.md #2 has data to work with.

---

## Run

1. **Double-click `run.bat`** in the RLQC folder.
   (Power users: `python RLQuickChat.py` from a terminal works
   too.)
2. Launch Rocket League (Borderless mode!).
3. Press **F1** to arm the script. Press a category key (1..4),
   then a sub-category key (1..4) — the picked phrase types
   itself into chat.
4. **F2** quits cleanly.

*You are free to build friendly relationships with your mates and
opponents ;)*

### What happens on startup

RLQC silently looks at your Rocket League configuration before
arming itself:

- It locates your RL Config folder
  (`Documents\My Games\Rocket League\TAGame\Config\`), reads
  `TAInput.ini`, and **auto-detects the keys you actually have
  bound to RL's chat actions** (`Chat`, `TeamChat`,
  `ChatPreset1..4`). Those override the corresponding entries in
  `config.py` for this session — you don't have to keep the two
  in sync any more.
- It reads `TASystemSettings.ini` and warns you if you're in
  exclusive fullscreen (the only display mode our overlay can't
  draw over).
- It compares RL's bound chat keys against ours and warns you
  about collisions: if your in-game Quick Chat is still on and
  bound to the same `1..4` keys, pressing one will fire BOTH
  the game's default phrase and yours.

Detected bindings are always printed to the console. A popup
appears **only when there's a warning**, with `Continue` and
`Quit RLQC` buttons — RLQC never modifies your game files and
never forces you to fix anything; it just tells you what to
click in RL's settings.

> Diagnostic mode: run `python rl_config.py` to dump what RLQC
> sees in your config without launching the overlay.

---

## Roadmap

Living plan — full detail in `TODO.md`.

- **#1 Pixel-perfect background fade.** The four-edge fade now
  uses a parametric quadratic Bezier; remaining work is mostly
  caching a pre-rendered pixmap for cheaper repaints.
- **#2 Auto-adaptation to any (resolution × HUD scale).** Once
  enough reference presets are saved, derive a formula and apply
  it automatically — no more `INTERFACE_SCALE` knob, no more
  per-resolution recalibration. Windows DPI is collected but
  currently NOT applied (see the status block on #2).
- **#2b First-run wizard.** Tiny GUI on first launch to collect
  the one input we can't auto-detect: the in-game HUD scale.
- **#3 / #3b Style dict slimming.** As presets accumulate, drop
  keys that don't actually vary out of `DEFAULT_STYLE` and into
  module-level constants.
- **#4 Frictionless first-run setup — read-only path shipped.**
  RLQC now auto-finds your RL Config folder, reads `TAInput.ini`
  to pull your real key bindings into memory, and shows a
  preflight popup if it spots a problem (exclusive fullscreen,
  in-game Quick Chat overlapping with our keys, etc.). It never
  modifies your game files. See "What happens on startup" above.
  Remaining: a first-run wizard for the HUD scale (the only
  input we still can't auto-detect).
- **#6 Gamepad support.** Currently RLQC is keyboard-only —
  controller users get no input handling and no preflight
  warning if RL's D-pad chat presets overlap with what we'd
  listen on. Plan covers XInput polling, gamepad-side preflight
  collision check, and a pragmatic "still emit keyboard `T` for
  text chat" approach to avoid needing a virtual-controller
  driver. Details in `TODO.md` #6.

---

## What's done in the current development cycle

The original "Need to add / fix" checklist is now folded into
TODO.md. Headline changes since the last release:

- [x] **UI overlay** — a frameless, click-through, always-on-top
      replica of the in-game quick chat menu, rendered with Qt.
- [x] **Selected-phrase highlight** — bold white text + tunable
      letter-spacing, matching the game's selection behaviour.
- [x] **Background fade** — Bezier-curve gradients on all four
      edges, calibratable.
- [x] **Tuner** (`tuner.py`) — live calibration UI with preset
      save/load and per-machine environment capture.
- [x] **Qt HiDPI scaling disabled** — overlay no longer grows on
      Windows display-scale 125% / 150%, matches the game.
- [x] **Interruptible high-precision `sleep_key`** with
      `winmm.timeBeginPeriod(1)`; busy-loops gone.
- [x] **Bug-fix sweep** — masking on `VkKeyScan_` return values,
      cleanly-scoped `Controller`, proper safe-exit, dead
      CapsLock branch removed, etc.
- [x] **Random-token substitution** in messages
      (`{shooting_code}` / `{defence_code}`) so variants no
      longer require a brute-force list per code.
- [x] **Preflight + auto-detect Rocket League bindings**
      (`rl_config.py`, `preflight.py`) — reads `TAInput.ini` and
      `TASystemSettings.ini`, auto-applies the detected keys, and
      warns you (without modifying anything) if your in-game
      setup conflicts with RLQC.

---

*Found a bug? Have an idea?* →
[Discussions](https://github.com/KroSheChKa/RLQC/discussions)
