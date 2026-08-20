"""
Tests for modules/music_player.py

All tests are async so pytest-asyncio (mode=auto) manages the event loop
throughout the entire suite — no asyncio.get_event_loop() in sync helpers.

Covers:
- Cog loads cleanly (existing test)
- GuildMusicState construction / isolation
- Queue logic: tracks enqueued and popped in FIFO order
- _play_next scheduling logic via mocked VoiceClient
- _ensure_voice: deferred vs. non-deferred error paths
- Spotify URL routing (track / album / playlist / artist / spotify: URI)
- /play command: enqueue + start path and enqueue-behind-playing path
- Queue ordering: Spotify album appended to tail, added_count reflects this request only
"""

import asyncio
import importlib
from collections import deque
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers (no asyncio.get_event_loop() — loop is always the running test loop)
# ---------------------------------------------------------------------------

def _get_module():
    return importlib.import_module("modules.music_player")


def _make_bot():
    """Return a MagicMock bot whose .loop is the *currently running* event loop."""
    bot = MagicMock()
    bot.loop = asyncio.get_event_loop()
    return bot


def _make_cog(spotify=None):
    module = _get_module()
    bot = _make_bot()
    cog = module.MusicPlayer(bot)
    if spotify is not None:
        cog.spotify = spotify
    else:
        cog.spotify = None
    return cog


def _fake_spotify():
    sp = MagicMock()

    sp.track.return_value = {
        "name": "My Song",
        "artists": [{"name": "Artist A"}],
    }
    sp.album_tracks.return_value = {
        "items": [
            {"name": "Album Track 1", "artists": [{"name": "Band"}]},
            {"name": "Album Track 2", "artists": [{"name": "Band"}]},
        ]
    }
    sp.playlist_tracks.return_value = {
        "items": [
            {"track": {"name": "PL Track 1", "artists": [{"name": "Solo"}]}},
            {"track": {"name": "PL Track 2", "artists": [{"name": "Solo"}]}},
            {"track": None},  # should be skipped
        ]
    }
    sp.artist_top_tracks.return_value = {
        "tracks": [
            {"name": "Hit 1", "artists": [{"name": "Star"}]},
            {"name": "Hit 2", "artists": [{"name": "Star"}]},
        ]
    }
    return sp


def _make_interaction(*, in_voice: bool = False, guild_id: int = 1001):
    """Return a fully mocked discord.Interaction."""
    interaction = MagicMock()
    interaction.guild.id = guild_id
    # No real discord.py-side voice client until code actually connects one.
    interaction.guild.voice_client = None
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    if in_voice:
        channel = MagicMock()
        channel.name = "General"
        vc = MagicMock(spec=["is_connected", "is_playing", "is_paused",
                             "play", "stop", "pause", "resume", "disconnect",
                             "guild"])
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        vc.guild = MagicMock()
        vc.guild.id = guild_id
        channel.connect = AsyncMock(return_value=vc)
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = channel
    else:
        interaction.user.voice = None

    return interaction


# ---------------------------------------------------------------------------
# 1. Cog loads cleanly (backwards-compat existing test)
# ---------------------------------------------------------------------------

async def test_music_player_loads():
    module = _get_module()

    class DummyBot:
        pass

    cog = module.MusicPlayer(DummyBot())
    assert isinstance(cog, module.MusicPlayer)


# ---------------------------------------------------------------------------
# 2. GuildMusicState construction
# ---------------------------------------------------------------------------

async def test_guild_state_initial_values():
    module = _get_module()
    state = module.GuildMusicState()
    assert state.voice_client is None
    assert isinstance(state.queue, deque)
    assert len(state.queue) == 0
    assert state.current is None
    assert state.is_playing is False
    assert state.volume == 100


async def test_guild_state_per_guild_isolation():
    cog = _make_cog()
    s1 = cog._state(111)
    s2 = cog._state(222)
    assert s1 is not s2
    s1.is_playing = True
    assert s2.is_playing is False


# ---------------------------------------------------------------------------
# 3. Queue FIFO ordering
# ---------------------------------------------------------------------------

