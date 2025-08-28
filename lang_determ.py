from config import quick_chat_messages
import ctypes
from pynput.keyboard import Controller, Key
import time

def VkKeyScan_(ch):
    tid = ctypes.windll.user32.GetWindowThreadProcessId(ctypes.windll.user32.GetForegroundWindow(), 0)
    hkl = ctypes.windll.user32.GetKeyboardLayout(tid)
    result = ctypes.windll.user32.VkKeyScanExW(ord(ch), hkl)
    return result


# Sleep func. that you could stop by pressing the stop key
def sleep_key(sec = 0.00001):
    start_time = time.time()
    
    while True:
        current_time = time.time()
        elapsed_time = current_time - start_time
        
        # If the time has run out, exit the loop
        if elapsed_time >= sec:
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


# Iterating over each letter in text messages
def checker(msgs, list_of_checks):
    for item in msgs:
        # Check if the item is a list 
        if isinstance(item, list):
            checker(item, list_of_checks)
        # Check if the item is a str
        elif isinstance(item, str):
            if len(item) == 1:
                # Every character is printable?
                everything_ok = all(map(codification_check, msgs))
                list_of_checks.append(everything_ok)
                continue
            else:
                checker(item, list_of_checks)
        else:
            print("Something went wrong!")
    # If any letter isn't printable - return False
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
