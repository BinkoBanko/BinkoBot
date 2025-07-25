import discord
import json
import os

def load_dm_preferences():
    path = "data/dm_preferences.json"
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

async def send_private_or_public(ctx, message, file=None):
    """Send a message respecting a user's DM preference.

    ``ctx`` may be either a ``commands.Context`` or ``discord.Interaction``.
    ``message`` is the content to send and ``file`` an optional file attachment.
    """

    prefs = load_dm_preferences()

    user = getattr(ctx, "author", None) or getattr(ctx, "user", None)
    if user is None:
        raise TypeError("ctx must be a commands.Context or discord.Interaction")

    send_dm = prefs.get(str(user.id), False)

    async def send_channel(msg, file=None):
        if hasattr(ctx, "send"):
            await ctx.send(msg, file=file)
        elif hasattr(ctx, "response"):
            if not ctx.response.is_done():
                await ctx.response.send_message(msg, file=file)
            else:
                await ctx.followup.send(msg, file=file)

    try:
        if send_dm:
            if file:
                await user.send(message, file=file)
            else:
                await user.send(message)

            if hasattr(ctx, "response"):
                if not ctx.response.is_done():
                    await ctx.response.send_message("📩 Sent in DMs", ephemeral=True)
                else:
                    await ctx.followup.send("📩 Sent in DMs", ephemeral=True)
        else:
            await send_channel(message, file)
    except discord.Forbidden:
        await send_channel("I tried to DM you but couldn’t~ Here’s your message publicly instead.")
        await send_channel(message, file)