async def test_queue_fifo():
    cog = _make_cog()
    state = cog._state(42)
    tracks = [
        {"title": "Track A", "url": "http://a"},
        {"title": "Track B", "url": "http://b"},
        {"title": "Track C", "url": "http://c"},
    ]
    for t in tracks:
        state.queue.append(t)

    assert state.queue.popleft() == tracks[0]
    assert state.queue.popleft() == tracks[1]
    assert state.queue.popleft() == tracks[2]
    assert len(state.queue) == 0


# ---------------------------------------------------------------------------
# 4. _play_next scheduling
# ---------------------------------------------------------------------------

async def test_play_next_no_queue_clears_state():
    cog = _make_cog()
    guild_id = 99
    state = cog._state(guild_id)

    mock_vc = MagicMock()
    mock_vc.is_connected.return_value = True
    state.voice_client = mock_vc
    state.is_playing = True
    state.current = {"title": "old", "url": "http://old"}

    await cog._play_next(guild_id)

    assert state.is_playing is False
    assert state.current is None
    mock_vc.play.assert_not_called()


async def test_play_next_starts_first_track():
    module = _get_module()
    cog = _make_cog()
    guild_id = 55
    state = cog._state(guild_id)

    mock_vc = MagicMock()
    mock_vc.is_connected.return_value = True
    state.voice_client = mock_vc

    track = {"title": "Song 1", "url": "http://stream/1"}
    state.queue.append(track)

    with patch("modules.music_player.discord.FFmpegPCMAudio") as MockAudio, \
         patch("modules.music_player.discord.PCMVolumeTransformer") as MockVolume:
        mock_source = MagicMock()
        volume_source = MagicMock()
        MockAudio.return_value = mock_source
        MockVolume.return_value = volume_source
        await cog._play_next(guild_id)

    MockAudio.assert_called_once_with(track["url"], **module.FFMPEG_OPTS)
    MockVolume.assert_called_once_with(mock_source, volume=1.0)
    mock_vc.play.assert_called_once_with(volume_source, after=ANY)
    assert state.current == track


async def test_play_next_warns_when_e2ee_session_not_established():
    """Discord now requires E2EE (DAVE) on regular voice channels. If
    voice_privacy_code isn't set after play() starts, the DAVE session likely
    never finished, so audio may be silently dropped even though nothing
    raised - this must be logged so it's diagnosable."""
    module = _get_module()
    cog = _make_cog()
    guild_id = 56
    state = cog._state(guild_id)

    mock_vc = MagicMock()
    mock_vc.is_connected.return_value = True
    mock_vc.voice_privacy_code = None
    state.voice_client = mock_vc
    state.queue.append({"title": "Song", "url": "http://stream/1"})

    with patch("modules.music_player.discord.FFmpegPCMAudio"), \
         patch("modules.music_player.discord.PCMVolumeTransformer"), \
         patch.object(module.logger, "warning") as mock_warning:
        await cog._play_next(guild_id)

    assert any(
        "voice_privacy_code" in str(call) for call in mock_warning.call_args_list
    )


async def test_play_next_logs_info_when_e2ee_session_established():
    module = _get_module()
    cog = _make_cog()
    guild_id = 57
    state = cog._state(guild_id)

    mock_vc = MagicMock()
    mock_vc.is_connected.return_value = True
    mock_vc.voice_privacy_code = "abcd-1234"
    state.voice_client = mock_vc
    state.queue.append({"title": "Song", "url": "http://stream/1"})

    with patch("modules.music_player.discord.FFmpegPCMAudio"), \
         patch("modules.music_player.discord.PCMVolumeTransformer"), \
         patch.object(module.logger, "warning") as mock_warning, \
         patch.object(module.logger, "info") as mock_info:
        await cog._play_next(guild_id)

    mock_warning.assert_not_called()
    assert any("abcd-1234" in str(call) for call in mock_info.call_args_list)
    assert state.is_playing is True
    assert len(state.queue) == 0


