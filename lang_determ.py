from config import quick_chat_messages, key_bindings
import ctypes
import atexit
from pynput.keyboard import Controller, Key
import time

# -----------------------------------------------------------------------------
# Timer resolution boost (Windows-only).
#
# By default Windows scheduler ticks at ~15.6 ms which means that
# time.sleep(0.001) actually sleeps for ~16 ms — useless for the precise
# inter-keystroke delays this project relies on. Bumping the multimedia
# timer resolution to 1 ms makes time.sleep() honour millisecond values.
# The setting is per-process and we undo it on shutdown so we don't leave
# the whole OS in high-resolution mode.
# -----------------------------------------------------------------------------
try:
    _winmm = ctypes.WinDLL('winmm', use_last_error=True)
    _winmm.timeBeginPeriod(1)
    atexit.register(lambda: _winmm.timeEndPeriod(1))
except Exception:
    _winmm = None

_user32 = ctypes.WinDLL('user32', use_last_error=True)
_RLAC_END_VK = key_bindings.get('RLAC_END', 0x71)


def _exit_pressed():
    return _user32.GetAsyncKeyState(_RLAC_END_VK) & 0x8000 != 0


# Callback invoked from inside sleep_key() when the user pressed the
# exit key while we were waiting. RLQuickChat.py registers safe_exit()
# here at startup, so any sleep_key() call across the whole code base
# is automatically interruptible without sprinkling stop checks
# everywhere.
_on_stop_handler = None


def set_stop_handler(callback):
    global _on_stop_handler
    _on_stop_handler = callback

def VkKeyScan_(ch):
    tid = ctypes.windll.user32.GetWindowThreadProcessId(ctypes.windll.user32.GetForegroundWindow(), 0)
    hkl = ctypes.windll.user32.GetKeyboardLayout(tid)
    result = ctypes.windll.user32.VkKeyScanExW(ord(ch), hkl)
    return result


# Precise, interruptible sleep.
#
# Why this is non-trivial on Windows:
#   * time.sleep() is quantised by the OS scheduler tick (~15.6 ms by
#     default). That makes time.sleep(0.001) actually sleep ~16 ms.
#   * Pure busy-wait on time.time() / perf_counter() works but burns a
#     full CPU core, which we used to do.
#
# Strategy:
#   1) timeBeginPeriod(1) above lowers the scheduler tick to 1 ms.
#   2) We use perf_counter() to track an absolute deadline, immune to
#      sleep quantisation.
#   3) For the bulk of the wait we hand the CPU back to the OS in 1 ms
#      slices via time.sleep().
#   4) During the final ~2 ms we tight-loop on perf_counter() for
#      sub-millisecond accuracy.
#   5) On every iteration we poll RLAC_END; if pressed and a stop
#      handler is registered (RLQuickChat.py registers safe_exit), we
#      invoke it. This makes every sleep_key() call across the program
#      interruptible.
def sleep_key(sec=0.00001):
    if sec is None or sec <= 0:
        if _exit_pressed() and _on_stop_handler is not None:
            _on_stop_handler()
        return

    end = time.perf_counter() + sec
    SPIN_THRESHOLD = 0.002  # last 2 ms we busy-wait for precision

    while True:
        remaining = end - time.perf_counter()
        if remaining <= 0:
            return

        if _exit_pressed():
            if _on_stop_handler is not None:
                _on_stop_handler()
            return

        if remaining > SPIN_THRESHOLD:
            # Cap each chunk at 1 ms so we react quickly to the exit
            # key and so we never overshoot the deadline.
            time.sleep(min(0.001, remaining - SPIN_THRESHOLD))
        else:
            # Sub-2 ms tail: tight loop with stop-key polling.
            while time.perf_counter() < end:
                if _exit_pressed():
                    if _on_stop_handler is not None:
                        _on_stop_handler()
                    return
            return


# Get the code of current keyboard layout
def get_keyboard_layout_name():
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    # Get the active window and thread id of it
    handle = user32.GetForegroundWindow()
    threadid = user32.GetWindowThreadProcessId(handle, 0)
    # Recieve keyboard layout
    layout_id = user32.GetKeyboardLayout(threadid)
    # Apply the mask
    language_id = layout_id & (2 ** 16 - 1)
    language_id_hex = hex(language_id)
    return str(language_id_hex)


