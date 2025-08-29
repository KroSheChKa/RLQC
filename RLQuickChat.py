import sys
import ctypes
from win32api import keybd_event, GetKeyState
from pynput.keyboard import Controller, Key, KeyCode
import time
from config import *
from random import choice
from lang_determ import *
from PyQt5.QtWidgets import QApplication
from visuals import FramelessOverlay
import win32gui
import win32con

# Check whether the key is pressed
def is_key_pressed(key):
    #return ctypes.windll.user32.GetKeyState(key) & 0x8000 != 0
    return ctypes.windll.user32.GetAsyncKeyState(key) & 0x8000 != 0


# Safely exit the script
def safe_exit():
    capslock_state = GetKeyState(0x14) & 0x0001
    # Do not touch CapsLock on exit

    # Releasing keys that might be pressed
    for _, key_code in key_bindings.items():
        keybd_event(key_code, 0, KEYEVENTF_KEYUP, 0)
        sleep_key(1 / MONITOR_REFRESH_RATE)

    # Restore initial keyboard layout once
    try:
        if initial_keyboard_layout is not None and lang_switch_keys is not None:
            tries = 0
            while get_keyboard_layout_name() != initial_keyboard_layout and tries < 20:
                press_lang_switch(lang_switch_keys[0], lang_switch_keys[1])
                sleep_key(0.02)
                tries += 1
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
    INTERFACE_SCALE = 100
    default = {'left':16,'top':470,'width':395,'height':260}
    left = int(default['left'] * INTERFACE_SCALE/100)
    top = int(default['top'] * INTERFACE_SCALE/100)
    width = int(default['width'] * INTERFACE_SCALE/100)
    height = int(default['height'] * INTERFACE_SCALE/100)
    wp = {'left':left,'top':top,'width':width,'height':height}

    overlay_app = QApplication(sys.argv)
    overlay_win = FramelessOverlay(wp)
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
    # Prepare four random static phrases (no training code appenders)
    overlay_msgs = []
    for sub_idx in range(4):
        options = quick_chat_messages[first_click][sub_idx]
        # For category index 1 (COMPLIMENTS), sub 0 and 3 have training-code prompts at index 0
        if first_click == 1 and sub_idx in (0, 3) and len(options) > 1:
            msg = choice(options[1:])
        else:
            msg = choice(options)
        overlay_msgs.append(msg)

    # Show overlay for the chosen category with pre-selected messages and start the timer
    overlay_show_for_category(first_click, overlay_msgs)
    start_time = time.time()
    fade_out_started = False

    try:
        while True:
            overlay_pump_events()
            # Iterate to detect next keystroke
            for key in quick_buttons_iterate:
                if is_key_pressed(key):

                    # Instantly release the key (avoid false detection)
                    keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
                    
                    second_key = quick_buttons_iterate.index(key)

                    # Visual selection feedback: bold chosen line, then fade out
                    try:
                        # White color for selected text, configurable weight
                        overlay_win.set_selected_style(second_key, weight=65, color="#FFFFFF")
                        overlay_pump_events()
                    except Exception:
                        pass

                    # Text that should be typed in chat equals the displayed option
                    text_message = overlay_msgs[second_key]

                    # Start faster fade-out while we begin typing (0.2s quicker)
                    overlay_hide(duration_ms=119)

                    # Type the message in chat
                    paste_in_chat(text_message, first_click)
                    return

            # ExitKey pressed during the loop? - exit the entire program
            if is_key_pressed(key_bindings['RLAC_END']):
                safe_exit()

            # Check the timer
            current_time = time.time()
            elapsed_time = current_time - start_time

            # Start early fade-out 0.2s before timeout
            if not fade_out_started and elapsed_time >= max(0.0, WAIT_TIME_SECOND_CLICK - 0.2):
                fade_out_started = True
                overlay_hide()

            # If the time has run out, exit the loop
            if elapsed_time >= WAIT_TIME_SECOND_CLICK:
                return
    finally:
        overlay_hide()


# Quickly type message in chat
def paste_in_chat(txt_msg, chat):

    # Prepare layout variables once (no switching yet)
    global initial_keyboard_layout, lang_switch_keys
    if initial_keyboard_layout is None:
        try:
            initial_keyboard_layout = get_keyboard_layout_name()
            lang_switch_keys = determ_change_lang_keys()
        except Exception:
            initial_keyboard_layout, lang_switch_keys = None, None
    # Do not touch CapsLock anymore

    while not(is_key_pressed(key_bindings['RLAC_END'])):
        overlay_hide()
        
        # Determine in what chat we need to type
        if chat:
            chat_type = key_bindings['TEXT_CHAT_ALL']
        else:
            chat_type = key_bindings['TEXT_CHAT_PARTY']
        
        # Open the chat — slightly increased delays to avoid truncation on rapid key sequences
        # sleep_key(0.023)
        keybd_event(chat_type, 0, 0, 0)
        sleep_key(0.001)
        keybd_event(chat_type, 0, KEYEVENTF_KEYUP, 0)
        sleep_key(0.02)

        # Ensure English layout AFTER chat field receives focus (game may reset layout)
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
            letter_vk = KeyCode().from_vk(VkKeyScan_(letter))

            # Check if the key needs to be written with the shift pressed
            if letter.isupper() or letter in shift_symbols:

                # Press the key with shift pressed
                with keyboard.pressed(Key.shift):
                    keyboard.press(letter_vk)
                    sleep_key(0.0005)
                    keyboard.release(letter_vk)

            # Else just press like a usuall button
            else:
                keyboard.press(letter_vk)
                sleep_key(0.0005)
                keyboard.release(letter_vk)
            sleep_key(0.0005)

        # Successfully send the message by pressing enter
        keybd_event(key_bindings['ENTER'], 0, 0, 0)
        sleep_key()
        keybd_event(key_bindings['ENTER'], 0, KEYEVENTF_KEYUP, 0)

        # Keep English layout during runtime; do not restore per-message
        sleep_key(0.05)
        return


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

    # Press F1 to start the code
    while not(is_key_pressed(key_bindings['RLAC_START'])):
        pass
    keybd_event(key_bindings['RLAC_START'], 0, KEYEVENTF_KEYUP, 0)

    # Get info about CapsLock key state
    capslock_state = GetKeyState(0x14) & 0x0001

    # Change the CapsLock flag if the key's state is 1
    if capslock_state:
        global capslock_flag
        capslock_flag = not(capslock_flag)

    # Waiting for pressing the quick chat button
    while True:
        overlay_pump_events()
        for key in quick_buttons_iterate:
            if is_key_pressed(key):

                # Instantly release the key (avoid false detection)
                keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
                second_click(quick_buttons_iterate.index(key))
                break
    
        # Check wether the exit button pressed
        if is_key_pressed(key_bindings['RLAC_END']):
            safe_exit()

        sleep_key(0.001)

if __name__ =='__main__':
    
    keyboard = Controller()

    main()
