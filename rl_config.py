"""
rl_config.py — discovery utilities for Rocket League's per-user config.

Phase A scope (current implementation):
    * Locate the RL Config directory on this machine.
    * Read `TAInput.ini` and pull every `PCBindings=( Action=...,
      Key=... )` row.
    * Identify the quick-chat / text-chat actions and translate
      Unreal's key names to Win32 VK codes so they slot into our
      `key_bindings` dict.
    * Surface chat-related lines in any other config file we find.

Phase A is intentionally READ-ONLY. No `.ini` is modified, no game
process is touched, no values are written back to `config.py`.
Modification + restore (the real auto-setup) lives in a future
phase — see TODO.md #4 for the full plan.

Findings worth remembering (May 2026, calibrated against a real
install on a Steam-version RL):

    * Bindings live in `TAInput.ini` as
        PCBindings=( Action="<RL action>", Key="<UE key name>" )
      Earlier UE3 docs use `Bindings=(Name=..., Command=...)`; RL
      does NOT use that form, so a generic UE3 parser misses
      everything.
    * There are MULTIPLE preset sections — `[ProjectX.ControlPreset_X]`,
      `[Standard ControlPreset_X]`, `[Legacy ControlPreset_X]`, ...
      The user's actively-edited bindings are in `[ProjectX.ControlPreset_X]`;
      the others are unchanged factory defaults the game ships
      with. We prefer ProjectX and fall back to the rest.
    * `TAGame.ini` may NOT exist locally even on a heavy player's
      machine. This means the "Quick Chat Off/Friends/Teammates/
      Everyone" setting is probably stored server-side (profile)
      and CANNOT be flipped from outside the game. Phase B has to
      verify this — if it's true, the "auto-disable in-game quick
      chat" half of TODO #4 turns into "tell the user to remap or
      disable it themselves".

Run directly to see what this script finds on the current machine:

    python rl_config.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Unreal key name -> Win32 VK code
# ---------------------------------------------------------------------------
# Subset of UE3's FKey table, scoped to the keys that can plausibly
# appear in a Rocket League chat binding. Extend when a real preset
# surfaces something new.
UNREAL_KEY_TO_VK: dict[str, int] = {
    # number row (top of keyboard, NOT numpad)
    "Zero": 0x30, "One": 0x31, "Two": 0x32, "Three": 0x33,
    "Four": 0x34, "Five": 0x35, "Six": 0x36, "Seven": 0x37,
    "Eight": 0x38, "Nine": 0x39,

    # letters (UE3 uses single-letter names so 'A' -> VK_A etc.)
    **{c: ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},

    # function keys
    **{f"F{i}": 0x70 + (i - 1) for i in range(1, 13)},

    # navigation
    "Up": 0x26, "Down": 0x28, "Left": 0x25, "Right": 0x27,
    "Home": 0x24, "End": 0x23,
    "PageUp": 0x21, "PageDown": 0x22,
    "Insert": 0x2D, "Delete": 0x2E,

    # editing
    "Enter": 0x0D, "Tab": 0x09, "Escape": 0x1B, "BackSpace": 0x08,
    "SpaceBar": 0x20, "Space": 0x20,

    # modifiers
    "LeftShift": 0xA0, "RightShift": 0xA1,
    "LeftControl": 0xA2, "RightControl": 0xA3,
    "LeftAlt": 0xA4, "RightAlt": 0xA5,

    # symbols on US layout (OEM_* codes differ by layout but the
    # codes below match UE3's defaults)
    "Tilde": 0xC0, "Equals": 0xBB, "Hyphen": 0xBD,
    "LeftBracket": 0xDB, "RightBracket": 0xDD,
    "Backslash": 0xDC, "Semicolon": 0xBA, "Quote": 0xDE,
    "Comma": 0xBC, "Period": 0xBE, "Slash": 0xBF,

    # mouse — RL lists these in input bindings; never relevant for
    # text/quick chat but mapping is cheap and avoids confusing
    # None returns.
    "LeftMouseButton": 0x01, "RightMouseButton": 0x02,
    "MiddleMouseButton": 0x04,
    "ThumbMouseButton": 0x05, "ThumbMouseButton2": 0x06,
}


def unreal_key_to_vk(name: str) -> Optional[int]:
    """Translate an Unreal key name to a Win32 virtual-key code.

    Returns None for gamepad / Steam Input names (e.g.
    'XboxTypeS_DPad_Up') and anything else without a keyboard
    equivalent.
    """
    return UNREAL_KEY_TO_VK.get(name)


# ---------------------------------------------------------------------------
# Mapping: RL's internal action names -> our config.py key_bindings keys
# ---------------------------------------------------------------------------
# In `config.py` the user labels go like:
#     'TEXT_CHAT_ALL', 'TEXT_CHAT_PARTY',
#     'INFORMATION(TEAM)', 'COMPLIMENTS', 'REACTIONS', 'APOLOGIES'
# RL doesn't use those names internally; it uses:
#     'Chat', 'TeamChat', 'PartyChat',
#     'ChatPreset1', 'ChatPreset2', 'ChatPreset3', 'ChatPreset4'
#
# Subtle: our `TEXT_CHAT_PARTY` is bound to RL's `TeamChat`
# (defaults to Y), NOT RL's `PartyChat` (defaults to U). The naming
# clash is unfortunate but historical — we keep the user's existing
# config.py labels and only re-route through this map.
RL_ACTION_TO_BINDING: dict[str, str] = {
    "Chat":         "TEXT_CHAT_ALL",
    "TeamChat":     "TEXT_CHAT_PARTY",
    "ChatPreset1":  "INFORMATION(TEAM)",
    "ChatPreset2":  "COMPLIMENTS",
    "ChatPreset3":  "REACTIONS",
    "ChatPreset4":  "APOLOGIES",
    # Note: there's no RL action for our `CUSTOM` slot (key '5'). It
    # is an RLQC-only extension — must stay user-configurable.
}


# ---------------------------------------------------------------------------
# Locating the Config folder
# ---------------------------------------------------------------------------
def find_rl_config_dir() -> Optional[Path]:
    """Locate the per-user Rocket League Config directory.

    UE3 writes per-user config under the Documents folder regardless
    of where the game itself was installed (Steam / Epic / Microsoft
    Store all share this path). Many modern Windows installs redirect
    Documents into OneDrive, so we try both candidates and return
    the first one that actually exists.
    """
    candidates = [
        Path.home() / "Documents" / "My Games" / "Rocket League" / "TAGame" / "Config",
        Path.home() / "OneDrive" / "Documents" / "My Games" / "Rocket League" / "TAGame" / "Config",
    ]
    for p in candidates:
        if p.is_dir():
            return p
    return None


def _read_text_safely(path: Path) -> Optional[str]:
    """Read a .ini file as UTF-8, replacing any undecodable bytes."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Parsing TAInput.ini
