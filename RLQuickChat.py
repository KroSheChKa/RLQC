import sys
import ctypes
from win32api import keybd_event, VkKeyScan, GetKeyState
import time
from config import *
from random import choice


# Check whether the key is pressed
def is_key_pressed(key):
    #return ctypes.windll.user32.GetKeyState(key) & 0x8000 != 0
    return ctypes.windll.user32.GetAsyncKeyState(key) & 0x8000 != 0


# Safely exit the script by releasing keys and returning CapsLock to def.val.
def safe_exit():
    if capslock_flag != capslock_light:
        keybd_event(0x14, 0, 0, 0)
        sleep_key(1 / MONITOR_REFRESH_RATE)
        keybd_event(0x14, 0, KEYEVENTF_KEYUP, 0)
    #capslock_fuse(capslock_flag, return_to_default = True)
    for _, key_code in key_bindings.items():
        keybd_event(key_code, 0, KEYEVENTF_KEYUP, 0)
        sleep_key(1 / MONITOR_REFRESH_RATE)
    sys.exit()


# Sleep func. that you could stop by pressing the stop key
def sleep_key(sec = 0.00001):
    start_time = time.time()
    
    while True:
        # ExitKey pressed during the loop? - exit the entire program
        if is_key_pressed(key_bindings['RLAC_END']):
            safe_exit()

        current_time = time.time()
        elapsed_time = current_time - start_time
        
        # If the time has run out, exit the loop
        if elapsed_time >= sec:
            return


# The function that remembers latest pressed keys
def save_latest_keys():
    # Here we store them
    list_of_pressed_keys = []

    # Iterate to find pressed keys
    for key_name, key_code in active_RL_keyboard_keys.items():
        if is_key_pressed(key_code):
            list_of_pressed_keys.append(key_name)

    return list_of_pressed_keys


# Expecting a second click after the first
def second_click(first_click):
    # Start the timer
    start_time = time.time()

    while True:
        # Iterate to detect next button
        for key in quick_buttons_iterate:
            if is_key_pressed(key):

                # Instantly release the key (avoid false detection)
                keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
                
                second_key = quick_buttons_iterate.index(key)

                # Save the latest pressed buttons before the typing in chat
                #list_of_pressed_keys = save_latest_keys()

                # Text that should be typed in chat
                text_message = choice(quick_chat_messages[first_click][second_key])

                # Check whether we need to add map codes
                if text_message == quick_chat_2_1[0]:
                    text_message = text_message + choice(shooting_trainig_map_codes)
                elif text_message == quick_chat_2_4[0]:
                    text_message = text_message + choice(defence_trainig_map_codes)
                
                # Type the message in chat
                paste_in_chat(text_message, first_click)

                # Press again the keys
                # for key_name in list_of_pressed_keys:
                #     keybd_event(active_RL_keyboard_keys[key_name], 0, 0, 0)
                
                return

        # ExitKey pressed during the loop? - exit the entire program
        if is_key_pressed(key_bindings['RLAC_END']):
            safe_exit()

        # Check the timer
        current_time = time.time()
        elapsed_time = current_time - start_time

        # If the time has run out, exit the loop
        if elapsed_time >= WAIT_TIME_SECOND_CLICK:
            return


# Quickly typing message in chat
def paste_in_chat(txt_msg, chat):

    capslock_state = GetKeyState(0x14) & 0x0001

    if capslock_state:
        keybd_event(0x14, 0, 0, 0)
        sleep_key(1 / MONITOR_REFRESH_RATE)
        keybd_event(0x14, 0, KEYEVENTF_KEYUP, 0)

        global capslock_light
        global capslock_flag

        capslock_light = not(capslock_light)
        capslock_flag = not(capslock_flag)

    while not(is_key_pressed(key_bindings['RLAC_END'])):
        
        # Determine in what chat we need to type
        if chat:
            chat_type = key_bindings['TEXT_CHAT_ALL']
        else:
            chat_type = key_bindings['TEXT_CHAT_PARTY']
        
        # Open the chat
        sleep_key()
        keybd_event(chat_type, 0, 0, 0)
        sleep_key()
        keybd_event(chat_type, 0, KEYEVENTF_KEYUP, 0)
        sleep_key(0.013)
        
        # Iterate over each letter in text message
        for letter in txt_msg:

            # Get the code of a key
            letter_VK = VkKeyScan(letter)
            sleep_key()

            # Check if the key needs to be written with the shift pressed
            if letter in shift_symbols or letter.isupper():

                # Press and hold shift
                keybd_event(key_bindings['SHIFT'], 0, 0, 0)
                sleep_key()

                # Click button that needed shift
                keybd_event(letter_VK, 0, 0, 0)
                sleep_key()
                keybd_event(letter_VK, 0, KEYEVENTF_KEYUP, 0)
                sleep_key()

                # Release shift
                keybd_event(key_bindings['SHIFT'], 0, KEYEVENTF_KEYUP, 0)


            # Else just press like a usuall button
            else:
                keybd_event(letter_VK, 0, 0, 0)
                sleep_key()
                keybd_event(letter_VK, 0, KEYEVENTF_KEYUP, 0)

        # Successfully send the message by pressing enter
        keybd_event(key_bindings['ENTER'], 0, 0, 0)
        sleep_key()
        keybd_event(key_bindings['ENTER'], 0, KEYEVENTF_KEYUP, 0)

        sleep_key(0.05)
        return


def main():
    # Press F1 to start the code
    while not(is_key_pressed(key_bindings['RLAC_START'])):
        pass
    keybd_event(key_bindings['RLAC_START'], 0, KEYEVENTF_KEYUP, 0)

    capslock_state = GetKeyState(0x14) & 0x0001

    if capslock_state:
        global capslock_flag
        capslock_flag = not(capslock_flag)

    # Waiting for pressing the quick chat button
    while True:
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
    
    main()