async def test_play_next_disconnected_vc_clears_state():
    cog = _make_cog()
    guild_id = 77
    state = cog._state(guild_id)

    mock_vc = MagicMock()
    mock_vc.is_connected.return_value = False
    state.voice_client = mock_vc
    state.queue.append({"title": "T", "url": "http://t"})
    state.is_playing = True

    await cog._play_next(guild_id)

    assert state.is_playing is False
    assert state.current is None


async def test_after_playing_logs_unhandled_error_instead_of_swallowing_it():
    """run_coroutine_threadsafe's Future silently drops exceptions unless
    something retrieves them. after_playing must attach a callback that logs
    a failure in _handle_playback_finished rather than losing it."""
    module = _get_module()
    cog = _make_cog()
    guild_id = 950
    state = cog._state(guild_id)

    vc = MagicMock()
    vc.is_connected.return_value = True
    state.voice_client = vc
    state.queue.append({"title": "Song", "url": "http://stream"})

    with patch("modules.music_player.discord.FFmpegPCMAudio"), \
         patch("modules.music_player.discord.PCMVolumeTransformer"):
        await cog._play_next(guild_id)

    after_playing = vc.play.call_args.kwargs["after"]

    with patch.object(
        cog, "_handle_playback_finished", new=AsyncMock(side_effect=RuntimeError("boom"))
    ), patch.object(module.logger, "error") as mock_error:
        after_playing(None)
        # Give the scheduled coroutine, and its done-callback, a chance to run.
        await asyncio.sleep(0.05)

    assert any("boom" in str(call) for call in mock_error.call_args_list)


# ---------------------------------------------------------------------------
# 5. _ensure_voice: deferred vs. non-deferred error paths
# ---------------------------------------------------------------------------

async def test_not_in_voice_undeferred_uses_send_message():
    cog = _make_cog()
    interaction = _make_interaction(in_voice=False)

    state = await cog._ensure_voice(interaction, deferred=False)

    assert state is None
    interaction.response.send_message.assert_awaited_once()
    interaction.followup.send.assert_not_awaited()


async def test_not_in_voice_deferred_uses_followup():
    cog = _make_cog()
    interaction = _make_interaction(in_voice=False)

    state = await cog._ensure_voice(interaction, deferred=True)

    assert state is None
    interaction.followup.send.assert_awaited_once()
    interaction.response.send_message.assert_not_awaited()


async def test_ensure_voice_connects_and_returns_state():
    cog = _make_cog()
    interaction = _make_interaction(in_voice=True, guild_id=500)

    state = await cog._ensure_voice(interaction, deferred=False)

    assert state is not None
    assert state.voice_client is not None


# ---------------------------------------------------------------------------
# 6. Spotify URL routing
# ---------------------------------------------------------------------------

async def test_spotify_track_url():
    cog = _make_cog(spotify=_fake_spotify())
    queries = cog.get_spotify_queries("https://open.spotify.com/track/abc123?si=x")
    assert queries == ["My Song Artist A"]


async def test_spotify_album_url():
    cog = _make_cog(spotify=_fake_spotify())
    queries = cog.get_spotify_queries("https://open.spotify.com/album/xyz?si=y")
    assert queries == ["Album Track 1 Band", "Album Track 2 Band"]


async def test_spotify_playlist_url():
    cog = _make_cog(spotify=_fake_spotify())
    queries = cog.get_spotify_queries("https://open.spotify.com/playlist/ppp?si=z")
    # None-track items are skipped
    assert queries == ["PL Track 1 Solo", "PL Track 2 Solo"]


async def test_spotify_artist_url():
    cog = _make_cog(spotify=_fake_spotify())
    queries = cog.get_spotify_queries("https://open.spotify.com/artist/aaa")
    assert queries == ["Hit 1 Star", "Hit 2 Star"]


async def test_spotify_uri_track():
    cog = _make_cog(spotify=_fake_spotify())
    queries = cog.get_spotify_queries("spotify:track:abc123")
    assert queries == ["My Song Artist A"]


async def test_spotify_disabled_returns_empty():
    cog = _make_cog(spotify=None)
    assert cog.get_spotify_queries("https://open.spotify.com/track/abc") == []


