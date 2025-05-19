# RLQC (beta)
## Make your qiuck chat uniqie!
❌~~What a save!~~\
❌~~Nice shot!~~\
✔️Here's the code for practicing saves: 2E68-0A19-F54F-D41F\
✔️Nice shot! If you were aiming for the bleachers!

![image](https://github.com/user-attachments/assets/76cdd253-cb88-4a70-8841-8b1074a8791e)
> Guess where is the real **chat menu**

### Advantages of this program:
- Custom comments!
- Easy and familiar message sending, as implemented in Rocket League (4 buttons system + delay to reset the press)
- You can add as many comments as you want to one keyboard shortcut (e.g. 1-1, 2-4 ect.).\
    They will be selected randomly
- A feature that prevents accidental pressing of Caps Lock and subsequent output of a message in uppercase. \
  Also the synchronization of the value and the light indicator on Caps Lock is maintained!
- Safe termination of the script without accidentally unreleased  keys.
- Start and end the program by pressing a button.
- Prevent incorrect emulation of keystrokes on the wrong layout.
> Gamepad support upcoming!

#### Warning: modify text messages at your own risk! You may be banned for obscene language. 

## How to install, customize and launch


Installation
---
A few steps:
- Make sure you have installed [python 3.X](https://www.python.org/downloads/) (Better to download 3.10 or higher.)
- Download it as **.zip**. As an alternative you can clone this project by command below:
```
git clone https://github.com/KroSheChKa/RLQC.git
```
> **Make sure you have downloaded [git](https://git-scm.com/downloads)!**

Open cmd as admin and paste this:
```
pip install -r requirements.txt
```

Customize
----
If you have modified default values in the Rocket League, you should go to the root of the file `config.py` and change the corresponding values.

#### YOU NEED TO EITHER REASSIGN THE KEYS IN THE FILE `config.py`, OR CHANGE THE DEFAULTS IN ROCKET LEAGUE
> Key values you can find in [this table](https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes)

**NOTE:** The default navigation values are set to keys 1 2 3 and 4. I reassigned the quick chat keys in Rocket League to other keys in order to completely replace it in the game with mine, so...
##### You can change:


Time during which the second quick chat key can be pressed
```python
WAIT_TIME_SECOND_CLICK = 2.1
```

The messages themselves. Use your imagination
```python
quick_chat_1_1 = [
    "Dear mate, let me take that kickoff!",
    ...
    ]
quick_chat_1_2 = [
    "Ooh, I have no hands to take that :(",
    ...
    ]
...
```

##### You need to change:

Key values you can find in [this table](https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes)
```python
key_bindings = {
    'RLAC_START': 0x70,
    'RLAC_END': 0x71,
    'TEXT_CHAT_ALL': 0x54,
    'TEXT_CHAT_PARTY': 0x59,
    'INFORMATION(TEAM)': 0x31,
    'COMPLIMENTS': 0x32,
    'REACTIONS': 0x33,
    'APOLOGIES': 0x34,
    ...
```

Launching
---

- Double click on the `RLQuickChat.py` file
- Open Rocket League
- Press the launch button (F1 by default)(F2 to exit the script)
  
*You are free to build friendly relationships with your mates and opponents ;)*

## Need to add/fix
- [ ] **Add** UI for quick chat (UPCOMING!!!!)
- [ ] **Add** gamepad support
- [ ] **Add** language fuse
- [x] **Add** CapsLock fuse
- [x] **Add** randomized training codes in certain message
- [x] **Add** random messages. + new ones
- [x] **Add** variety of messages
---
- [ ] **Fix:** sending a message in chat leads to forgetting the keys pressed at that moment, which interferes with gameplay
- [ ] **Fix** freezes when emulating fast typing
- [x] **Fix:** spontaneous non-pressing of letters in the message (numbers and symbols are printed)
- [x] **Fix** rarely missing symbols
- [x] **Fix** the issue when two messages combine in one
- [x] **Fix:** falsely remembering the last click results in an incorrect follow-up message
---
  
*Any suggestions? You found a bug?*

-> Welcome to [Discussions](https://github.com/KroSheChKa/RLQC/discussions)
