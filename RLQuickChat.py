import sys, ctypes
import win32api, win32con
import time

def is_key_pressed(key):
    return ctypes.windll.user32.GetAsyncKeyState(key) & 0x8000 != 0

def sleep_key(sec, exit_key_code = 0x3A-40, stop = True):
    start_time = time.time()
    
    while True:
        # ExitKey pressed during the loop? - exit the entire program
        if is_key_pressed(exit_key_code) and stop:
            sys.exit()

        current_time = time.time()
        elapsed_time = current_time - start_time
        
        # If the time has run out, exit the loop
        if elapsed_time >= sec:
            return

def paste_in_chat(txt_msg, keys):
    shift_symbols = {'!','@','#','$','%','^','&','*','(',')','{','}','"',':','_','+','<','>','?','~'}
    while not(is_key_pressed(keys['RLAC_END'])):
        uppercase_flag = 1
        sleep_key(0.001)
        win32api.keybd_event(keys['TEXT_CHAT'], 0, 0, 0)
        sleep_key(0.00001)
        win32api.keybd_event(keys['TEXT_CHAT'], 0, win32con.KEYEVENTF_KEYUP, 0)
        sleep_key(0.012) # Safe value
        
        for letter in txt_msg:
            if uppercase_flag == 1 or letter in shift_symbols or letter.isupper():
                # Shift key = 0x10
                win32api.keybd_event(keys['SHIFT'], 0, 0, 0)
                sleep_key(0.00001, keys['RLAC_END'], stop = False)
                win32api.keybd_event(win32api.VkKeyScan(letter), 0, 0, 0)
                sleep_key(0.00001, keys['RLAC_END'], stop = False)
                win32api.keybd_event(win32api.VkKeyScan(letter), 0, win32con.KEYEVENTF_KEYUP, 0)
                sleep_key(0.00001, keys['RLAC_END'], stop = False)
                win32api.keybd_event(keys['SHIFT'], 0, win32con.KEYEVENTF_KEYUP, 0)
                uppercase_flag = 0
                continue

            #print(i, win32api.VkKeyScan(i))
            win32api.keybd_event(win32api.VkKeyScan(letter), 0, 0, 0)

            sleep_key(0.00001, keys['RLAC_END'], stop = False)
            
            win32api.keybd_event(win32api.VkKeyScan(letter), 0, win32con.KEYEVENTF_KEYUP, 0)

        win32api.keybd_event(keys['ENTER'], 0, 0, 0)

        sleep_key(0.0001, keys['RLAC_END'], stop = False)
        
        win32api.keybd_event(keys['ENTER'], 0, win32con.KEYEVENTF_KEYUP, 0)
        return

def second_click(first, keys, msgs):
    start_time = time.time()
    while True:
        any_key_pressed = [
            is_key_pressed(keys['INFORMATION(TEAM)']),
            is_key_pressed(keys['COMPLIMENTS']),
            is_key_pressed(keys['REACTIONS']),
            is_key_pressed(keys['APOLOGIES'])
        ]
        if any(any_key_pressed):
            key_pressed = any_key_pressed.index(True)
            win32api.keybd_event(0x31 + key_pressed, 0, win32con.KEYEVENTF_KEYUP, 0)
            paste_in_chat(msgs[first][key_pressed], keys)
            

        # ExitKey pressed during the loop? - exit the entire program
        if is_key_pressed(keys['RLAC_END']):
            sys.exit()

        # Check the timer
        current_time = time.time()
        elapsed_time = current_time - start_time

        # If the time has run out, exit the loop
        if elapsed_time >= 2.5:
            return

def main():
    text_messages =[
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
            'That one was close enough',
            'NIEN! NIEN! NIEN!',
            'Holy Wow!',
            'I was calculating that for years!'
            ],
        [
            'Okay...',
            'No problema, noob',
            'Oops, that is your mistake',
            "I'm not sorry. Sorry"
            ]
        ]

    # You can whatch them in that table:
    # https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
    key_bindings = {
        'RLAC_START': 0x70,
        'RLAC_END': 0x71,
        'TEXT_CHAT': 0x54,
        'TEXT_CHAT_PARTY': 0x59,
        'INFORMATION(TEAM)': 0x31,
        'COMPLIMENTS': 0x32,
        'REACTIONS': 0x33,
        'APOLOGIES': 0x34,
        'SHIFT': 0x10,
        'ENTER': 0x0D
        }
    
    # Press P to start the code
    while not(is_key_pressed(key_bindings['RLAC_START'])):
        pass
    win32api.keybd_event(key_bindings['RLAC_START'], 0, win32con.KEYEVENTF_KEYUP, 0)


    while True:
        any_key_pressed = [
            is_key_pressed(key_bindings['INFORMATION(TEAM)']),
            is_key_pressed(key_bindings['COMPLIMENTS']),
            is_key_pressed(key_bindings['REACTIONS']),
            is_key_pressed(key_bindings['APOLOGIES'])
        ]

        if any(any_key_pressed):
            key_pressed = any_key_pressed.index(True)
            win32api.keybd_event(0x31 + key_pressed, 0, win32con.KEYEVENTF_KEYUP, 0)
            second_click(key_pressed, key_bindings, text_messages)
            


if __name__ =='__main__':
    
    main()