# ---------------------------------------------------------------------------
# Section header: [Some.Name] OR [Standard ControlPreset_X] (yes, with a space).
_SECTION_RE = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*$")

# PCBindings row — keyboard binding only. Whitespace inside the
# parens is generous; values are always double-quoted.
_PC_BINDING_RE = re.compile(
    r'^\s*PCBindings\s*=\s*\(\s*'
    r'Action\s*=\s*"(?P<action>[^"]+)"\s*,\s*'
    r'Key\s*=\s*"(?P<key>[^"]+)"\s*\)',
    re.IGNORECASE,
)

# Section names we look at, in priority order. ProjectX is where the
# user's customisations end up; the others are factory defaults the
# game ships with.
_PRESET_SECTIONS_PRIORITY = (
    "ProjectX.ControlPreset_X",
    "Standard ControlPreset_X",
    "Legacy ControlPreset_X",
    "OldClassic ControlPreset_X",
)


def parse_pc_bindings(ini_text: str) -> dict[str, dict[str, str]]:
    """Return `{section_name: {action: key_name}}` for all PCBindings rows.

    Key order within a section is preserved by ordinary insertion
    order (Python 3.7+). Useful when there are duplicate Action rows
    in a single section — the last write wins, which matches what
    Rocket League itself does at load time.
    """
    out: dict[str, dict[str, str]] = {}
    current_section: Optional[str] = None
    for raw in ini_text.splitlines():
        m_sec = _SECTION_RE.match(raw)
        if m_sec:
            current_section = m_sec.group("name").strip()
            continue
        if current_section is None:
            continue
        m_bind = _PC_BINDING_RE.match(raw)
        if m_bind:
            sec_map = out.setdefault(current_section, {})
            sec_map[m_bind.group("action")] = m_bind.group("key")
    return out


def pick_active_preset(
    parsed: dict[str, dict[str, str]],
) -> tuple[Optional[str], dict[str, str]]:
    """Return `(section_name, action_map)` for whichever preset wins.

    Priority is `_PRESET_SECTIONS_PRIORITY`; if none of them contain
    PCBindings, fall back to the first non-empty section we saw at
    all.
    """
    for name in _PRESET_SECTIONS_PRIORITY:
        if parsed.get(name):
            return name, parsed[name]
    for name, m in parsed.items():
        if m:
            return name, m
    return None, {}