async def test_spotify_unrecognised_url_returns_empty():
    cog = _make_cog(spotify=_fake_spotify())
    assert cog.get_spotify_queries("https://not-spotify.com/track/abc") == []


async def test_get_spotify_query_compat_alias():
    cog = _make_cog(spotify=_fake_spotify())
    result = cog.get_spotify_query("https://open.spotify.com/track/abc123")
    assert result == "My Song Artist A"


async def test_get_spotify_query_compat_alias_none_when_no_spotify():
    cog = _make_cog(spotify=None)
    assert cog.get_spotify_query("https://open.spotify.com/track/abc") is None


# ---------------------------------------------------------------------------
# 7. /play command: enqueue + start, and enqueue-behind-playing
# ---------------------------------------------------------------------------

async def test_play_command_starts_track_when_idle():
    """When nothing is playing, /play extracts the track and starts it."""
    cog = _make_cog()
    guild_id = 200
    interaction = _make_interaction(in_voice=True, guild_id=guild_id)

    fake_track = {"title": "Awesome Song", "url": "http://stream/awesome"}

    with patch.object(cog, "_extract_info", new=AsyncMock(return_value=fake_track)), \
         patch("modules.music_player.discord.FFmpegPCMAudio"), \
         patch("modules.music_player.discord.PCMVolumeTransformer"):
        await cog.play.callback(cog, interaction, "awesome song")

    state = cog._state(guild_id)
    assert state.current == fake_track
    assert state.is_playing is True
    state.voice_client.play.assert_called_once()
    # followup was used because play() defers after voice check
    interaction.followup.send.assert_awaited_once()
    msg = interaction.followup.send.call_args[0][0]
    assert "Awesome Song" in msg


async def test_join_defers_before_connecting_to_voice():
    """/join must ack the interaction before the voice connect, which can
    easily exceed Discord's 3-second response window."""
    cog = _make_cog()
    guild_id = 903
    interaction = _make_interaction(in_voice=True, guild_id=guild_id)
    channel = interaction.user.voice.channel
    vc = channel.connect.return_value

    call_order: list[str] = []
    interaction.response.defer = AsyncMock(
        side_effect=lambda *a, **k: call_order.append("defer")
    )
    channel.connect = AsyncMock(
        side_effect=lambda *a, **k: call_order.append("connect") or vc
    )

    await cog.join.callback(cog, interaction)

    assert call_order == ["defer", "connect"]
    interaction.followup.send.assert_awaited_once()


async def test_play_command_reports_error_when_playback_fails_to_start():
    """If _play_next can't actually start playback (e.g. voice dropped right
    after connecting), /play must report that instead of crashing when it
    assumes state.current is set."""
    cog = _make_cog()
    guild_id = 905
    interaction = _make_interaction(in_voice=True, guild_id=guild_id)
    fake_track = {"title": "Song", "url": "http://stream"}

    with patch.object(cog, "_extract_info", new=AsyncMock(return_value=fake_track)), \
         patch.object(cog, "_play_next", new=AsyncMock()):  # leaves state.current as None
        await cog.play.callback(cog, interaction, "song")

    interaction.followup.send.assert_awaited_once()
    msg = interaction.followup.send.call_args[0][0]
    assert "couldn't start playback" in msg


async def test_play_defers_before_connecting_to_voice():
    """/play must ack the interaction before the voice connect, which can
    easily exceed Discord's 3-second response window — deferring after
    connecting means a slow connect silently drops the interaction."""
    cog = _make_cog()
    guild_id = 902
    interaction = _make_interaction(in_voice=True, guild_id=guild_id)
    channel = interaction.user.voice.channel
    vc = channel.connect.return_value

    call_order: list[str] = []
    interaction.response.defer = AsyncMock(
        side_effect=lambda *a, **k: call_order.append("defer")
    )
    channel.connect = AsyncMock(
        side_effect=lambda *a, **k: call_order.append("connect") or vc
    )

    fake_track = {"title": "Song", "url": "http://stream"}
    with patch.object(cog, "_extract_info", new=AsyncMock(return_value=fake_track)), \
         patch("modules.music_player.discord.FFmpegPCMAudio"), \
         patch("modules.music_player.discord.PCMVolumeTransformer"):
        await cog.play.callback(cog, interaction, "song")

    assert call_order == ["defer", "connect"]


