# RLQC
## Make your qiuck chat uniqie!
❌~~What a save!~~\
❌~~What a save!~~\
✔️Here's the code for practicing saves: 2E68-0A19-F54F-D41F\
✔️No cap bro you didn't make it...

## How to install, customize and launch


Installation
---
A few steps:
- Make sure you have installed [python 3.X](https://www.python.org/downloads/) (Better to download 3.10 or higher)
- Download it as **.zip**. As an alternative you can clone this project by command below:
```
git clone https://github.com/KroSheChKa/RLQC.git
```
> **Make sure you have downloaded [git](https://git-scm.com/downloads)!**

Customize
---
If you have modified default values in the Rocket League, you should go to the root of the file `RLQuickChat.py` and change the corresponding values.

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
        'SHIFT': 0x10,
        'ENTER': 0x0D
        }
```

---

Time during which the second quick chat key can be pressed
```python
WAIT_TIME_SECOND_CLICK = 2.5
```

---

The messages themselves. Use your imagination
```python
quick_chat_messages = [
        [
            'Dear mate, let me take that kickoff!',
            'Please mate, take that shot!',
            "I'm here!",
            'I will defend for you!'
            ],
        [
            'Dddaaamn! That shot!',
            ...
            ]
        ...
        ]
```

Launching
---

- Double click on the `RLQuickChat.py` file
- Open Rocket League
- Press the launch button (F1 by default)
You are free to build friendly relationships with your mates and opponents ;)

## Need to add/fix
- [ ] **Add** gamepad support
- [ ] **Add** random messages. + new ones
- [ ] **Add** variety of messages
- [ ] **Fix:** A message in chat leads to forgetting the keys pressed at that moment, which interferes with gameplay
- [ ] **Fix:** Last click falsely remembering the last click results in an incorrect follow-up message

---
  
*Any suggestions? You found a flaw?*

-> Welcome to [Discussions](https://github.com/KroSheChKa/SteamEmoticonsFilter/discussions)
