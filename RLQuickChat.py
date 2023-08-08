import sys
import ctypes
from win32api import keybd_event, VkKeyScan
import time

"""----------------------- Constants -----------------------"""

quick_chat_messages = [
        [
            'Dear mate, let me take that kickoff!',
            'Please mate, take that shot!',
            "I'm here!",
            'I will defend for you!'
            ],
        [
            'Dddaaamn! That shot!',
            'Incredible pass!',
            'Thanks a lot!',
            'Bruh, that save as shitty as your skill!'
            ],
        [
            'That one was close enough.',
            'NIEN! NIEN! NIEN!',
            'Holy Wow!',
            'I was calculating that for years!'
            ],
        [
            'Okay...',
            'No problema, noob.',
            'Oops, that is your mistake.',
            "I'm not sorry. Sorry."
            ]
        ]

# Values set due that table:
# https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
key_bindings = {
        'RLAC_START': 0x70,
        'RLAC_END': 0x71,
        'TEXT_CHAT_ALL': 0x54,
        'TEXT_CHAT_PARTY': 0x59,
        'INFORMATION(TEAM)': 0x31,
        'COMPLIMENTS': 0x32,
        'REACTIONS': 0x33,
        'APOLOGIES': 0x34,
        'SHIFT': 0x10,
        'ENTER': 0x0D
        }

# Symbols that need to be printed with shift pressed
shift_symbols = {
            '!','@','#','$','%','^','&','*','(',')',
            '{','}','"',':','_','+','<','>','?','~'
            }

KEYEVENTF_KEYUP = 0x0002

"""---------------------------------------------------------"""

# Check whether the key is pressed
def is_key_pressed(key):
    return ctypes.windll.user32.GetAsyncKeyState(key) & 0x8000 != 0


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
            print('Im out sys3')
            safe_exit()

        current_time = time.time()
        elapsed_time = current_time - start_time
        
        # If the time has run out, exit the loop
        if elapsed_time >= sec:
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

                continue

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
            print('Im out sys2')
            safe_exit()

        # Check the timer
        current_time = time.time()
        elapsed_time = current_time - start_time

        # If the time has run out, exit the loop
        if elapsed_time >= 2.5:
            return
        
        # Type corresponding message if pressed button
        if any(any_key_pressed):
            key_pressed = any_key_pressed.index(True)
            keybd_event(key_bindings['INFORMATION(TEAM)'] + key_pressed,
                        0, KEYEVENTF_KEYUP, 0)
            paste_in_chat(quick_chat_messages[first_click][key_pressed],
                          first_click)
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
            print('Im out sys1')
            safe_exit()

        sleep_key(0.1)


if __name__ =='__main__':
    
    main()
