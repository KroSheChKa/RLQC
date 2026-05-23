"""
preflight.py — read-only sanity checks against the user's Rocket
League configuration before RLQC starts its main loop.

The rule of this module: **never modify anything**. We open files
in read mode only, we don't touch the game's profile, we don't
spawn helper processes. If something looks off, we surface a
human-readable warning and let the user fix it themselves. The
script keeps running unless the user explicitly chooses to quit
when shown the warnings.

What we check today
-------------------
1.  **Can we find the RL config folder?** Required for everything
    else. If missing, auto-detection is disabled but the script
    can still run on whatever is in `config.py`.
2.  **Display mode.** True exclusive fullscreen (Fullscreen=True +
    Borderless=False in `TASystemSettings.ini`) defeats every
    overlay tool in existence, ours included. The user has to
    switch to Borderless in RL's video settings.
3.  **Quick-chat key collision.** We can't read RL's profile-side
    "Quick Chat Off/Friends/Teammates/Everyone" setting from disk
    (it lives in the cloud profile, not the local INI), so we use
    a proxy: did RL bind ChatPreset1..4 to the same physical keys
    that RLQC listens on? If yes, the user must either set the
    in-game Quick Chat to Off or remap one set of keys, otherwise
    both chats fire on every press.

What this module deliberately does NOT do
------------------------------------------
* Modify `config.py`. Detected overrides are returned in the
  report and applied to `key_bindings` in memory only.
* Modify any of RL's `.ini` files. See TODO.md #4 — we explicitly
  scoped that out after Phase A discovery; the "auto-disable
  in-game Quick Chat" idea probably isn't possible from disk and
  warning-the-user is a strictly better UX anyway.
* Open any GUI. Presentation is the caller's job — see
  `RLQuickChat.py::main()` for how it gets shown.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rl_config import (
    _SECTION_RE,
    _read_text_safely,
    discover_quick_chat_bindings,
    find_rl_config_dir,
)


# Local user state — separate from `config.py` on purpose. We
# promised not to touch the user-editable config file, so things
# like "I've dismissed this warning, stop nagging me" go here.
# This file is regenerated on demand and safe to delete.
_STATE_PATH = Path(__file__).resolve().parent / ".rlqc_state.json"


def _load_state() -> dict:
    try:
        return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    try:
        _STATE_PATH.write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def dismissed_warning_ids() -> set[str]:
    """IDs the user has previously chosen to silence."""
    state = _load_state()
    return set(state.get("dismissed_warnings", []))


def dismiss_warnings(ids) -> None:
    """Persist `ids` as dismissed. No-op for an empty iterable."""
    ids = list(ids)
    if not ids:
        return
    state = _load_state()
    existing = set(state.get("dismissed_warnings", []))
    existing.update(ids)
    state["dismissed_warnings"] = sorted(existing)
    _save_state(state)


# Category keys we own. Sub-category keys are the same physical
# keys (the menu uses the second press to pick a phrase within
# the chosen category), so checking the four category keys for
# collisions also covers the sub-category case.
_RL_CATEGORY_BINDINGS = (
    "INFORMATION(TEAM)",
    "COMPLIMENTS",
    "REACTIONS",
    "APOLOGIES",
)


@dataclass
class PreflightWarning:
    """One thing the user should know about before continuing.

    `id` is a stable string so a "Don't show this again" choice
    survives across runs (state stored in `.rlqc_state.json`);
    `title` is the short headline shown bold in the dialog;
    `detail` is the longer "why this matters" explanation;
    `fix_hint` is the concrete "click here in RL to fix it" step.
    """
    id: str
    title: str
    detail: str
    fix_hint: str


@dataclass
class PreflightReport:
    """Result of `run_preflight()`. Everything the caller needs."""

    config_dir: Optional[Path] = None
    detected_bindings: dict[str, int] = field(default_factory=dict)
    warnings: list[PreflightWarning] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------
def _read_system_settings_section(cfg_dir: Path) -> dict[str, str]:
    """Read `[SystemSettings]` from `TASystemSettings.ini` as a flat dict.

    UE3 settings files can have duplicate keys across sections
    (`Fullscreen=True` appears in several quality-bucket sections);
    we only care about the active one in `[SystemSettings]`.
    """
    path = cfg_dir / "TASystemSettings.ini"
    text = _read_text_safely(path)
    if text is None:
        return {}

    out: dict[str, str] = {}
    in_section = False
    for raw in text.splitlines():
        m = _SECTION_RE.match(raw)
        if m:
            in_section = m.group("name").strip() == "SystemSettings"
            continue
        if not in_section or "=" not in raw:
            continue
        k, _, v = raw.partition("=")
        out[k.strip()] = v.strip()
    return out


def _check_display_mode(report: PreflightReport) -> None:
    """Add a warning if RL is set to exclusive fullscreen.

    Combinations and what they mean for us:
        Fullscreen=True  + Borderless=False -> exclusive fullscreen, WE BREAK.
        Fullscreen=True  + Borderless=True  -> borderless fullscreen, fine.
        Fullscreen=False + Borderless=True  -> borderless window, fine.
        Fullscreen=False + Borderless=False -> small window, fine
                                               (overlay still draws).
    """
    if report.config_dir is None:
        return
    s = _read_system_settings_section(report.config_dir)
    if not s:
        return

    fullscreen = s.get("Fullscreen", "").lower() == "true"
    borderless = s.get("Borderless", "").lower() == "true"

    if fullscreen and not borderless:
        report.warnings.append(PreflightWarning(
            id="exclusive_fullscreen",
            title="Rocket League is in exclusive fullscreen mode",
            detail=(
                "RLQC draws its quick-chat overlay as a normal Windows "
                "window. Exclusive fullscreen bypasses the desktop "
                "compositor, which means our overlay will be invisible "
                "the moment you alt-tab back to the game."
            ),
            fix_hint=(
                "Rocket League: Settings → Video → Display Mode → "
                "Borderless. There's no performance cost; almost every "
                "overlay tool (Discord, OBS, Steam) expects this mode."
            ),
        ))


def _check_quickchat_collision(
    report: PreflightReport,
    current_bindings: dict[str, int],
) -> None:
    """Add an *advisory* warning if RL's quick-chat keys overlap with ours.

    Important context: the user-facing "Quick Chat Off / Friends /
    Teammates / Everyone" toggle is stored in RL's binary cloud
    save (`SaveData/DBE_Production/<SteamID>_*.save`) and CANNOT
    be read from outside the game with any reasonable amount of
    effort. So this check cannot say "your quick chat IS on" with
    certainty — only "they share keys, and IF it's still on, both
    chats will fire". The wording reflects that.

    The user can dismiss this warning permanently via the
    "Don't show this again" button in the preflight dialog —
    state is persisted in `.rlqc_state.json`. Delete that file
    to bring all dismissed warnings back.
    """
    if not report.detected_bindings:
        return

    collisions = []
    for name in _RL_CATEGORY_BINDINGS:
        rl_vk = report.detected_bindings.get(name)
        our_vk = current_bindings.get(name)
        if rl_vk is not None and our_vk is not None and rl_vk == our_vk:
            collisions.append(name)
    if not collisions:
        return

    report.warnings.append(PreflightWarning(
        id="quickchat_collision",
        title="Heads-up: RL's chat presets share keys with RLQC",
        detail=(
            "Rocket League has its built-in quick chat bound to the "
            "same physical keys RLQC listens on (categories: "
            + ", ".join(collisions)
            + "). <b>If</b> your in-game Quick Chat is set to anything "
            "other than 'Off', pressing one of these keys will trigger "
            "BOTH the game's default phrase and the one configured in "
            "RLQC. <i>We can't read that setting directly</i> — it "
            "lives in RL's binary cloud save, not in any text config "
            "— so this is a heads-up rather than a confirmed problem."
        ),
        fix_hint=(
            "If you haven't already done it: Rocket League → Settings "
            "→ Chat → Quick Chat → Off. If you've already done it and "
            "everything works, just click 'Don't show this again' below."
        ),
    ))


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------
def run_preflight(current_bindings: dict[str, int]) -> PreflightReport:
    """Run every read-only check; return a populated report.

    `current_bindings` is the script's `key_bindings` dict — used
    by the collision check to compare against what RL has bound.
    """
    report = PreflightReport()
    report.config_dir = find_rl_config_dir()

    if report.config_dir is None:
        report.warnings.append(PreflightWarning(
            id="no_config_dir",
            title="Rocket League config folder not found",
            detail=(
                "Couldn't find your RL config under "
                "Documents\\My Games\\Rocket League\\TAGame\\Config "
                "(also tried the OneDrive-redirected variant). "
                "Auto-detection of your in-game key bindings is "
                "disabled. RLQC will still run, using whatever is in "
                "your config.py."
            ),
            fix_hint=(
                "Launch Rocket League at least once with this Windows "
                "account; the game creates the folder on first run."
            ),
        ))
        return report

    report.detected_bindings = discover_quick_chat_bindings() or {}
    _check_display_mode(report)
    _check_quickchat_collision(report, current_bindings)
    return report
