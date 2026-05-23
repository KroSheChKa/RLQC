import sys
import ctypes
import time
from win32api import keybd_event
from pynput.keyboard import Controller, Key, KeyCode
from config import *
from lang_determ import *
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMessageBox
from visuals import FramelessOverlay
from preflight import (
    run_preflight, PreflightReport,
    dismissed_warning_ids, dismiss_warnings,
)
from pseudo_random import ShuffleBag
import win32gui
import win32con

# pynput controller used to emulate keystrokes. It is created at module
# import time on purpose: previously it was only created under
# `if __name__ == '__main__'`, which caused NameError if any function
# from this module was imported elsewhere.
keyboard = Controller()

# Check whether the key is pressed
def is_key_pressed(key):
    #return ctypes.windll.user32.GetKeyState(key) & 0x8000 != 0
    return ctypes.windll.user32.GetAsyncKeyState(key) & 0x8000 != 0


# Safely exit the script
def safe_exit():
    # Release only keys that are actually held down right now. Sending
    # KEYUP for every key in key_bindings (incl. F1/F2/T/Y/1..5) is
    # unnecessary and can interfere with the user's other apps.
    for _, key_code in key_bindings.items():
        if is_key_pressed(key_code):
            keybd_event(key_code, 0, KEYEVENTF_KEYUP, 0)
            sleep_key(1 / MONITOR_REFRESH_RATE)

    # Restore initial keyboard layout once (best-effort).
    try:
        if initial_keyboard_layout is not None and lang_switch_keys is not None:
            tries = 0
            while get_keyboard_layout_name() != initial_keyboard_layout and tries < 20:
                press_lang_switch(lang_switch_keys[0], lang_switch_keys[1])
                sleep_key(0.02)
                tries += 1
    except Exception:
        pass

    # Cleanly tear down the Qt application if it exists.
    try:
        if overlay_app is not None:
            overlay_app.quit()
    except Exception:
        pass

    sys.exit()
# ----------------------
# Overlay UI management
# ----------------------

overlay_app = None
overlay_win = None
initial_keyboard_layout = None
lang_switch_keys = None

# True once paste_in_chat has actually opened the in-game chat at
# least once. The very first chat-open in RL takes noticeably
# longer than subsequent ones — the game has to cold-load the
# chat widget / fonts / render pipeline — and a 20 ms wait after
# the T-keystroke isn't enough to be sure the textbox has focus
# yet. We sleep significantly longer on the first paste so the
# opening characters of the first message don't get dropped on
# the closing scene; after that, the game is warm.
_chat_subsystem_warm = False

def qt_app_init():
    """Bring up the QApplication once, with HiDPI scaling disabled.

    Split out from overlay_init() so that the preflight dialog can
    pop up BEFORE the overlay window itself is created — otherwise
    the empty overlay would briefly flash on screen before the
    user has a chance to read any warnings.
    """
    global overlay_app
    if overlay_app is not None:
        return

    # Opt out of Qt's automatic HiDPI scaling BEFORE the QApplication
    # is built — Rocket League ignores the Windows display-scale
    # setting (100/125/150%), so we have to as well, otherwise our
    # overlay grows on high-DPI systems while the in-game quick chat
    # stays put. See the matching note in tuner.py / TODO.md #2.
    QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True)
    overlay_app = QApplication(sys.argv)