async def test_play_command_queues_behind_current_track():
    """When a track is already playing, /play appends to the queue."""
    module = _get_module()
    cog = _make_cog()
    guild_id = 201
    interaction = _make_interaction(in_voice=True, guild_id=guild_id)

    # Simulate an already-playing state
    state = cog._state(guild_id)
    existing_vc = MagicMock()
    existing_vc.is_connected.return_value = True
    existing_vc.is_playing.return_value = True
    state.voice_client = existing_vc
    state.is_playing = True
    state.current = {"title": "Playing Now", "url": "http://now"}

    new_track = {"title": "Queued Song", "url": "http://stream/queued"}

    with patch.object(cog, "_extract_info", new=AsyncMock(return_value=new_track)):
        await cog.play.callback(cog, interaction, "queued song")

    # Track must be in queue, not immediately playing
    assert list(state.queue) == [new_track]
    interaction.followup.send.assert_awaited_once()
    msg = interaction.followup.send.call_args[0][0]
    assert "Queued Song" in msg


# ---------------------------------------------------------------------------
# 8. Queue ordering: Spotify album appended to tail; added_count this-request only
# ---------------------------------------------------------------------------

async def test_spotify_album_appended_to_tail():
    """All Spotify tracks must go to the tail, never ahead of pre-existing queue items."""
    cog = _make_cog(spotify=_fake_spotify())
    state = cog._state(42)

    existing = {"title": "Existing Track", "url": "http://existing"}
    state.queue.append(existing)

    queries = cog.get_spotify_queries("https://open.spotify.com/album/xyz")
    assert len(queries) == 2

    for q in queries:
        state.queue.append({"title": q, "url": f"http://yt/{q}"})

    items = list(state.queue)
    assert items[0] == existing
    assert items[1]["title"] == queries[0]
    assert items[2]["title"] == queries[1]
    assert len(items) == 3


async def test_added_count_reflects_this_request_only():
    """added_count must count this /play invocation's tracks, not the whole queue."""
    cog = _make_cog(spotify=_fake_spotify())
    state = cog._state(43)

    state.queue.append({"title": "Old 1", "url": "http://o1"})
    state.queue.append({"title": "Old 2", "url": "http://o2"})

    queries = cog.get_spotify_queries("https://open.spotify.com/album/xyz")
    added_count = 0
    for q in queries:
        state.queue.append({"title": q, "url": f"http://yt/{q}"})
        added_count += 1

    # 2 new tracks, not 4 (total queue size)
    assert added_count == len(queries) == 2
    assert len(state.queue) == 4


async def test_spotify_play_reports_skipped_tracks_by_name():
    """A partial Spotify load reports both successful and failed searches."""
    cog = _make_cog(spotify=_fake_spotify())
    interaction = _make_interaction(in_voice=True, guild_id=44)
    extracted = {
        "Album Track 1 Band": {"title": "Album Track 1", "url": "http://track/1"},
    }

    async def extract(query):
        if query not in extracted:
            raise RuntimeError("not available")
        return extracted[query]

    with patch.object(cog, "_extract_info", new=AsyncMock(side_effect=extract)), \
         patch("modules.music_player.discord.FFmpegPCMAudio"), \
         patch("modules.music_player.discord.PCMVolumeTransformer"):
        await cog.play.callback(
            cog, interaction, "https://open.spotify.com/album/xyz"
        )

    message = interaction.followup.send.call_args[0][0]
    assert "Queued **1 of 2** Spotify track(s)." in message
    assert "Skipped **1** track(s)" in message
    assert "Album Track 2 Band" in message


