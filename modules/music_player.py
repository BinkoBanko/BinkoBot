import asyncio
import discord
from collections import deque
from discord.ext import commands
from discord import app_commands
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import logging
import inspect

logger = logging.getLogger(__name__)

YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch1",
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

DEFAULT_VOICE_RECONNECT_RETRIES = 3
DEFAULT_VOICE_RECONNECT_DELAY = 2.0


def _positive_int_setting(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        logger.warning("Invalid %s; using %s", name, default)
        return default


def _non_negative_float_setting(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        logger.warning("Invalid %s; using %s", name, default)
        return default


# These can be tuned without changing code:
# MUSIC_RECONNECT_RETRIES=5 MUSIC_RECONNECT_DELAY=3
VOICE_RECONNECT_MAX_RETRIES = _positive_int_setting(
    "MUSIC_RECONNECT_RETRIES", DEFAULT_VOICE_RECONNECT_RETRIES
)
VOICE_RECONNECT_RETRY_DELAY = _non_negative_float_setting(
    "MUSIC_RECONNECT_DELAY", DEFAULT_VOICE_RECONNECT_DELAY
)


class GuildMusicState:
    """Per-guild state: voice client, queue, now-playing info, and volume."""

    def __init__(self):
        self.voice_client: discord.VoiceClient | None = None
        self.queue: deque[dict] = deque()   # dicts: {"title": str, "url": str}
        self.current: dict | None = None    # currently playing track
        self.is_playing: bool = False
        self.volume: int = 100              # percentage, from 0 (muted) to 100
        self.voice_channel: discord.VoiceChannel | None = None
        self.text_channel: discord.TextChannel | None = None
        self.reconnecting: bool = False
        self.reconnect_generation: int = 0


class MusicPlayer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._states: dict[int, GuildMusicState] = {}
        self._reconnect_locks: dict[int, asyncio.Lock] = {}
        self._gateway_recovery_pending: set[int] = set()
        self.reconnect_max_retries = VOICE_RECONNECT_MAX_RETRIES
        self.reconnect_retry_delay = VOICE_RECONNECT_RETRY_DELAY
        self.spotify = None
        spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
        spotify_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if spotify_client_id and spotify_client_secret:
            try:
                creds = SpotifyClientCredentials(
                    client_id=spotify_client_id,
                    client_secret=spotify_client_secret,
                )
                self.spotify = spotipy.Spotify(client_credentials_manager=creds)
            except Exception as exc:
                logger.warning("Spotify init failed — Spotify support disabled: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self._states:
            self._states[guild_id] = GuildMusicState()
        return self._states[guild_id]

    async def _send_state_message(
        self, state: GuildMusicState, message: str
    ) -> None:
        """Send a best-effort status message to the last music text channel."""
        channel = state.text_channel
        if channel is None:
            logger.warning("Could not notify users about voice recovery: no text channel")
            return

        try:
            await channel.send(message)
        except Exception as exc:
            logger.warning("Could not send voice recovery notice: %s", exc)

    @staticmethod
    def _cancel_voice_recovery(state: GuildMusicState) -> None:
        """Prevent an in-flight retry loop from restoring a stopped session."""
        state.reconnect_generation += 1
        state.reconnecting = False

    def _recovery_was_cancelled(
        self, guild_id: int, state: GuildMusicState, generation: int
    ) -> bool:
        return (
            self._states.get(guild_id) is not state
            or state.reconnect_generation != generation
        )

    async def _cleanup_stale_voice_client(self, guild_id: int, voice_client) -> None:
        """Remove a stale client from discord.py's cache without a voice event."""
        cleanup = getattr(voice_client, "cleanup", None)
        if not callable(cleanup):
            return

        try:
            cleanup_result = cleanup()
            if inspect.isawaitable(cleanup_result):
                await cleanup_result
        except Exception as exc:
            logger.debug(
                "Old voice client cleanup failed in guild %s: %s",
                guild_id,
                exc,
            )

    def _sync_state_voice_client(
        self, guild: discord.Guild, state: GuildMusicState
    ) -> discord.VoiceClient | None:
        """Reconcile our per-guild bookkeeping with discord.py's own
        authoritative voice client for this guild.

        Our own ``state.voice_client`` can desync from discord.py's real
        connection cache (``guild.voice_client``) — most commonly after an
        abrupt process restart while a voice session was active, or a failed
        auto-reconnect that didn't fully clear discord.py's cache. Always
        trust ``guild.voice_client`` as the source of truth and self-heal
        our bookkeeping from it, rather than letting the two disagree.
        """
        real_vc = guild.voice_client
        if real_vc is not None and real_vc.is_connected():
            state.voice_client = real_vc
        elif state.voice_client is not None and not state.voice_client.is_connected():
            state.voice_client = None
        return state.voice_client

    async def _recover_voice_connection(
        self, guild_id: int, *, force: bool = False
    ) -> bool:
        """Reconnect a stale voice client and restart its interrupted track.

        The current track is put back at the front of the queue before trying
        to connect, so every retry (and the eventual successful connection)
        starts the track from its beginning.  A per-guild lock prevents
        duplicate voice-state and gateway-disconnect events from creating
        competing voice clients.
        """
        state = self._states.get(guild_id)
        if not state or not (state.current or state.queue):
            return False

        voice_client = state.voice_client
        connected = bool(voice_client and voice_client.is_connected())
        if connected and not force:
            return True

        lock = self._reconnect_locks.setdefault(guild_id, asyncio.Lock())
        async with lock:
            state = self._states.get(guild_id)
            if not state or not (state.current or state.queue):
                return False

            voice_client = state.voice_client
            connected = bool(voice_client and voice_client.is_connected())
            if connected and state.is_playing and not force:
                return True
            if state.reconnecting:
                return False

            state.reconnecting = True
            generation = state.reconnect_generation
            interrupted_track = state.current if state.is_playing else None
            if interrupted_track is not None:
                state.queue.appendleft(interrupted_track)
                state.current = None
                state.is_playing = False

            channel = state.voice_channel or getattr(voice_client, "channel", None)
            if channel is None:
                logger.warning("Cannot reconnect guild %s: voice channel is unknown", guild_id)
            elif voice_client is not None and connected:
                # The bot was moved but its client remains healthy. Moving the
                # existing client back avoids a disconnect event that would
                # otherwise look like a second external voice loss.
                try:
                    if interrupted_track is not None:
                        voice_client.stop()
                    await voice_client.move_to(channel)
                    if self._recovery_was_cancelled(guild_id, state, generation):
                        return False

                    state.voice_client = voice_client
                    state.voice_channel = channel
                    state.reconnecting = False
                    await self._play_next(guild_id)
                    if interrupted_track is not None:
                        await self._send_state_message(
                            state,
                            "🔄 Voice connection restored. Resuming "
                            f"**{interrupted_track['title']}** from the beginning.",
                        )
                    return True
                except Exception as exc:
                    logger.warning(
                        "Could not move voice client back in guild %s: %s",
                        guild_id,
                        exc,
                    )

                    # Remove the unusable client from discord.py's cache
                    # without sending another voice-state update, then fall
                    # back to a fresh connection below.
                    await self._cleanup_stale_voice_client(guild_id, voice_client)

            elif voice_client is not None:
                # VoiceChannel.connect checks discord.py's per-guild voice
                # client cache, which can still retain a disconnected client.
                # Clear that cache before attempting the replacement client.
                await self._cleanup_stale_voice_client(guild_id, voice_client)

            state.voice_client = None
            if channel is not None:
                for attempt in range(1, self.reconnect_max_retries + 1):
                    if self._recovery_was_cancelled(guild_id, state, generation):
                        return False
                    try:
                        new_voice_client = await channel.connect(reconnect=True)
                        if self._recovery_was_cancelled(guild_id, state, generation):
                            try:
                                await new_voice_client.disconnect(force=True)
                            except Exception:
                                pass
                            return False
                        state.voice_client = new_voice_client
                        state.voice_channel = getattr(
                            new_voice_client, "channel", None
                        ) or channel
                        state.reconnecting = False
                        await self._play_next(guild_id)

                        if interrupted_track is not None:
                            await self._send_state_message(
                                state,
                                "🔄 Voice connection restored. Resuming "
                                f"**{interrupted_track['title']}** from the beginning.",
                            )
                        return True
                    except Exception as exc:
                        logger.warning(
                            "Voice reconnect attempt %s/%s failed for guild %s: %s",
                            attempt,
                            self.reconnect_max_retries,
                            guild_id,
                            exc,
                        )
                        if attempt < self.reconnect_max_retries:
                            await asyncio.sleep(self.reconnect_retry_delay)

            if self._recovery_was_cancelled(guild_id, state, generation):
                return False

            retries = self.reconnect_max_retries
            await self._send_state_message(
                state,
                "⚠️ I lost my Discord voice connection and could not reconnect "
                f"after {retries} attempt(s). The music queue was cleared; "
                "please use `/play` to start again.",
            )
            # A failed connect(reconnect=True) attempt can leave a
            # half-registered client in discord.py's own cache; clear it so
            # it doesn't block a future /join.
            leftover_guild = self.bot.get_guild(guild_id)
            if leftover_guild is not None and leftover_guild.voice_client is not None:
                await self._cleanup_stale_voice_client(guild_id, leftover_guild.voice_client)
            state.voice_client = None
            state.voice_channel = None
            state.queue.clear()
            state.current = None
            state.is_playing = False
            state.reconnecting = False
            self._states.pop(guild_id, None)
            return False

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Recover when Discord reports that the bot left its voice channel."""
        bot_user = self.bot.user
        if bot_user is None or getattr(member, "id", None) != bot_user.id:
            return

        guild = getattr(member, "guild", None)
        if guild is None:
            return
        state = self._states.get(guild.id)
        if not state or not (state.current or state.queue):
            return

        voice_client = state.voice_client
        expected_channel = state.voice_channel or getattr(voice_client, "channel", None)
        stale_client = voice_client is None or not voice_client.is_connected()
        changed_channel = (
            after.channel is None
            or (
                expected_channel is not None
                and after.channel != expected_channel
            )
        )
        if stale_client or changed_channel:
            await self._recover_voice_connection(guild.id, force=True)

    @commands.Cog.listener()
    async def on_disconnect(self):
        """Remember active sessions until Discord's gateway is usable again."""
        self._gateway_recovery_pending.update(
            guild_id
            for guild_id, state in self._states.items()
            if state.current or state.queue
        )

    async def _recover_stale_gateway_voice_clients(self) -> None:
        """Recover only voice clients still stale after a gateway reconnect."""
        guild_ids = tuple(self._gateway_recovery_pending)
        self._gateway_recovery_pending.clear()
        if guild_ids:
            await asyncio.gather(
                *(
                    self._recover_voice_connection(guild_id)
                    for guild_id in guild_ids
                )
            )

    @commands.Cog.listener()
    async def on_resumed(self):
        """Check pending voice sessions once Discord resumes its gateway."""
        await self._recover_stale_gateway_voice_clients()

    @commands.Cog.listener()
    async def on_ready(self):
        """Also handle gateway reconnects that establish a fresh READY session."""
        await self._recover_stale_gateway_voice_clients()

    @staticmethod
    def _format_skipped_tracks(
        skipped_queries: list[str],
        *,
        max_characters: int = 1200,
        max_track_characters: int = 300,
    ) -> str:
        """Return a Discord-safe list of failed Spotify search queries.

        A Spotify album or playlist may have enough long track names to exceed
        Discord's 2,000-character message limit. Show as many names as fit and
        state how many could not be displayed.
        """
        lines: list[str] = []
        for index, query in enumerate(skipped_queries):
            track_name = query
            if len(track_name) > max_track_characters:
                track_name = f"{track_name[:max_track_characters - 1]}…"
            track_line = f"• {track_name}"

            omitted_count = len(skipped_queries) - index - 1
            omission_line = (
                f"• … and {omitted_count} more skipped track(s) not shown."
                if omitted_count
                else ""
            )
            separator = "\n" if lines else ""
            projected_length = (
                len("\n".join(lines))
                + len(separator)
                + len(track_line)
                + (len("\n") + len(omission_line) if omission_line else 0)
            )
            if projected_length > max_characters:
                remaining_count = len(skipped_queries) - index
                lines.append(
                    f"• … and {remaining_count} more skipped track(s) not shown."
                )
                break

            lines.append(track_line)

        return "\n".join(lines)

    async def _extract_info(self, query: str) -> dict:
        """Run yt-dlp extraction in a thread so it never blocks the event loop."""
        loop = asyncio.get_event_loop()

        def _sync_extract():
            with yt_dlp.YoutubeDL(YTDL_OPTS) as ytdl:
                data = ytdl.extract_info(query, download=False)
            if data is None:
                raise RuntimeError(f"yt-dlp returned no data for: {query!r}")
            if "entries" in data:
                entries = [e for e in data["entries"] if e]
                if not entries:
                    raise RuntimeError(f"No results found for: {query!r}")
                data = entries[0]
            return data

        try:
            data = await loop.run_in_executor(None, _sync_extract)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch audio for {query!r}: {exc}") from exc

        stream_url = data.get("url")
        if not stream_url:
            raise RuntimeError(f"yt-dlp found metadata but no stream URL for: {query!r}")

        return {"url": stream_url, "title": data.get("title", "Unknown")}

    async def _play_next(self, guild_id: int) -> None:
        """Pop the next track from the queue and start playing it."""
        state = self._state(guild_id)
        if state.reconnecting:
            return
        vc = state.voice_client

        if not vc or not vc.is_connected():
            if state.current and state.is_playing:
                state.queue.appendleft(state.current)
            state.is_playing = False
            state.current = None
            return

        if not state.queue:
            state.is_playing = False
            state.current = None
            return

        track = state.queue.popleft()
        state.current = track
        state.is_playing = True

        def after_playing(error):
            if error:
                logger.error("Playback error in guild %s: %s", guild_id, error)
            # Schedule next track on the bot's event loop. Unlike an
            # asyncio.Task, a run_coroutine_threadsafe Future silently drops
            # any exception unless something retrieves it — log it instead.
            coro = self._handle_playback_finished(guild_id, vc, error)
            future = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            future.add_done_callback(self._log_future_exception)

        try:
            source = discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTS)
            # PCMVolumeTransformer expects a normalized float where 1.0 is
            # 100%. Keep the user-facing value as a percentage in state.
            source = discord.PCMVolumeTransformer(
                source, volume=state.volume / 100
            )
            vc.play(source, after=after_playing)
        except Exception as exc:
            logger.error("Failed to start playback for guild %s: %s", guild_id, exc)
            state.is_playing = False
            state.current = None
            # Try the next track
            await self._play_next(guild_id)

    @staticmethod
    def _log_future_exception(future) -> None:
        """Surface exceptions from a run_coroutine_threadsafe Future.

        Nothing else ever calls .result()/.exception() on this future, so
        without this callback a failure here would vanish with no log line.
        """
        if future.cancelled():
            return
        exc = future.exception()
        if exc:
            logger.error(
                "Unhandled error advancing playback queue: %s", exc, exc_info=exc
            )

    async def _handle_playback_finished(
        self, guild_id: int, source_voice_client, error
    ) -> None:
        """Advance only for the client that actually finished playback.

        A stale client's callback may run after a reconnect. Advancing the
        queue from that callback would skip a track on the replacement client.
        """
        state = self._states.get(guild_id)
        if (
            not state
            or state.voice_client is not source_voice_client
            or state.reconnecting
        ):
            return
        if error:
            logger.error("Playback error in guild %s: %s", guild_id, error)
        await self._play_next(guild_id)

    async def _ensure_voice(
        self,
        interaction: discord.Interaction,
        *,
        deferred: bool = False,
    ) -> GuildMusicState | None:
        """Join the invoker's voice channel if not already there.

        When *deferred* is True the interaction has already been deferred, so
        errors are sent via followup.send instead of response.send_message.

        Returns the GuildMusicState on success, or sends an error and returns None.
        """
        guild_id = interaction.guild.id
        state = self._state(guild_id)

        vc = self._sync_state_voice_client(interaction.guild, state)
        if vc and vc.is_connected():
            state.text_channel = getattr(interaction, "channel", None)
            state.voice_channel = getattr(vc, "channel", None) or (
                interaction.user.voice.channel
                if interaction.user.voice
                else state.voice_channel
            )
            return state

        async def _send_error(msg: str) -> None:
            if deferred:
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)

        if state.reconnecting:
            await _send_error(
                "🔄 I'm reconnecting to the voice channel. Please try again in a moment."
            )
            return None

        if not interaction.user.voice:
            await _send_error("❌ You need to be in a voice channel first.")
            return None

        # Clear any stale discord.py-side client left over from a previous
        # session (e.g. an abrupt restart) so it doesn't block a fresh connect.
        stale_vc = interaction.guild.voice_client
        if stale_vc is not None and not stale_vc.is_connected():
            await self._cleanup_stale_voice_client(guild_id, stale_vc)

        try:
            vc = await interaction.user.voice.channel.connect()
            state.voice_client = vc
            state.voice_channel = getattr(vc, "channel", None) or (
                interaction.user.voice.channel
            )
            state.text_channel = getattr(interaction, "channel", None)
        except Exception as exc:
            await _send_error(f"❌ Could not join your voice channel: {exc}")
            return None

        return state

    # ------------------------------------------------------------------
    # Spotify URL routing
    # ------------------------------------------------------------------

    def _parse_spotify_uri(self, url: str):
        """
        Return (entity_type, entity_id) for any Spotify track/album/playlist/artist
        URL or spotify: URI, or (None, None) if not recognised.
        """
        # spotify:<type>:<id>
        if url.startswith("spotify:"):
            parts = url.split(":")
            if len(parts) >= 3:
                return parts[1], parts[2]
            return None, None

        # https://open.spotify.com/<type>/<id>?...
        # Use a strict check so we only match actual Spotify domains
        import re
        if re.search(r"(^|\.)spotify\.com", url):
            path_part = url.split("spotify.com")[-1]
            segments = [s for s in path_part.split("/") if s]
            for entity_type in ("track", "album", "playlist", "artist"):
                if entity_type in segments:
                    idx = segments.index(entity_type)
                    if idx + 1 < len(segments):
                        entity_id = segments[idx + 1].split("?")[0]
                        return entity_type, entity_id

        return None, None

    def get_spotify_queries(self, url: str) -> list[str]:
        """
        Return a list of search query strings derived from a Spotify URL/URI.
        Returns an empty list when Spotify is unconfigured or the URL is unrecognised.
        For multi-track types (album / playlist) returns up to 25 queries.
        """
        if not self.spotify:
            return []

        entity_type, entity_id = self._parse_spotify_uri(url)
        if not entity_type:
            return []

        try:
            if entity_type == "track":
                track = self.spotify.track(entity_id)
                name = track["name"]
                artist = track["artists"][0]["name"]
                return [f"{name} {artist}"]

            elif entity_type == "album":
                results = self.spotify.album_tracks(entity_id, limit=25)
                queries = []
                for item in results["items"][:25]:
                    artist = item["artists"][0]["name"]
                    queries.append(f"{item['name']} {artist}")
                return queries

            elif entity_type == "playlist":
                results = self.spotify.playlist_tracks(entity_id, limit=25)
                queries = []
                for item in results["items"][:25]:
                    track = item.get("track")
                    if not track:
                        continue
                    artist = track["artists"][0]["name"]
                    queries.append(f"{track['name']} {artist}")
                return queries

            elif entity_type == "artist":
                results = self.spotify.artist_top_tracks(entity_id)
                queries = []
                for track in results["tracks"][:25]:
                    queries.append(f"{track['name']} {track['artists'][0]['name']}")
                return queries

        except Exception as exc:
            logger.warning("Spotify lookup failed for %s: %s", url, exc)

        return []

    # Backwards-compat alias used by tests
    def get_spotify_query(self, url: str) -> str | None:
        queries = self.get_spotify_queries(url)
        return queries[0] if queries else None

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------

    @app_commands.command(name="join", description="Join your voice channel")
    async def join(self, interaction: discord.Interaction):
        try:
            state = await self._ensure_voice(interaction)
            if not state:
                return
            channel = interaction.user.voice.channel
            await interaction.response.send_message(
                f"✅ Connected to **{channel.name}**.", ephemeral=True
            )
        except Exception as exc:
            logger.exception("Error in /join")
            msg = f"❌ Error: {exc}"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="play", description="Play music from YouTube or Spotify")
    @app_commands.describe(query="YouTube link, Spotify link, or search term")
    async def play(self, interaction: discord.Interaction, query: str):
        # Ack immediately: the voice connect below, and the extraction that
        # follows, can both easily exceed Discord's 3-second response window.
        await interaction.response.defer()
        state = await self._ensure_voice(interaction, deferred=True)
        if not state:
            return

        try:
            # Resolve Spotify → YouTube search queries
            if "spotify.com" in query or query.startswith("spotify:"):
                spotify_queries = self.get_spotify_queries(query)
                if not spotify_queries:
                    await interaction.followup.send(
                        "❌ Could not resolve that Spotify link. "
                        "Make sure Spotify credentials are configured and the link is valid.",
                        ephemeral=True,
                    )
                    return

                # Resolve all queries and append them to the tail of the queue in order
                added_count = 0
                skipped_queries: list[str] = []
                first_title: str | None = None
                for sq in spotify_queries:
                    try:
                        t = await self._extract_info(sq)
                        state.queue.append(t)
                        if first_title is None:
                            first_title = t["title"]
                        added_count += 1
                    except Exception as exc:
                        logger.warning("Could not load Spotify track %r: %s", sq, exc)
                        skipped_queries.append(sq)

                if added_count == 0:
                    skipped_list = self._format_skipped_tracks(skipped_queries)
                    await interaction.followup.send(
                        "❌ Could not find any of the Spotify tracks on YouTube."
                        f"\n⚠️ Skipped **{len(skipped_queries)} of {len(spotify_queries)}** "
                        f"track(s):\n{skipped_list}",
                        ephemeral=True,
                    )
                    return

                queue_summary = (
                    f"✅ Queued **{added_count} of {len(spotify_queries)}** Spotify track(s)."
                )
                if skipped_queries:
                    skipped_list = self._format_skipped_tracks(skipped_queries)
                    queue_summary += (
                        f"\n⚠️ Skipped **{len(skipped_queries)}** track(s):\n{skipped_list}"
                    )

                if not state.is_playing:
                    guild_id = interaction.guild.id
                    await self._play_next(guild_id)
                    current = state.current
                    await interaction.followup.send(
                        f"{queue_summary}\n▶️ Now playing: **{current['title']}**"
                        + (f"\n📋 {added_count - 1} more track(s) queued." if added_count > 1 else "")
                    )
                else:
                    await interaction.followup.send(
                        f"{queue_summary}\n📋 Added **{added_count}** track(s) to the queue."
                    )
                return

            # Single YouTube link or search term
            track = await self._extract_info(query)

            guild_id = interaction.guild.id
            if state.is_playing:
                state.queue.append(track)
                await interaction.followup.send(
                    f"📋 Added to queue (position {len(state.queue)}): **{track['title']}**"
                )
            else:
                state.queue.append(track)
                await self._play_next(guild_id)
                current = state.current
                await interaction.followup.send(
                    f"▶️ Now playing: **{current['title']}**"
                )

        except RuntimeError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
        except Exception as exc:
            logger.exception("Error in /play")
            await interaction.followup.send(f"❌ Unexpected error: {exc}", ephemeral=True)

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue(self, interaction: discord.Interaction):
        try:
            guild_id = interaction.guild.id
            state = self._state(guild_id)

            lines: list[str] = []
            if state.current and state.is_playing:
                lines.append(f"▶️ **Now playing:** {state.current['title']}")
            else:
                lines.append("⏸️ Nothing is currently playing.")

            if state.queue:
                lines.append("")
                lines.append("**Up next:**")
                for i, track in enumerate(state.queue, 1):
                    lines.append(f"  {i}. {track['title']}")
            else:
                lines.append("📋 Queue is empty.")

            lines.append(f"🔊 Volume: **{state.volume}%**")
            await interaction.response.send_message("\n".join(lines))
        except Exception as exc:
            logger.exception("Error in /queue")
            await interaction.response.send_message(f"❌ Error: {exc}", ephemeral=True)

    @app_commands.command(name="volume", description="Set playback volume")
    @app_commands.describe(level="Playback volume percentage (0–100)")
    async def volume(
        self,
        interaction: discord.Interaction,
        level: app_commands.Range[int, 0, 100],
    ):
        try:
            # Range validation is enforced when Discord invokes the command,
            # but retain a guard for direct calls and future callers.
            if not 0 <= level <= 100:
                await interaction.response.send_message(
                    "❌ Volume must be between 0 and 100.", ephemeral=True
                )
                return

            guild_id = interaction.guild.id
            state = self._state(guild_id)
            state.volume = level

            vc = state.voice_client
            active_source = getattr(vc, "source", None) if vc else None
            if isinstance(active_source, discord.PCMVolumeTransformer):
                active_source.volume = level / 100

            await interaction.response.send_message(
                f"🔊 Volume set to **{level}%**."
            )
        except Exception as exc:
            logger.exception("Error in /volume")
            await interaction.response.send_message(f"❌ Error: {exc}", ephemeral=True)

    @app_commands.command(name="skip", description="Skip the current track")
    async def skip(self, interaction: discord.Interaction):
        try:
            guild_id = interaction.guild.id
            state = self._state(guild_id)
            vc = state.voice_client

            if not vc or not vc.is_connected() or not state.is_playing:
                await interaction.response.send_message(
                    "❌ Nothing is playing.", ephemeral=True
                )
                return

            vc.stop()   # triggers after= callback → _play_next
            await interaction.response.send_message("⏭️ Skipped.")
        except Exception as exc:
            logger.exception("Error in /skip")
            await interaction.response.send_message(f"❌ Error: {exc}", ephemeral=True)

    @app_commands.command(name="pause", description="Pause playback")
    async def pause(self, interaction: discord.Interaction):
        try:
            guild_id = interaction.guild.id
            state = self._state(guild_id)
            vc = state.voice_client

            if not vc or not vc.is_playing():
                await interaction.response.send_message(
                    "❌ Nothing is playing.", ephemeral=True
                )
                return

            vc.pause()
            await interaction.response.send_message("⏸️ Paused.")
        except Exception as exc:
            logger.exception("Error in /pause")
            await interaction.response.send_message(f"❌ Error: {exc}", ephemeral=True)

    @app_commands.command(name="resume", description="Resume paused playback")
    async def resume(self, interaction: discord.Interaction):
        try:
            guild_id = interaction.guild.id
            state = self._state(guild_id)
            vc = state.voice_client

            if not vc or not vc.is_paused():
                await interaction.response.send_message(
                    "❌ Nothing is paused.", ephemeral=True
                )
                return

            vc.resume()
            await interaction.response.send_message("▶️ Resumed.")
        except Exception as exc:
            logger.exception("Error in /resume")
            await interaction.response.send_message(f"❌ Error: {exc}", ephemeral=True)

    @app_commands.command(name="stop", description="Stop playback and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        try:
            guild_id = interaction.guild.id
            state = self._state(guild_id)
            vc = state.voice_client

            self._cancel_voice_recovery(state)
            state.queue.clear()
            state.current = None
            state.is_playing = False

            if vc and (vc.is_playing() or vc.is_paused()):
                vc.stop()
                await interaction.response.send_message("⏹️ Stopped and queue cleared.")
            else:
                await interaction.response.send_message(
                    "❌ Nothing is playing.", ephemeral=True
                )
        except Exception as exc:
            logger.exception("Error in /stop")
            await interaction.response.send_message(f"❌ Error: {exc}", ephemeral=True)

    @app_commands.command(name="leave", description="Disconnect from the voice channel")
    async def leave(self, interaction: discord.Interaction):
        # Ack immediately: vc.disconnect() below performs a real network
        # teardown that can exceed Discord's 3-second response window.
        await interaction.response.defer()
        try:
            guild_id = interaction.guild.id
            state = self._state(guild_id)
            vc = self._sync_state_voice_client(interaction.guild, state)

            if state.reconnecting:
                self._cancel_voice_recovery(state)
                state.queue.clear()
                state.current = None
                state.is_playing = False
                state.voice_channel = None
                await interaction.followup.send("👋 Left the voice channel.")
                return

            if not vc or not vc.is_connected():
                # Clean up any stale discord.py-side client left over from a
                # previous session, so it doesn't silently block a future /join.
                stale_vc = interaction.guild.voice_client
                if stale_vc is not None:
                    await self._cleanup_stale_voice_client(guild_id, stale_vc)
                await interaction.followup.send(
                    "❌ I'm not in a voice channel.", ephemeral=True
                )
                return

            state.queue.clear()
            state.current = None
            state.is_playing = False
            self._cancel_voice_recovery(state)
            await vc.disconnect()
            state.voice_client = None
            state.voice_channel = None
            state.volume = 100

            await interaction.followup.send("👋 Left the voice channel.")
        except Exception as exc:
            logger.exception("Error in /leave")
            await interaction.followup.send(f"❌ Error: {exc}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicPlayer(bot))
