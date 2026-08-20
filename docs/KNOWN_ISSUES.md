# Known Issues

## Voice playback: no audio due to Discord's mandatory E2EE (DAVE)

**Status:** Unresolved, blocked on upstream libraries. Last investigated 2026-08-19.

### Symptom

`/join` and `/play` succeed - the bot connects to the voice channel, the
`▶️ Now playing` message appears, no exceptions are logged - but no audio is
actually heard by anyone in the channel. This affects **all** audio sources
(YouTube links, search terms, and Spotify links, since Spotify tracks are
resolved to a YouTube search and then go through the exact same playback
pipeline in `modules/music_player.py::_play_next`).

### Root cause

Discord made end-to-end encryption (the DAVE protocol) **mandatory for every
regular voice channel** starting March 2, 2026, with no server-side opt-out.
(Stage channels are the only exemption, and aren't a fit for a normal music
bot - only "speakers" can transmit audio there.)

- Before this project's discord.py upgrade (2.3.2 -> 2.7.1, see git log), the
  bot couldn't even connect to voice: every attempt failed with a repeated
  `discord.errors.ConnectionClosed: ... WebSocket closed with 4006` loop,
  because an old client that doesn't support DAVE gets rejected by Discord's
  voice servers outright.
- discord.py only merged DAVE support on **2026-01-07**
  ([PR #10300](https://github.com/Rapptz/discord.py/pull/10300)), via a new
  required dependency called `davey` (added to `requirements.txt`). Without
  `davey` installed, discord.py 2.7.1 raises
  `RuntimeError: davey library needed in order to use voice` at connect time.
- With `davey` installed, the connection itself now works cleanly (confirmed:
  no more 4006 errors, `/join`/`/play` succeed). But discord.py's own docs
  describe DAVE support as "still tentative," and `davey` itself is described
  by its maintainers as "yet to be reviewed by others." In practice, the
  MLS-based end-to-end key exchange either never fully completes, or
  completes incorrectly - so encrypted audio packets are sent but are
  silently undecodable (or dropped) on the receiving end. No exception
  surfaces on our side, because from discord.py's perspective playback
  genuinely started.
- This is not specific to this project or to discord.py: discord.js (the
  Node.js equivalent library) has open issues describing the identical
  symptom class right now (bots connecting fine but sending audio that's
  silently undecodable due to DAVE key-exchange bugs). This is a rough,
  actively-evolving patch for the whole self-hosted Discord bot ecosystem,
  roughly 5-6 months into a mandatory-encryption rollout that voice libraries
  are still catching up to.

### Why we can't patch around it

Our bot is the *encryptor* in this exchange (`VoiceClient._get_voice_packet`
calls `dave_session.encrypt_opus(data)` before sending). The key material
comes from a live MLS handshake between `davey` and Discord's servers -
there's no local workaround our application code could apply; a broken
handshake can only be fixed by fixing the handshake itself, upstream in
`davey`/discord.py. `davey` also ships as a compiled native extension
(`davey-0.1.6-cp311-cp311-win_amd64.whl` on Windows), not something we can
patch inline even if we wanted to reimplement its crypto (which we don't -
rolling your own fix for someone else's E2EE protocol is exactly the kind of
thing that goes wrong silently).

### What's in place to diagnose it further

`modules/music_player.py::_play_next` logs once playback starts:
- `discord.VoiceClient.voice_privacy_code` is a public property that's only
  set once the DAVE session is genuinely established.
- If it's **missing** when playback starts, we log a `WARNING` (persisted to
  `logs/bot.log`) - this is the concrete signature of "the E2EE handshake
  never finished," as opposed to "it finished but encrypted wrong" (which
  would show a privacy code but still produce no audio).

Check `logs/bot.log` for `"no E2EE voice_privacy_code is set"` after a
`/play` attempt to tell which failure mode is happening.

### Next steps (when picking this back up)

1. Check `logs/bot.log` for whether `voice_privacy_code` was ever set during
   a failed playback attempt - narrows down which of the two failure modes
   above is occurring.
2. Check for newer `discord.py` / `davey` releases
   (`pip index versions discord.py` / `pip index versions davey`) - both are
   very new and actively being patched.
3. Search/file an issue on
   [Rapptz/discord.py](https://github.com/Rapptz/discord.py/issues) if the
   `voice_privacy_code`-missing signature reproduces consistently - that's
   concrete enough to be a useful bug report.
4. No config change in this repo can route around this: E2EE enforcement is
   server-side and has no opt-out for regular voice channels.