async def test_spotify_play_reports_all_skipped_tracks():
    """An all-failed Spotify load names the tracks instead of hiding the failure."""
    cog = _make_cog(spotify=_fake_spotify())
    interaction = _make_interaction(in_voice=True, guild_id=45)

    with patch.object(
        cog, "_extract_info", new=AsyncMock(side_effect=RuntimeError("not available"))
    ):
        await cog.play.callback(
            cog, interaction, "https://open.spotify.com/album/xyz"
        )

    message = interaction.followup.send.call_args[0][0]
    assert "Could not find any of the Spotify tracks on YouTube." in message
    assert "Skipped **2 of 2** track(s)" in message
    assert "Album Track 1 Band" in message
    assert "Album Track 2 Band" in message


async def test_spotify_play_limits_long_skipped_track_reports():
    """Failure reporting remains valid when many long track names are skipped."""
    cog = _make_cog(spotify=_fake_spotify())
    interaction = _make_interaction(in_voice=True, guild_id=46)
    queries = [f"Track {i} {'Artist Name ' * 20}" for i in range(25)]

    with patch.object(cog, "get_spotify_queries", return_value=queries), \
         patch.object(
             cog,
             "_extract_info",
             new=AsyncMock(side_effect=RuntimeError("not available")),
         ):
        await cog.play.callback(
            cog, interaction, "https://open.spotify.com/playlist/long"
        )

    messages = [call.args[0] for call in interaction.followup.send.await_args_list]
    assert all(len(message) <= 2000 for message in messages)
    assert "Skipped **25 of 25** track(s)" in messages[0]
    assert "Track 0" in messages[0]
    assert "more skipped track(s) not shown." in messages[0]


# ---------------------------------------------------------------------------
# 9. Volume controls
# ---------------------------------------------------------------------------

async def test_play_next_wraps_source_with_current_volume():
    module = _get_module()
    cog = _make_cog()
    guild_id = 56
    state = cog._state(guild_id)
    state.volume = 35

    vc = MagicMock()
    vc.is_connected.return_value = True
    state.voice_client = vc
    state.queue.append({"title": "Quiet Song", "url": "http://stream/quiet"})

    with patch("modules.music_player.discord.FFmpegPCMAudio") as MockAudio, \
         patch("modules.music_player.discord.PCMVolumeTransformer") as MockVolume:
        raw_source = MagicMock()
        volume_source = MagicMock()
        MockAudio.return_value = raw_source
        MockVolume.return_value = volume_source

        await cog._play_next(guild_id)

    MockVolume.assert_called_once_with(raw_source, volume=0.35)
    vc.play.assert_called_once_with(volume_source, after=ANY)


async def test_volume_command_updates_state_and_active_source():
    module = _get_module()
    cog = _make_cog()
    interaction = _make_interaction(guild_id=600)
    state = cog._state(600)

    raw_source = module.discord.AudioSource()
    active_source = module.discord.PCMVolumeTransformer(raw_source, volume=1.0)
    vc = MagicMock()
    vc.source = active_source
    state.voice_client = vc

    await cog.volume.callback(cog, interaction, 35)

    assert state.volume == 35
    assert active_source.volume == 0.35
    interaction.response.send_message.assert_awaited_once_with(
        "🔊 Volume set to **35%**."
    )


async def test_volume_command_rejects_out_of_range_value():
    cog = _make_cog()
    interaction = _make_interaction(guild_id=601)

    await cog.volume.callback(cog, interaction, 101)

    assert cog._state(601).volume == 100
    interaction.response.send_message.assert_awaited_once_with(
        "❌ Volume must be between 0 and 100.", ephemeral=True
    )


async def test_queue_shows_current_volume():
    cog = _make_cog()
    interaction = _make_interaction(guild_id=602)
    state = cog._state(602)
    state.volume = 65

    await cog.queue.callback(cog, interaction)

    message = interaction.response.send_message.call_args.args[0]
    assert "🔊 Volume: **65%**" in message


async def test_leave_resets_volume_to_default():
    cog = _make_cog()
    interaction = _make_interaction(in_voice=True, guild_id=603)
    state = cog._state(603)
    vc = interaction.user.voice.channel.connect.return_value
    vc.disconnect = AsyncMock()
    state.voice_client = vc
    state.volume = 15

    await cog.leave.callback(cog, interaction)

    assert state.volume == 100
    vc.disconnect.assert_awaited_once()


