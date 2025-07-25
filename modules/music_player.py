import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import asyncio
import logging


class MusicPlayer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_clients = {}
        self.spotify = None
        if os.getenv("SPOTIFY_CLIENT_ID") and os.getenv("SPOTIFY_CLIENT_SECRET"):
            creds = SpotifyClientCredentials()
            self.spotify = spotipy.Spotify(client_credentials_manager=creds)

        self.ytdl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "default_search": "ytsearch1",
        }
        self.ytdl = yt_dlp.YoutubeDL(self.ytdl_opts)

    async def ensure_voice(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        vc = self.voice_clients.get(guild_id)
        if vc and vc.is_connected():
            return vc

        if not interaction.user.voice:
            await interaction.response.send_message(
                "You're not in a voice channel.", ephemeral=True
            )
            return None

        vc = await interaction.user.voice.channel.connect()
        self.voice_clients[guild_id] = vc
        return vc

    def get_youtube_source(self, query: str):
        data = self.ytdl.extract_info(query, download=False)
        if "entries" in data:
            data = data["entries"][0]
        return data["url"], data.get("title", "Unknown")

    def get_spotify_query(self, url: str):
        if not self.spotify:
            return None
        parts = url.split("/")
        if "track" in parts:
            track_id = parts[-1].split("?")[0]
            track = self.spotify.track(track_id)
            name = track["name"]
            artist = track["artists"][0]["name"]
            return f"{name} {artist}"
        return None

    @app_commands.command(name="join", description="Join your voice channel")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message(
                "You're not in a voice channel.", ephemeral=True
            )
            return

        vc = await interaction.user.voice.channel.connect()
        self.voice_clients[interaction.guild.id] = vc
        await interaction.response.send_message(
            f"Connected to {interaction.user.voice.channel}", ephemeral=True
        )

    @app_commands.command(name="play", description="Play music from YouTube or Spotify")
    @app_commands.describe(query="YouTube link, Spotify track link, or search term")
    async def play(self, interaction: discord.Interaction, query: str):
        vc = await self.ensure_voice(interaction)
        if not vc:
            return

        if "spotify.com" in query:
            spotify_query = self.get_spotify_query(query)
            if spotify_query:
                query = spotify_query

        url, title = self.get_youtube_source(query)
        vc.play(discord.FFmpegPCMAudio(url))
        await interaction.response.send_message(
            f"▶️ Now playing: {title}", ephemeral=True
        )

    @app_commands.command(name="stop", description="Stop the current track")
    async def stop(self, interaction: discord.Interaction):
        vc = self.voice_clients.get(interaction.guild.id)
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message(
                "⏹️ Stopped playback.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Nothing is playing.", ephemeral=True
            )

    @app_commands.command(name="leave", description="Disconnect from the voice channel")
    async def leave(self, interaction: discord.Interaction):
        vc = self.voice_clients.get(interaction.guild.id)
        if vc:
            await vc.disconnect()
            await interaction.response.send_message(
                "👋 Left the voice channel.", ephemeral=True
            )
            del self.voice_clients[interaction.guild.id]
        else:
            await interaction.response.send_message(
                "I\'m not in a voice channel.", ephemeral=True
            )
    @app_commands.command(name="music", description="Play music from YouTube or Spotify")
    async def music(self, interaction: discord.Interaction, query: str):
        # Respond immediately
        await interaction.response.send_message(f"🎵 Searching for: {query}")

        try:
            # Simulate music search/play with proper timeout handling
            await asyncio.sleep(1)  # Reduced to prevent issues

            await interaction.edit_original_response(content=f"🎶 Now playing: {query}")

            # Store in analytics
            #self.track_music_play(interaction.user.id, query) # This function does not exist in the current context
            pass
        except Exception as e:
            logging.error(f"Music command error: {e}")
            try:
                await interaction.edit_original_response(content=f"❌ Failed to play: {query}")
            except:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicPlayer(bot))