def overlay_init():
    global overlay_app, overlay_win
    if overlay_win is not None:
        return
    if overlay_app is None:
        qt_app_init()

    # INTERFACE_SCALE and OVERLAY_POSITION come from config.py — that's
    # where the user is supposed to tweak the menu size to match the
    # in-game HUD scale. See the comment block in config.py for details.
    scale = INTERFACE_SCALE / 100.0
    wp = {
        'left':   int(OVERLAY_POSITION['left']   * scale),
        'top':    int(OVERLAY_POSITION['top']    * scale),
        'width':  int(OVERLAY_POSITION['width']  * scale),
        'height': int(OVERLAY_POSITION['height'] * scale),
    }

    # Pass the scale to the overlay so that the painter inside scales
    # fonts/paddings/line-offsets the same way the window is scaled.
    overlay_win = FramelessOverlay(wp, scale=scale)
    overlay_win.hide()

    hwnd = int(overlay_win.winId())
    win32gui.SetWindowPos(
        hwnd, win32con.HWND_TOPMOST,
        0,0,0,0,
        win32con.SWP_NOMOVE|win32con.SWP_NOSIZE|win32con.SWP_SHOWWINDOW
    )

def overlay_pump_events():
    if overlay_app is not None:
        overlay_app.processEvents()

def overlay_show_for_category(category_idx, msgs=None):
    if overlay_app is None or overlay_win is None:
        return
    titles = category_titles if 'category_titles' in globals() else ['INFORMATIONAL', 'COMPLIMENTS', 'REACTIONS', 'APOLOGIES', 'CUSTOM']
    title = titles[category_idx] if 0 <= category_idx < len(titles) else 'QUICK CHAT'
    # if msgs provided, use them; else preview first phrase of each sub-list
    if msgs is None:
        msgs_preview = []
        cats = quick_chat_messages[category_idx]
        for i in range(4):
            sub = cats[i] if i < len(cats) else []
            msgs_preview.append(sub[0] if sub else '')
        overlay_win.show_with_content(title, msgs_preview, duration_ms=200)
    else:
        overlay_win.show_with_content(title, msgs, duration_ms=200)
    overlay_pump_events()

def overlay_hide(duration_ms=200):
    if overlay_win is not None:
        overlay_win.fade_out(duration_ms=duration_ms)
        overlay_pump_events()


# ----------------------
# Message rendering
# ----------------------
# Phrases in config.py may contain placeholders such as {shooting_code}
# or {defence_code}. We substitute a code from the corresponding pool
# right before showing/sending the message. Missing/unknown
# placeholders are left as empty strings instead of crashing.
#
# Picking strategy: ShuffleBag (see pseudo_random.py). Plain
# random.choice() on a 5-item list yields a same-as-last result
# ~20% of the time, which feels lame for the user. ShuffleBag
# shuffles the pool, walks through it, reshuffles on exhaustion,
# and guards the seam — perceived as random, never repeats.
#
# `_bags` caches one bag per logical pool so the cycle state
# survives across calls. Lazy creation on first use so unused
# chords don't allocate.
class _DefaultDict(dict):
    """dict.format_map helper: unknown placeholders become empty strings."""
    def __missing__(self, key):
        return ''


_bags: dict = {}


def _bag_for(key, items):
    """Return the cached ShuffleBag for `key`, creating it on demand."""
    bag = _bags.get(key)
    if bag is None:
        bag = ShuffleBag(items)
        _bags[key] = bag
    return bag


def _pick_phrase(category_idx, subcat_idx):
    """Yield the next phrase template for the given chord, shuffle-bag style."""
    options = quick_chat_messages[category_idx][subcat_idx]
    if not options:
        return ''
    return _bag_for(('phrase', category_idx, subcat_idx), options).next() or ''


def _pick_code(pool_name, pool):
    """Yield the next training-map code from the given pool."""
    if not pool:
        return ''
    return _bag_for(('code', pool_name), pool).next() or ''


def render_message(template):
    if not isinstance(template, str) or '{' not in template:
        return template
    mapping = {
        'shooting_code': _pick_code('shooting', shooting_training_map_codes),
        'defence_code':  _pick_code('defence',  defence_training_map_codes),
    }
    try:
        return template.format_map(_DefaultDict(mapping))
    except Exception:
        return template


# # The function that remembers latest pressed keys (not working properly!)
# def save_latest_keys():
#     # We store keys
#     list_of_pressed_keys = []