def discover_quick_chat_bindings() -> Optional[dict[str, int]]:
    """End-to-end: locate config, parse it, return overrides for `key_bindings`.

    Returns a dict shaped like RLQC's existing `key_bindings` — only
    populated with entries we were able to look up — e.g.

        {'TEXT_CHAT_ALL': 0x54, 'COMPLIMENTS': 0x32, ...}

    Returns None if the Config folder or TAInput.ini is missing
    entirely. Returns an empty dict if files are there but nothing
    relevant parsed (so the caller can tell "no data" apart from
    "data, but no useful actions").
    """
    cfg = find_rl_config_dir()
    if cfg is None:
        return None
    tainput = cfg / "TAInput.ini"
    if not tainput.is_file():
        return None
    text = _read_text_safely(tainput)
    if text is None:
        return None

    parsed = parse_pc_bindings(text)
    _section, active = pick_active_preset(parsed)

    overrides: dict[str, int] = {}
    for rl_action, our_name in RL_ACTION_TO_BINDING.items():
        ue_key = active.get(rl_action)
        if not ue_key:
            continue
        vk = unreal_key_to_vk(ue_key)
        if vk is not None:
            overrides[our_name] = vk
    return overrides


# ---------------------------------------------------------------------------
# CLI entry — dump what we find so the mapping can be built by hand
# ---------------------------------------------------------------------------
def _dump_input_ini(path: Path) -> None:
    text = _read_text_safely(path)
    if text is None:
        print(f"[rl_config] Cannot read {path.name}")
        return

    parsed = parse_pc_bindings(text)
    total_rows = sum(len(m) for m in parsed.values())
    print(f"\n[rl_config] {path.name}: {total_rows} PCBindings row(s) "
          f"across {len(parsed)} section(s).")

    section, active = pick_active_preset(parsed)
    print(f"           Picked active preset: [{section or '—'}]")

    if not active:
        print("           No PCBindings in any known preset section.")
        return

    chat_actions = [
        (a, active[a]) for a in RL_ACTION_TO_BINDING
        if a in active
    ]
    if not chat_actions:
        print("           No chat-related actions in the active preset.")
        return

    print("\n           Quick-chat / text-chat bindings on this machine:")
    print("           {:<14}  {:<6}  {:<14}  {}".format(
        "RL action", "Key", "Our binding", "VK code"))
    print("           " + "-" * 60)
    for action, ue_key in chat_actions:
        vk = unreal_key_to_vk(ue_key)
        vk_repr = f"0x{vk:02X}" if vk is not None else "  N/A "
        our = RL_ACTION_TO_BINDING[action]
        print(f"           {action:<14}  {ue_key:<6}  {our:<14}  {vk_repr}")


def _dump_chat_lines(path: Path) -> None:
    text = _read_text_safely(path)
    if text is None:
        print(f"[rl_config] Cannot read {path.name}")
        return
    refs = [
        line.rstrip()
        for line in text.splitlines()
        if any(n in line.lower() for n in ("chat", "quickchat", "preset"))
    ]
    if not refs:
        print(f"\n[rl_config] {path.name}: nothing chat-related.")
        return

    print(f"\n[rl_config] {path.name}: {len(refs)} chat-related line(s).")
    cap = 30
    for line in refs[:cap]:
        print(f"  {line}")
    if len(refs) > cap:
        print(f"  ... (+{len(refs) - cap} more)")


def main() -> int:
    cfg = find_rl_config_dir()
    if cfg is None:
        print("[rl_config] Rocket League config folder NOT FOUND.")
        print("           Looked under:")
        print("             %USERPROFILE%\\Documents\\My Games\\Rocket League\\TAGame\\Config")
        print("             %USERPROFILE%\\OneDrive\\Documents\\My Games\\...")
        print("           Has Rocket League ever been launched on this account?")
        return 1

    print(f"[rl_config] Config dir: {cfg}")
    files = sorted(cfg.glob("*.ini"))
    print(f"[rl_config] {len(files)} .ini file(s) present:")
    for f in files:
        print(f"  - {f.name}")

    tainput = cfg / "TAInput.ini"
    if tainput.is_file():
        _dump_input_ini(tainput)
    else:
        print("\n[rl_config] TAInput.ini not present — input bindings unavailable.")

    tagame = cfg / "TAGame.ini"
    if tagame.is_file():
        _dump_chat_lines(tagame)
    else:
        print("\n[rl_config] TAGame.ini not present — chat permission likely lives")
        print("           in the cloud profile, not on disk. See module docstring.")

    overrides = discover_quick_chat_bindings()
    if overrides:
        print(f"\n[rl_config] Auto-detected overrides for config.key_bindings:")
        for k, v in overrides.items():
            print(f"             {k!r:<22} = 0x{v:02X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