async def test_leave_defers_before_disconnecting_voice():
    """/leave must ack the interaction before vc.disconnect(), which performs
    a real network teardown that can exceed Discord's 3-second response
    window — responding only after disconnect risks the interaction expiring
    with no acknowledgement shown to the user."""
    cog = _make_cog()
    guild_id = 904
    interaction = _make_interaction(in_voice=True, guild_id=guild_id)
    vc = interaction.user.voice.channel.connect.return_value
    state = cog._state(guild_id)
    state.voice_client = vc
    interaction.guild.voice_client = vc

    call_order: list[str] = []
    interaction.response.defer = AsyncMock(
        side_effect=lambda *a, **k: call_order.append("defer")
    )
    vc.disconnect = AsyncMock(
        side_effect=lambda *a, **k: call_order.append("disconnect")
    )

    await cog.leave.callback(cog, interaction)

    assert call_order == ["defer", "disconnect"]
    interaction.followup.send.assert_awaited_once()


# ---------------------------------------------------------------------------
# 10. Voice connection recovery
# ---------------------------------------------------------------------------

async def test_voice_recovery_requeues_interrupted_track_and_resumes():
    cog = _make_cog()
    cog.reconnect_retry_delay = 0
    guild_id = 700
    state = cog._state(guild_id)

    voice_channel = MagicMock()
    old_vc = MagicMock()
    old_vc.is_connected.return_value = False
    old_vc.disconnect = AsyncMock()
    old_vc.channel = voice_channel
    old_vc.cleanup = MagicMock()

    new_vc = MagicMock()
    new_vc.is_connected.return_value = True
    new_vc.channel = voice_channel

    async def connect_after_cleanup(*args, **kwargs):
        assert old_vc.cleanup.called
        return new_vc

    voice_channel.connect = AsyncMock(side_effect=connect_after_cleanup)

    text_channel = MagicMock()
    text_channel.send = AsyncMock()
    state.voice_client = old_vc
    state.voice_channel = voice_channel
    state.text_channel = text_channel
    interrupted = {"title": "Interrupted", "url": "http://interrupted"}
    queued = {"title": "Next", "url": "http://next"}
    state.current = interrupted
    state.queue.append(queued)
    state.is_playing = True

    with patch("modules.music_player.discord.FFmpegPCMAudio"), \
         patch("modules.music_player.discord.PCMVolumeTransformer"):
        recovered = await cog._recover_voice_connection(guild_id, force=True)

    assert recovered is True
    assert state.voice_client is new_vc
    assert state.current == interrupted
    assert list(state.queue) == [queued]
    new_vc.play.assert_called_once()
    old_vc.disconnect.assert_not_awaited()
    old_vc.cleanup.assert_called_once()
    voice_channel.connect.assert_awaited_once_with(reconnect=True)
    text_channel.send.assert_awaited_once()
    assert "Interrupted" in text_channel.send.call_args.args[0]


async def test_voice_recovery_clears_state_and_notifies_after_retries():
    cog = _make_cog()
    cog.reconnect_max_retries = 2
    cog.reconnect_retry_delay = 0
    guild_id = 701
    state = cog._state(guild_id)

    voice_channel = MagicMock()
    voice_channel.connect = AsyncMock(side_effect=RuntimeError("voice unavailable"))
    text_channel = MagicMock()
    text_channel.send = AsyncMock()
    state.voice_channel = voice_channel
    state.text_channel = text_channel
    state.current = {"title": "Lost Song", "url": "http://lost"}
    state.is_playing = True

    recovered = await cog._recover_voice_connection(guild_id, force=True)

    assert recovered is False
    assert guild_id not in cog._states
    assert voice_channel.connect.await_count == 2
    message = text_channel.send.call_args.args[0]
    assert "could not reconnect after 2 attempt(s)" in message
    assert "queue was cleared" in message