#     # Iterate over the dict. to find pressed keys
#     for key_name, key_code in active_RL_keyboard_keys.items():
#         if is_key_pressed(key_code):
#             list_of_pressed_keys.append(key_name)

#     return list_of_pressed_keys


# Expecting a second click after the first
def second_click(first_click):
    # Pick a phrase per sub-category (ShuffleBag — see render_message's
    # _pick_phrase helper) and render any {shooting_code}/{defence_code}
    # placeholders right away, so that the overlay shows exactly the
    # same text that will be typed into chat.
    overlay_msgs = []
    for sub_idx in range(4):
        overlay_msgs.append(render_message(_pick_phrase(first_click, sub_idx)))

    # Show overlay for the chosen category with pre-selected messages and start the timer
    overlay_show_for_category(first_click, overlay_msgs)
    start_time = time.perf_counter()
    fade_out_started = False

    # Sub-category keys are exactly the same physical keys as the first
    # click (1..4/5). We must not react to a key that is still held down
    # from the first click; require a release-then-press by waiting until
    # every category key is up before starting to listen.
    while any(is_key_pressed(k) for k in quick_buttons_iterate):
        overlay_pump_events()
        sleep_key(0.002)

    try:
        while True:
            overlay_pump_events()
            for second_key, key in enumerate(quick_buttons_iterate):
                if is_key_pressed(key):
                    # Instantly release the key (avoid false detection)
                    keybd_event(key, 0, KEYEVENTF_KEYUP, 0)

                    # Visual selection feedback. Colour / weight of
                    # the highlighted line are game-fixed inside
                    # FramelessOverlay (white + bold); we just have
                    # to tell the overlay WHICH line is selected.
                    try:
                        overlay_win.set_selected_style(second_key)
                        overlay_pump_events()
                    except Exception:
                        pass

                    # Text that should be typed in chat equals the displayed option
                    text_message = overlay_msgs[second_key]

                    # Start faster fade-out while we begin typing (0.2s quicker)
                    overlay_hide(duration_ms=119)

                    paste_in_chat(text_message, first_click)
                    return

            elapsed_time = time.perf_counter() - start_time

            # Start early fade-out 0.2s before timeout
            if not fade_out_started and elapsed_time >= max(0.0, WAIT_TIME_SECOND_CLICK - 0.2):
                fade_out_started = True
                overlay_hide()

            if elapsed_time >= WAIT_TIME_SECOND_CLICK:
                return

            # Yield CPU. ~2 ms gives ~500 Hz polling which is more than
            # enough for human reaction times, instead of pegging a core.
            # sleep_key also polls RLAC_END and triggers safe_exit
            # automatically if pressed.
            sleep_key(0.002)
    finally:
        overlay_hide()


