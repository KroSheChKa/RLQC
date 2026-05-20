import sys
import ctypes
import time
from win32api import keybd_event
from pynput.keyboard import Controller, Key, KeyCode
from config import *
from random import choice
from lang_determ import *
from PyQt5.QtWidgets import QApplication
from visuals import FramelessOverlay
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

def overlay_init():
    global overlay_app, overlay_win
    if overlay_app is not None:
        return

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

    overlay_app = QApplication(sys.argv)
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
# or {defence_code}. We substitute a random code from the corresponding
# pool right before showing/sending the message. Missing/unknown
# placeholders are left as empty strings instead of crashing.
class _DefaultDict(dict):
    """dict.format_map helper: unknown placeholders become empty strings."""
    def __missing__(self, key):
        return ''


def _safe_choice(seq):
    return choice(seq) if seq else ''


def render_message(template):
    if not isinstance(template, str) or '{' not in template:
        return template
    mapping = {
        'shooting_code': _safe_choice(shooting_training_map_codes),
        'defence_code':  _safe_choice(defence_training_map_codes),
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
    # Pick a random phrase per sub-category and render any
    # {shooting_code}/{defence_code} placeholders right away so that the
    # overlay shows exactly the same text that will be typed.
    overlay_msgs = []
    for sub_idx in range(4):
        options = quick_chat_messages[first_click][sub_idx]
        overlay_msgs.append(render_message(choice(options) if options else ''))

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

                    # Visual selection feedback: bold chosen line, then fade out
                    try:
                        overlay_win.set_selected_style(second_key, weight=65, color="#FFFFFF")
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

    # Lazily remember the user's original keyboard layout and detect a
    # working language-switch hotkey on the first call. Both are reused
    # later by safe_exit() to restore the layout on shutdown.
    global initial_keyboard_layout, lang_switch_keys
    if initial_keyboard_layout is None:
        try:
            initial_keyboard_layout = get_keyboard_layout_name()
            lang_switch_keys = determ_change_lang_keys()
        except Exception:
            initial_keyboard_layout, lang_switch_keys = None, None

    overlay_hide()

    # See function docstring: INFORMATIONAL (index 0) -> team chat,
    # anything else -> all-chat.
    if chat:
        chat_type = key_bindings['TEXT_CHAT_ALL']
    else:
        chat_type = key_bindings['TEXT_CHAT_PARTY']

    # Open the chat — small delays avoid truncation on rapid key sequences.
    keybd_event(chat_type, 0, 0, 0)
    sleep_key(0.001)
    keybd_event(chat_type, 0, KEYEVENTF_KEYUP, 0)
    sleep_key(0.02)

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
                sleep_key(0.0005)
                keyboard.release(letter_vk)
        else:
            keyboard.press(letter_vk)
            sleep_key(0.0005)
            keyboard.release(letter_vk)
        sleep_key(0.0005)

    # Send the message
    keybd_event(key_bindings['ENTER'], 0, 0, 0)
    sleep_key()
    keybd_event(key_bindings['ENTER'], 0, KEYEVENTF_KEYUP, 0)

    # Keep English layout during runtime; do not restore per-message.
    sleep_key(0.05)


def main():
    # Initialize overlay
    overlay_init()

    # Pre-render the overlay once to warm up fonts/GPU and avoid first-show delay
    try:
        overlay_show_for_category(0, ["", "", "", ""])  # minimal content
        overlay_pump_events()
        overlay_hide(duration_ms=50)
    except Exception:
        pass

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
