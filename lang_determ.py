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
        # # ExitKey pressed during the loop? - exit the entire program
        # if is_key_pressed(key_bindings['RLAC_END']):
        #     keybd_event(0x14, 0, key_bindings['RLAC_END'], 0)
        #     safe_exit()

        current_time = time.time()
        elapsed_time = current_time - start_time
        
        # If the time has run out, exit the loop
        if elapsed_time >= sec:
            return


def get_keyboard_layout_name():
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    handle = user32.GetForegroundWindow()
    threadid = user32.GetWindowThreadProcessId(handle, 0)
    layout_id = user32.GetKeyboardLayout(threadid)
    language_id = layout_id & (2 ** 16 - 1)
    language_id_hex = hex(language_id)
    return str(language_id_hex)


def codification_check(char):
    #print(char, VkKeyScan_(char))
    return VkKeyScan_(char) != -1


def checker(msgs, list_of_checks):
    for item in msgs:
        if isinstance(item, list):
            checker(item, list_of_checks)

        elif isinstance(item, str):
            if len(item) == 1:
                everything_ok = all(map(codification_check, msgs))
                list_of_checks.append(everything_ok)
                continue
            else:
                checker(item, list_of_checks)

        else:
            print("Something went wrong!")

    return all(list_of_checks)


def determ_change_lang_keys():
    keyboard = Controller()

    for key_str in [Key.ctrl_l, Key.alt_l]:

        keyb_layout = get_keyboard_layout_name()

        with keyboard.pressed(Key.shift):
            keyboard.press(key_str)
            sleep_key(0.0001)
            keyboard.release(key_str)
            sleep_key(0.0001)
    
        new_keyb_layout = get_keyboard_layout_name()

        if keyb_layout == new_keyb_layout:
            continue
        else:
            return [key_str, Key.shift]


def language_we_happy():
        
    first_key, second_key = determ_change_lang_keys()
    print(first_key, second_key)

    while True:
        keyboard = Controller()
        if checker(quick_chat_messages, []):
            break
        else:
            sleep_key(0.0001)
            with keyboard.pressed(second_key):
                keyboard.press(first_key)
                sleep_key(0.0001)
                keyboard.release(first_key)
                sleep_key(0.0001)

if __name__ == '__main__':
    print(checker(quick_chat_messages, []))
    #language_we_happy()
    sleep_key(2)
    print(checker(quick_chat_messages, []))