# Check whether the char could be printed on current keyboard layout
def codification_check(char):
    #print(char, VkKeyScan_(char))
    return VkKeyScan_(char) != -1


# Walks any nested structure of strings/lists and returns True
# only if every single character in every string is printable
# on the currently active keyboard layout.
def checker(msgs, list_of_checks=None):
    if list_of_checks is None:
        list_of_checks = []

    if isinstance(msgs, str):
        for ch in msgs:
            list_of_checks.append(codification_check(ch))
    elif isinstance(msgs, (list, tuple)):
        for item in msgs:
            checker(item, list_of_checks)
    else:
        print("checker(): unsupported item type:", type(msgs))
        list_of_checks.append(False)

    return all(list_of_checks)


# Func. to determ what keyboard shortcut for changing the language
def determ_change_lang_keys():
    keyboard = Controller()
    # I only iterate over 2 keyboard shortcuts
    for key_str in [Key.ctrl_l, Key.alt_l]:

        keyb_layout = get_keyboard_layout_name()

        with keyboard.pressed(Key.shift):
            keyboard.press(key_str)
            sleep_key(0.0001)
            keyboard.release(key_str)
            sleep_key(0.0001)
    
        new_keyb_layout = get_keyboard_layout_name()

        # Check if the language changed
        if keyb_layout == new_keyb_layout:
            continue
        else:
            return [key_str, Key.shift]
    # Could not detect a working hotkey combination
    return None


# A set of common English LCIDs (US/UK/AU/CA/NZ/etc.)
ENGLISH_LCIDS = {
    0x0409, 0x0809, 0x0C09, 0x1009, 0x1409, 0x1809,
    0x1C09, 0x2009, 0x2409, 0x2809, 0x2C09, 0x3009,
    0x3409, 0x4009
}


def is_english_layout_hex(layout_hex: str) -> bool:
    try:
        val = int(layout_hex, 16) & 0xFFFF
        return val in ENGLISH_LCIDS
    except Exception:
        return False


def press_lang_switch(first_key, second_key):
    keyboard = Controller()
    sleep_key(0.0001)
    with keyboard.pressed(second_key):
        keyboard.press(first_key)
        sleep_key(0.0001)
        keyboard.release(first_key)
        sleep_key(0.0001)


def ensure_english_layout_return_initial():
    """Ensure current layout is English.

    Returns a tuple (initial_layout_hex, keys) where keys is the detected
    switching combo (first_key, second_key). If detection fails, returns
    (current_layout_hex, None) and does not switch.
    """
    initial = get_keyboard_layout_name()
    keys = determ_change_lang_keys()
    if not keys:
        return initial, None

    if is_english_layout_hex(get_keyboard_layout_name()):
        return initial, keys

    for _ in range(20):
        press_lang_switch(keys[0], keys[1])
        if is_english_layout_hex(get_keyboard_layout_name()):
            break
    return initial, keys


def force_english_layout(keys=None):
    """Ensure English layout is active. Returns keys used (or None if failed)."""
    if is_english_layout_hex(get_keyboard_layout_name()):
        return keys

    local_keys = keys if keys else determ_change_lang_keys()
    if not local_keys:
        return None

    for _ in range(20):
        press_lang_switch(local_keys[0], local_keys[1])
        if is_english_layout_hex(get_keyboard_layout_name()):
            return local_keys
    return local_keys


# Changing the language until the messages will be printable
def language_we_happy():
    # Try to detect a working hotkey
    keys = determ_change_lang_keys()
    # If not found, skip language switching to avoid crash
    if not keys:
        return

    first_key, second_key = keys
    
    while True:
        keyboard = Controller()
        # If printable
        if checker(quick_chat_messages, []):
            break
        # Else change the language
        else:
            sleep_key(0.0001)
            with keyboard.pressed(second_key):
                keyboard.press(first_key)
                sleep_key(0.0001)
                keyboard.release(first_key)
                sleep_key(0.0001)

# Needed for testing
if __name__ == '__main__':
    print(checker(quick_chat_messages, []))
    #language_we_happy()
    sleep_key(2)
    print(checker(quick_chat_messages, []))