# Quickly type message in chat.
# `chat` is the first-click category index (0..N-1). In Rocket League
# the INFORMATIONAL category (index 0) is a team-only chat, while every
# other category (COMPLIMENTS / REACTIONS / APOLOGIES / CUSTOM) goes to
# the all-chat. That mirrors the in-game behaviour, so we route the
# message accordingly.
def paste_in_chat(txt_msg, chat):
    # Bail out fast if the user pressed the exit key while the overlay
    # was still up.
    if is_key_pressed(key_bindings['RLAC_END']):
        return

    # Recover lazily if startup warmup didn't run for any reason
    # (e.g. someone imported this module and called paste_in_chat
    # directly). Normally a no-op — main() already invoked it.
    global initial_keyboard_layout, lang_switch_keys, _chat_subsystem_warm
    if initial_keyboard_layout is None:
        _input_subsystem_warmup()

    overlay_hide()

    # See function docstring: INFORMATIONAL (index 0) -> team chat,
    # anything else -> all-chat.
    if chat:
        chat_type = key_bindings['TEXT_CHAT_ALL']
    else:
        chat_type = key_bindings['TEXT_CHAT_PARTY']

    # Snapshot the "first paste" status BEFORE we flip the flag —
    # the slower per-letter sleep further down also keys off it.
    is_first_paste = not _chat_subsystem_warm

    # Open the chat — small delays avoid truncation on rapid key sequences.
    keybd_event(chat_type, 0, 0, 0)
    sleep_key(0.001)
    keybd_event(chat_type, 0, KEYEVENTF_KEYUP, 0)
    # First chat-open of the session is significantly slower than
    # subsequent ones (RL has to cold-load the chat widget) AND
    # the first input-burst through pynput / SendInput has its
    # own warm-up cost. Without enough headroom here, the first
    # message loses its opening letters. 150 ms is the smallest
    # value that's worked reliably in testing; subsequent pastes
    # use the original snappy 20 ms once `_chat_subsystem_warm`
    # is True.
    sleep_key(0.15 if is_first_paste else 0.02)
    _chat_subsystem_warm = True

    # Ensure English layout AFTER chat field receives focus (game may
    # reset layout when the chat box opens).
    try:
        if not is_english_layout_hex(get_keyboard_layout_name()):
            keys_local = lang_switch_keys if lang_switch_keys else determ_change_lang_keys()
            if keys_local:
                for _ in range(6):
                    if is_english_layout_hex(get_keyboard_layout_name()):
                        break
                    press_lang_switch(keys_local[0], keys_local[1])
                    sleep_key(0.02)
                if not lang_switch_keys and keys_local:
                    lang_switch_keys = keys_local
    except Exception:
        pass

    # Iterate over each letter in text message
    #
    # The per-letter sleeps are scaled up on the FIRST paste of the
    # session. Even after the long sleep above, RL sometimes drops
    # the first 1-3 characters of the first message — likely the
    # game's input ring buffer warming up. Typing slowly the first
    # time gives it time to drain. Subsequent messages use the
    # original tight timing, which is what you want in-game.
    inter_letter = 0.0025 if is_first_paste else 0.0005
    inner_hold   = 0.0025 if is_first_paste else 0.0005
    for letter in txt_msg:
        scan = VkKeyScan_(letter)
        # VkKeyScan returns -1 if the char cannot be produced on the
        # current layout. Skip such characters instead of feeding -1
        # back into pynput.
        if scan == -1:
            continue
        # Low byte is the VK code, high byte holds modifier flags
        # (0x01=Shift, 0x02=Ctrl, 0x04=Alt). We handle Shift manually
        # below, so strip the modifier bits here.
        letter_vk = KeyCode.from_vk(scan & 0xFF)
        needs_shift = bool(scan & 0x0100) or letter.isupper() or letter in shift_symbols

        if needs_shift:
            with keyboard.pressed(Key.shift):
                keyboard.press(letter_vk)
                sleep_key(inner_hold)
                keyboard.release(letter_vk)
        else:
            keyboard.press(letter_vk)
            sleep_key(inner_hold)
            keyboard.release(letter_vk)
        sleep_key(inter_letter)

    # Send the message
    keybd_event(key_bindings['ENTER'], 0, 0, 0)
    sleep_key()
    keybd_event(key_bindings['ENTER'], 0, KEYEVENTF_KEYUP, 0)

    # Keep English layout during runtime; do not restore per-message.
    sleep_key(0.05)