async def test_stale_voice_callback_cannot_advance_replacement_queue():
    cog = _make_cog()
    guild_id = 702
    state = cog._state(guild_id)
    old_vc = MagicMock()
    new_vc = MagicMock()
    state.voice_client = new_vc
    state.current = {"title": "Still Playing", "url": "http://current"}
    state.queue.append({"title": "Do Not Skip", "url": "http://queued"})
    state.is_playing = True

    await cog._handle_playback_finished(guild_id, old_vc, RuntimeError("stale"))

    assert state.current["title"] == "Still Playing"
    assert list(state.queue)[0]["title"] == "Do Not Skip"


async def test_gateway_disconnect_waits_for_resume_then_recovers_stale_voice():
    cog = _make_cog()
    cog.reconnect_retry_delay = 0
    guild_id = 703
    state = cog._state(guild_id)

    voice_channel = MagicMock()
    old_vc = MagicMock()
    old_vc.is_connected.return_value = False
    old_vc.disconnect = AsyncMock()
    new_vc = MagicMock()
    new_vc.is_connected.return_value = True
    voice_channel.connect = AsyncMock(return_value=new_vc)

    state.voice_client = old_vc
    state.voice_channel = voice_channel
    state.current = {"title": "Recover Me", "url": "http://recover"}
    state.is_playing = True

    await cog.on_disconnect()
    voice_channel.connect.assert_not_awaited()

    with patch("modules.music_player.discord.FFmpegPCMAudio"), \
         patch("modules.music_player.discord.PCMVolumeTransformer"):
        await cog.on_resumed()

    voice_channel.connect.assert_awaited_once_with(reconnect=True)
    assert state.voice_client is new_vc
    assert state.current["title"] == "Recover Me"


async def test_voice_state_channel_move_returns_bot_to_saved_channel():
    cog = _make_cog()
    cog.reconnect_retry_delay = 0
    cog.bot.user = MagicMock(id=42)
    guild_id = 704
    state = cog._state(guild_id)

    saved_channel = MagicMock()
    other_channel = MagicMock()
    old_vc = MagicMock()
    old_vc.is_connected.return_value = True
    old_vc.move_to = AsyncMock()
    new_vc = MagicMock()
    new_vc.is_connected.return_value = True
    saved_channel.connect = AsyncMock(return_value=new_vc)

    state.voice_client = old_vc
    state.voice_channel = saved_channel
    state.current = {"title": "Moved", "url": "http://moved"}
    state.is_playing = True

    member = SimpleNamespace(id=42, guild=SimpleNamespace(id=guild_id))
    after = SimpleNamespace(channel=other_channel)
    with patch("modules.music_player.discord.FFmpegPCMAudio"), \
         patch("modules.music_player.discord.PCMVolumeTransformer"):
        await cog.on_voice_state_update(member, None, after)

    old_vc.move_to.assert_awaited_once_with(saved_channel)
    saved_channel.connect.assert_not_awaited()
    assert state.voice_client is old_vc
    assert state.current["title"] == "Moved"


async def test_recovery_moves_live_client_without_disconnecting_it():
    """Moving a live client avoids a self-triggered voice-leave event."""
    cog = _make_cog()
    cog.reconnect_retry_delay = 0
    guild_id = 705
    state = cog._state(guild_id)

    saved_channel = MagicMock()
    old_vc = MagicMock()
    old_vc.is_connected.return_value = True
    old_vc.move_to = AsyncMock()
    old_vc.disconnect = AsyncMock()

    state.voice_client = old_vc
    state.voice_channel = saved_channel
    state.current = {"title": "Recover Once", "url": "http://once"}
    state.is_playing = True

    with patch("modules.music_player.discord.FFmpegPCMAudio"), \
         patch("modules.music_player.discord.PCMVolumeTransformer"):
        recovered = await cog._recover_voice_connection(guild_id, force=True)

    assert recovered is True
    old_vc.move_to.assert_awaited_once_with(saved_channel)
    old_vc.disconnect.assert_not_awaited()
    saved_channel.connect.assert_not_called()
    old_vc.play.assert_called_once()
