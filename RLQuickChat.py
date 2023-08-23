import sys
import ctypes
from win32api import keybd_event, VkKeyScan
import time
from config import *
from random import choice

# Check whether the key is pressed
def is_key_pressed(key):
    return ctypes.windll.user32.GetKeyState(key) & 0x8000 != 0
    #return ctypes.windll.user32.GetAsyncKeyState(key) & 0x8000 != 0


def safe_exit():
    for _, key_code in key_bindings.items():
        keybd_event(key_code, 0, KEYEVENTF_KEYUP, 0)
        sleep_key(0.00001)
    sys.exit()


# Sleep func. that you could stop by pressing the stop key
def sleep_key(sec):
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


def save_latest_keys():
    list_of_pressed_keys = []
    for key_name, key_code in active_RL_keyboard_keys.items():
        if is_key_pressed(key_code):
            list_of_pressed_keys.append(key_name)
    return list_of_pressed_keys


# Expecting a second click after the first
def second_click(first_click):
    # Start the timer
    start_time = time.time()

    while True:
        # Array is more compact than if statements
        any_key_pressed = [
            is_key_pressed(key_bindings['INFORMATION(TEAM)']),
            is_key_pressed(key_bindings['COMPLIMENTS']),
            is_key_pressed(key_bindings['REACTIONS']),
            is_key_pressed(key_bindings['APOLOGIES'])
        ]
        
        # ExitKey pressed during the loop? - exit the entire program
        if is_key_pressed(key_bindings['RLAC_END']):
            safe_exit()

        # Check the timer
        current_time = time.time()
        elapsed_time = current_time - start_time

        # If the time has run out, exit the loop
        if elapsed_time >= WAIT_TIME_SECOND_CLICK:
            return
        
        # Type corresponding message if pressed button
        if any(any_key_pressed):
            key_pressed = any_key_pressed.index(True)
            keybd_event(key_bindings['INFORMATION(TEAM)'] + key_pressed, 0, KEYEVENTF_KEYUP, 0)

            # Save the latest pressed buttons before the typing in chat
            list_of_pressed_keys = save_latest_keys()

            # Text that should be typed in chat
            text_message = choice(quick_chat_messages[first_click][key_pressed])

            # Check whether we need to add map codes
            if text_message == quick_chat_2_1[0]:
                text_message = text_message + choice(shooting_trainig_map_codes)
            elif text_message == quick_chat_2_4[0]:
                text_message = text_message + choice(defence_trainig_map_codes)
            
            # Type the message in chat
            paste_in_chat(text_message, first_click)

            # Press again the keys
            for key_name in list_of_pressed_keys:
                keybd_event(active_RL_keyboard_keys[key_name], 0, 0, 0)
            return


# Quickly typing message in chat
def paste_in_chat(txt_msg, chat):
    while not(is_key_pressed(key_bindings['RLAC_END'])):
        
        # Determine in what chat we need to type
        if chat:
            chat_type = key_bindings['TEXT_CHAT_ALL']
        else:
            chat_type = key_bindings['TEXT_CHAT_PARTY']
        
        # Open the chat
        sleep_key(0.001)
        keybd_event(chat_type, 0, 0, 0)
        sleep_key(0.00001)
        keybd_event(chat_type, 0, KEYEVENTF_KEYUP, 0)
        sleep_key(0.012)
        

        # Iterate each lette in text message
        for letter in txt_msg:

            # Get the code of
            letter_VK = VkKeyScan(letter)

            # Check if the key needs to be written with the shift key
            if letter in shift_symbols or letter.isupper():

                # Press and hold shift
                keybd_event(key_bindings['SHIFT'], 0, 0, 0)
                sleep_key(0.00001)

                # Click button that needed shift
                keybd_event(letter_VK, 0, 0, 0)
                sleep_key(0.00001)
                keybd_event(letter_VK, 0, KEYEVENTF_KEYUP, 0)
                sleep_key(0.00001)

                # Release shift
                keybd_event(key_bindings['SHIFT'], 0, KEYEVENTF_KEYUP, 0)


            # Else just press like a usuall button
            else:
                keybd_event(letter_VK, 0, 0, 0)
                sleep_key(0.00001)
                keybd_event(letter_VK, 0, KEYEVENTF_KEYUP, 0)

        # Successfully send the message by pressing enter
        keybd_event(key_bindings['ENTER'], 0, 0, 0)
        sleep_key(0.0001)
        keybd_event(key_bindings['ENTER'], 0, KEYEVENTF_KEYUP, 0)

        return


def main():
    # Press P to start the code
    while not(is_key_pressed(key_bindings['RLAC_START'])):
        pass
    keybd_event(key_bindings['RLAC_START'], 0, KEYEVENTF_KEYUP, 0)

    # Waiting for pressing the quick chat button
    while True:
        any_key_pressed = [
            is_key_pressed(key_bindings['INFORMATION(TEAM)']),
            is_key_pressed(key_bindings['COMPLIMENTS']),
            is_key_pressed(key_bindings['REACTIONS']),
            is_key_pressed(key_bindings['APOLOGIES'])
        ]

        # Catch pressing the quick chat button
        if any(any_key_pressed):
            key_pressed = any_key_pressed.index(True)
            keybd_event(key_bindings['INFORMATION(TEAM)'] + key_pressed,
                        0, KEYEVENTF_KEYUP, 0)
            second_click(key_pressed)

        # Check wether the exit button pressed
        if is_key_pressed(key_bindings['RLAC_END']):
            safe_exit()

        sleep_key(0.01)


if __name__ =='__main__':
    
    main()