def _input_subsystem_warmup():
    """Pay all the one-time input-discovery costs up front.

    Used to happen lazily inside `paste_in_chat()` on its very
    first call. Problem with lazy: it added latency RIGHT BEFORE
    the user's first chat message went out — which is what was
    chopping the opening letters off the first quick-chat
    message. Doing it here while the user is alt-tabbing into
    RL / waiting for a match means the first paste is no slower
    than the rest.

    Things being warmed up:

      * `get_keyboard_layout_name()` — Win32 call. Cheap on its
        own, but Windows still has to bind the imports the first
        time it's called.
      * `determ_change_lang_keys()` — physically presses Ctrl+Shift
        and Alt+Shift to figure out which combo switches layouts.
        That probe can briefly flip the user's keyboard layout if
        the first guess works. Better to do that now while we're
        in the F1-wait phase than mid-typing.
      * pynput `Controller()` send path — first `.press()` /
        `.release()` of the process has a noticeable backend-
        bind cost in some builds. Exercise it with a Shift
        keystroke (Shift alone doesn't produce any printable
        character so the rest of the system can't tell).
      * Win32 `keybd_event()` send path — same idea, separate
        code path because the chat-open keystrokes go through
        keybd_event while text typing goes through pynput, so
        both need to be warm.

    Safe to call repeatedly; only the first invocation does work.
    """
    global initial_keyboard_layout, lang_switch_keys
    if initial_keyboard_layout is not None:
        return
    try:
        initial_keyboard_layout = get_keyboard_layout_name()
        lang_switch_keys = determ_change_lang_keys()
    except Exception:
        initial_keyboard_layout = None
        lang_switch_keys = None

    # Pynput backend bind. Shift alone is the safest "send something
    # through pynput without producing visible side effects" option:
    # no character is typed, no toggle state changes, no shortcut
    # fires (Shift+nothing isn't bound to anything in any sane app).
    try:
        keyboard.press(Key.shift)
        keyboard.release(Key.shift)
    except Exception:
        pass

    # Same idea for the raw Win32 path. VK_LSHIFT = 0xA0; we tap it
    # via keybd_event so the kernel has resolved the function
    # imports / loaded user32 hooks before the cold chat-open path
    # in paste_in_chat() needs them.
    try:
        keybd_event(0xA0, 0, 0, 0)
        keybd_event(0xA0, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        pass


def _log_preflight(report: PreflightReport) -> None:
    """Mirror the preflight findings to stdout.

    Detected bindings always print — they're useful diagnostic
    info even when no warnings are active. Dismissed warnings are
    skipped so the daily console output stays clean.
    """
    if report.detected_bindings:
        print("[RLQC] Auto-detected from Rocket League:")
        for name, vk in report.detected_bindings.items():
            print(f"         {name:<22} = 0x{vk:02X}")
    skip = dismissed_warning_ids()
    active = [w for w in report.warnings if w.id not in skip]
    if active:
        print("[RLQC] Pre-flight warnings:")
        for w in active:
            print(f"         - {w.title}")
            print(f"             {w.detail}")
            print(f"             Fix: {w.fix_hint}")


def _show_preflight_dialog(report: PreflightReport) -> bool:
    """Show the preflight summary as a Qt dialog. Returns True to continue.

    Warnings the user previously dismissed (via "Don't show this
    again") are filtered out here based on `.rlqc_state.json`.
    If nothing remains to surface, the dialog is skipped entirely.
    Detected bindings are always logged to the console regardless.
    """
    if not report.has_warnings:
        return True

    skip = dismissed_warning_ids()
    active = [w for w in report.warnings if w.id not in skip]
    if not active:
        return True

    msg = QMessageBox()
    msg.setWindowTitle("RLQC pre-flight")
    msg.setIcon(QMessageBox.Warning)
    msg.setTextFormat(Qt.RichText)

    parts: list[str] = []
    if report.detected_bindings:
        parts.append("<b>Detected from your Rocket League settings:</b><br/>")
        for name, vk in report.detected_bindings.items():
            parts.append(
                f"&nbsp;&nbsp;• <code>{name}</code> &nbsp;→&nbsp; "
                f"VK <code>0x{vk:02X}</code><br/>"
            )
        parts.append("<br/>")

    parts.append("<b>⚠ Things you should check before playing:</b><br/><br/>")
    for w in active:
        parts.append(f"<b>{w.title}</b><br/>")
        parts.append(f"{w.detail}<br/>")
        parts.append(f"<b>Fix:</b> {w.fix_hint}<br/><br/>")

    parts.append(
        "You can continue anyway — RLQC will still run, but the issue "
        "above may make it misbehave until you address it. "
        "<i>'Don't show this again' suppresses the warnings currently "
        "on screen for all future runs (state file: "
        ".rlqc_state.json — delete it to bring them back).</i>"
    )
    msg.setText("".join(parts))

    btn_continue = msg.addButton("Continue", QMessageBox.AcceptRole)
    btn_dismiss  = msg.addButton("Don't show this again", QMessageBox.ActionRole)
    btn_quit     = msg.addButton("Quit RLQC", QMessageBox.RejectRole)
    msg.setDefaultButton(btn_continue)
    msg.exec_()
    clicked = msg.clickedButton()

    if clicked is btn_dismiss:
        dismiss_warnings(w.id for w in active)
        return True
    return clicked is btn_continue


def main():
    # Bring up QApplication early so the preflight dialog has a host.
    # The overlay window itself comes up later, AFTER the user OK's
    # the preflight — otherwise an empty overlay would flash briefly
    # while the dialog is on screen.
    qt_app_init()

    # Read-only checks against the user's Rocket League setup. We
    # never modify the game's config; we just tell the user what
    # to fix and let them decide whether to continue.
    report = run_preflight(key_bindings)
    _log_preflight(report)
    if not _show_preflight_dialog(report):
        sys.exit(0)

    # Apply auto-detected bindings on top of config.py defaults.
    # RL wins on conflict — those are the keys the user actually
    # presses in-game and the whole point of auto-detection is to
    # remove the "keep config.py and the game in sync" chore.
    if report.detected_bindings:
        for name, vk in report.detected_bindings.items():
            key_bindings[name] = vk
        # `quick_buttons_iterate` was snapshotted from `key_bindings`
        # at config-import time, so it doesn't see our mutations
        # above. Rebuild the local binding so the main loop iterates
        # over the auto-detected codes.
        global quick_buttons_iterate
        quick_buttons_iterate = [
            key_bindings['INFORMATION(TEAM)'],
            key_bindings['COMPLIMENTS'],
            key_bindings['REACTIONS'],
            key_bindings['APOLOGIES'],
            key_bindings['CUSTOM'],
        ]

    # Initialize overlay
    overlay_init()

    # Pre-render the overlay once to warm up fonts/GPU and avoid first-show delay
    try:
        overlay_show_for_category(0, ["", "", "", ""])  # minimal content
        overlay_pump_events()
        overlay_hide(duration_ms=50)
    except Exception:
        pass

    # Warm up input plumbing now, while the user is still getting
    # into a match. Doing this here (instead of lazily inside the
    # first paste_in_chat) is what stops the first chat message of
    # the session from losing its opening letters.
    _input_subsystem_warmup()

    # Press F1 to start the script. sleep_key yields the CPU and also
    # polls RLAC_END, so the user can quit while the script is still
    # in its idle "waiting for F1" phase.
    while not is_key_pressed(key_bindings['RLAC_START']):
        overlay_pump_events()
        sleep_key(0.01)
    keybd_event(key_bindings['RLAC_START'], 0, KEYEVENTF_KEYUP, 0)

    # Main loop: wait for a category key press.
    while True:
        overlay_pump_events()
        for idx, key in enumerate(quick_buttons_iterate):
            if is_key_pressed(key):
                # Instantly release the key (avoid false detection)
                keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
                second_click(idx)
                break

        # ~500 Hz poll; sleep_key handles RLAC_END internally.
        sleep_key(0.002)


if __name__ == '__main__':
    # Wire sleep_key (defined in lang_determ) so that whenever the user
    # presses RLAC_END *during* any internal sleep, we tear down cleanly
    # via safe_exit(). This replaces dozens of ad-hoc stop checks.
    set_stop_handler(safe_exit)
    main()
