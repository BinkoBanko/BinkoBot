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
    prefs = load_dm_preferences()
    uid = str(ctx.author.id)
    send_dm = prefs.get(uid, False)

    try:
        if send_dm:
            if file:
                await ctx.author.send(message, file=file)
            else:
                await ctx.author.send(message)
        else:
            if file:
                await ctx.send(message, file=file)
            else:
                await ctx.send(message)
    except discord.Forbidden:
        await ctx.send("I tried to DM you but couldn’t~ Here’s your message publicly instead.")
        await ctx.send(message)
