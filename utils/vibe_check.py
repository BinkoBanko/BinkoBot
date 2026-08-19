"""
utils/vibe_check.py

Shared helper for reading a user's current vibe from disk and providing a
standard blocked-command reply when a vibe gate is not met.
"""

from __future__ import annotations

import json
import os

import discord

_VIBES_FILE = "data/user_vibes.json"


def get_user_vibe(user_id) -> str | None:
    """Return the stored vibe for *user_id*, or None if not set."""
    if not os.path.exists(_VIBES_FILE):
        return None
    try:
        with open(_VIBES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(str(user_id), {}).get("vibe")
    except (json.JSONDecodeError, OSError):
        return None


async def vibe_gate(
    interaction: discord.Interaction,
    allowed_vibes: list[str],
    blocked_msg: str,
) -> bool:
    """Check the caller's vibe and reply with *blocked_msg* when it is blocked.

    Returns True when the command should proceed, False when blocked.
    The reply is always ephemeral so the rejection is private.
    """
    vibe = get_user_vibe(interaction.user.id)
    if vibe in allowed_vibes:
        return True

    hint = ", ".join(f"**{v}**" for v in allowed_vibes)
    full_msg = f"{blocked_msg}\n*(This command requires one of: {hint})*"

    if interaction.response.is_done():
        await interaction.followup.send(full_msg, ephemeral=True)
    else:
        await interaction.response.send_message(full_msg, ephemeral=True)
    return False
