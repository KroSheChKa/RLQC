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
    #print(win32api.VkKeyScan('t'))
    while not(is_key_pressed(keys['RLAC_END'])):
        uppercase_flag = 1
        
        sleep_key(0.001)
                   
        win32api.keybd_event(keys['TEXT_CHAT'], 0, 0, 0)
        sleep_key(0.00001)
        win32api.keybd_event(keys['TEXT_CHAT'], 0, win32con.KEYEVENTF_KEYUP, 0)
        sleep_key(0.012) # Safe value
        
        for letter in txt_msg:
            if uppercase_flag == 1 or letter in '!?@#$%^&*()_+><:"}{~':
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
        if is_key_pressed(keys['INFORMATION(TEAM)']):
            win32api.keybd_event(keys['INFORMATION(TEAM)'], 0, win32con.KEYEVENTF_KEYUP, 0)
            paste_in_chat(msgs[first][0], keys)
            return
        elif is_key_pressed(keys['COMPLIMENTS']):
            win32api.keybd_event(keys['COMPLIMENTS'], 0, win32con.KEYEVENTF_KEYUP, 0)
            paste_in_chat(msgs[first][1], keys)
            return
        elif is_key_pressed(keys['REACTIONS']):
            win32api.keybd_event(keys['REACTIONS'], 0, win32con.KEYEVENTF_KEYUP, 0)
            paste_in_chat(msgs[first][2], keys)
            return
        elif is_key_pressed(keys['APOLOGIES']):
            win32api.keybd_event(keys['APOLOGIES'], 0, win32con.KEYEVENTF_KEYUP, 0)
            paste_in_chat(msgs[first][3], keys)
            return

        # ExitKey pressed during the loop? - exit the entire program
        if is_key_pressed(keys['RLAC_END']):
            sys.exit()


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
            'I will defend for you!'],
        [
            'Dddaaamn! That shot!',
            'Incredible shot!',
            'Thanks a lot!',
            'Bruh, that save as shitty as your skill!'
        ],
        [
            'That one was close enough',
            'NIEN! NIEN! NIEN!',
            'Whata heeeel',
            'I was calculating that for years'
        ],
        [
            'Okay...',
            'No problema, noob',
            'Oops, that is your mistake',
            'Im not sorry. Sorry'
        ]]
    # text_messages = {
    #     '1-1': 'Dear mate, let me take that kickoff!',
    #     '1-2': 'Please mate, take that shot!',
    #     '1-3': '',
    #     '1-4': '',
    #     '2-1': '',
    #     '2-2': '',
    #     '2-3': '',
    #     '2-4': '',
    #     '3-1': '',
    #     '3-2': '',
    #     '3-3': '',
    #     '3-4': '',
    #     '4-1': '',
    #     '4-2': '',
    #     '4-3': '',
    #     '4-4': ''
    #     }

    # You can whatch them in that table:
    # https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
    key_bindings = {
        'RLAC_START': 0x70,
        'RLAC_END': 0x71,
        'TEXT_CHAT': 0x54,
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
        if is_key_pressed(key_bindings['INFORMATION(TEAM)']):
            win32api.keybd_event(key_bindings['INFORMATION(TEAM)'], 0, win32con.KEYEVENTF_KEYUP, 0)
            second_click(0,key_bindings, text_messages)
            
        elif is_key_pressed(key_bindings['COMPLIMENTS']):
            win32api.keybd_event(key_bindings['COMPLIMENTS'], 0, win32con.KEYEVENTF_KEYUP, 0)
            second_click(1,key_bindings, text_messages)

        elif is_key_pressed(key_bindings['REACTIONS']):
            win32api.keybd_event(key_bindings['REACTIONS'], 0, win32con.KEYEVENTF_KEYUP, 0)
            second_click(2,key_bindings, text_messages)
            
        elif is_key_pressed(key_bindings['APOLOGIES']):
            win32api.keybd_event(key_bindings['APOLOGIES'], 0, win32con.KEYEVENTF_KEYUP, 0)
            second_click(3,key_bindings, text_messages)

if __name__ =='__main__':
    
    main()
