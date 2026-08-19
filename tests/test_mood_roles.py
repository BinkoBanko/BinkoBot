"""
tests/test_mood_roles.py

Unit tests for the Mood cog's role-lifecycle behaviour and the vibe_check
shared helper.

Key scenarios required by the code review:
- A vibe role shared by multiple users must NOT be deleted when one user
  switches vibe (the bot lacks the Members intent so guild.members is
  incomplete and role deletion would be unsafe).
- A guild with an incomplete member cache (guild.members does not contain
  all role holders) must not trigger role deletion.
- The invoking user's old vibe role IS removed from that user only.
- The new vibe role is assigned correctly.
- Vibe gates (vibe_check) block and allow correctly.
"""

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_role(name, role_id=1):
    role = MagicMock()
    role.name = name
    role.id = role_id
    role.__eq__ = lambda self, other: self.id == getattr(other, "id", None)
    role.__hash__ = lambda self: self.id
    return role


def make_mock_member(roles=None):
    member = MagicMock()
    member.roles = roles or []
    member.remove_roles = AsyncMock()
    member.add_roles = AsyncMock()
    member.id = 42
    return member


def make_mock_guild(roles=None, members=None):
    guild = MagicMock()
    guild.roles = roles or []
    guild.members = members or []
    guild.id = 99
    guild.create_role = AsyncMock()
    return guild


def make_mock_interaction(user, guild):
    interaction = MagicMock()
    interaction.user = user
    interaction.guild = guild
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=True)
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


# ---------------------------------------------------------------------------
# Mood cog helper tests (no Discord API calls)
# ---------------------------------------------------------------------------

class TestMoodHelpers:
    @pytest.fixture(autouse=True)
    def tmp_vibes(self, tmp_path, monkeypatch):
        """Redirect the vibes file to a temp directory."""
        vibes_path = tmp_path / "user_vibes.json"
        monkeypatch.chdir(tmp_path)
        os.makedirs("data", exist_ok=True)
        self.vibes_path = str(tmp_path / "data" / "user_vibes.json")
        return vibes_path

    def _make_cog(self):
        """Instantiate the Mood cog with a fake bot."""
        from modules.mood_with_roles import Mood
        bot = MagicMock()
        return Mood(bot)

    def test_save_and_load_vibe(self):
        cog = self._make_cog()
        cog.save_user_vibe("111", "999", "soft")
        data = cog.load_vibes()
        assert data["111"]["vibe"] == "soft"
        assert data["111"]["guild_id"] == "999"

    def test_save_vibe_overwrites_previous(self):
        cog = self._make_cog()
        cog.save_user_vibe("111", "999", "chaotic")
        cog.save_user_vibe("111", "999", "soft")
        data = cog.load_vibes()
        assert data["111"]["vibe"] == "soft"

    def test_get_role_colour_returns_colour_for_all_vibes(self):
        import discord
        from modules.mood_with_roles import Mood
        cog = Mood(MagicMock())
        from config.valid_vibes import VALID_VIBES
        for v in VALID_VIBES:
            colour = cog.get_role_colour(v)
            assert isinstance(colour, discord.Colour)

    def test_get_role_colour_unknown_returns_default(self):
        import discord
        from modules.mood_with_roles import Mood
        cog = Mood(MagicMock())
        assert cog.get_role_colour("mystery") == discord.Colour.default()


# ---------------------------------------------------------------------------
# Role lifecycle: no deletion even when guild.members looks empty
# ---------------------------------------------------------------------------

class TestRoleLifecycle:
    @pytest.fixture(autouse=True)
    def tmp_data(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        os.makedirs("data", exist_ok=True)

    def _run_setvibe(self, cog, interaction, vibe_value):
        """Call the underlying setvibe coroutine directly, bypassing the
        app_commands.Command wrapper that discord.py installs on decorated methods.
        The new implementation accepts a plain str for the vibe parameter."""
        # The decorator replaces the function with a Command object; the original
        # coroutine is stored as .callback on that Command.
        callback = cog.setvibe.callback
        return callback(cog, interaction, vibe_value)

    @pytest.mark.asyncio
    async def test_old_role_removed_from_user_not_deleted_from_server(self):
        """Switching vibe removes the old role from the user but never deletes
        it from the server — guild.members is unreliable without Members intent."""
        from modules.mood_with_roles import Mood

        old_role = make_mock_role("🌟 Chaotic", role_id=10)
        old_role.delete = AsyncMock()

        new_role = make_mock_role("🌟 Soft", role_id=20)

        user = make_mock_member(roles=[old_role])
        guild = make_mock_guild(
            roles=[old_role, new_role],
            members=[user],
        )

        interaction = make_mock_interaction(user, guild)
        cog = Mood(MagicMock())

        with patch("discord.utils.get", return_value=new_role):
            await self._run_setvibe(cog, interaction, "soft")

        # Old role removed FROM USER only
        user.remove_roles.assert_awaited_once_with(old_role, reason="Vibe changed")
        # Old role NOT deleted from server
        old_role.delete.assert_not_awaited()
        # New role assigned to user
        user.add_roles.assert_awaited_once_with(new_role, reason="Vibe set")

    @pytest.mark.asyncio
    async def test_role_shared_by_multiple_users_is_never_deleted(self):
        """A vibe role held by multiple users must never be deleted when one
        user switches — the server role belongs to the server, not one user."""
        from modules.mood_with_roles import Mood

        old_role = make_mock_role("🌟 Chaotic", role_id=10)
        old_role.delete = AsyncMock()
        new_role = make_mock_role("🌟 Soft", role_id=20)

        user = make_mock_member(roles=[old_role])
        other_user = make_mock_member(roles=[old_role])
        other_user.id = 99

        guild = make_mock_guild(
            roles=[old_role, new_role],
            members=[user, other_user],
        )

        interaction = make_mock_interaction(user, guild)
        cog = Mood(MagicMock())

        with patch("discord.utils.get", return_value=new_role):
            await self._run_setvibe(cog, interaction, "soft")

        old_role.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_incomplete_member_cache_does_not_cause_role_deletion(self):
        """guild.members may not contain all members (no Members intent).
        The bot must never delete a server role based on this incomplete list."""
        from modules.mood_with_roles import Mood

        old_role = make_mock_role("🌟 Chaotic", role_id=10)
        old_role.delete = AsyncMock()
        new_role = make_mock_role("🌟 Soft", role_id=20)

        user = make_mock_member(roles=[old_role])
        # Cache appears empty — real server may have uncached holders
        guild = make_mock_guild(roles=[old_role, new_role], members=[])

        interaction = make_mock_interaction(user, guild)
        cog = Mood(MagicMock())

        with patch("discord.utils.get", return_value=new_role):
            await self._run_setvibe(cog, interaction, "soft")

        old_role.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_same_vibe_does_not_remove_or_readd_role(self):
        """Setting the same vibe twice must not remove or re-add the existing role."""
        from modules.mood_with_roles import Mood

        existing_role = make_mock_role("🌟 Soft", role_id=20)
        user = make_mock_member(roles=[existing_role])
        guild = make_mock_guild(roles=[existing_role])

        interaction = make_mock_interaction(user, guild)
        cog = Mood(MagicMock())

        with patch("discord.utils.get", return_value=existing_role):
            await self._run_setvibe(cog, interaction, "soft")

        # The old role IS the new role: remove_roles must NOT be called
        user.remove_roles.assert_not_awaited()
        # And add_roles must NOT be called either (user already has the role)
        user.add_roles.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_vibe_rejected_server_side(self):
        """A value that bypasses autocomplete must be rejected server-side."""
        from modules.mood_with_roles import Mood

        user = make_mock_member(roles=[])
        guild = make_mock_guild()
        interaction = make_mock_interaction(user, guild)
        cog = Mood(MagicMock())

        await self._run_setvibe(cog, interaction, "definitely_not_a_vibe")

        # followup.send must have been called with an error message
        interaction.followup.send.assert_awaited_once()
        call_args = interaction.followup.send.call_args
        assert "valid vibe" in call_args.args[0].lower() or "valid vibe" in str(call_args).lower()
        # No role operations should have been attempted
        user.add_roles.assert_not_awaited()


# ---------------------------------------------------------------------------
# Autocomplete registration and filtering
# ---------------------------------------------------------------------------

class TestSetvibAutocomplete:
    @pytest.fixture(autouse=True)
    def tmp_data(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        os.makedirs("data", exist_ok=True)

    def test_autocomplete_is_registered_on_vibe_parameter(self):
        """The vibe parameter must have an autocomplete callback registered.

        discord.py stores the callback function (not True) in param.autocomplete
        when @cmd.autocomplete("vibe") is used.
        """
        from modules.mood_with_roles import Mood
        cog = Mood(MagicMock())
        cmd = cog.setvibe
        param = cmd._params.get("vibe")
        assert param is not None, "vibe parameter not found on setvibe command"
        # autocomplete is the callback function when registered, or MISSING/None when not
        import inspect
        assert callable(param.autocomplete), (
            f"expected autocomplete callback to be callable, got {param.autocomplete!r}"
        )

    @pytest.mark.asyncio
    async def test_autocomplete_returns_all_vibes_for_empty_input(self):
        """Empty string should return all valid vibes."""
        from modules.mood_with_roles import Mood
        from config.valid_vibes import VALID_VIBES
        cog = Mood(MagicMock())
        interaction = MagicMock()
        results = await cog.setvibe_autocomplete(interaction, "")
        returned_values = [c.value for c in results]
        assert set(returned_values) == set(VALID_VIBES)

    @pytest.mark.asyncio
    async def test_autocomplete_filters_by_prefix(self):
        """Typing 'so' should only return 'soft'."""
        from modules.mood_with_roles import Mood
        cog = Mood(MagicMock())
        interaction = MagicMock()
        results = await cog.setvibe_autocomplete(interaction, "so")
        values = [c.value for c in results]
        assert values == ["soft"]

    @pytest.mark.asyncio
    async def test_autocomplete_is_case_insensitive(self):
        """Uppercase input must still match correctly."""
        from modules.mood_with_roles import Mood
        cog = Mood(MagicMock())
        interaction = MagicMock()
        results = await cog.setvibe_autocomplete(interaction, "CH")
        values = [c.value for c in results]
        assert "chaotic" in values

    @pytest.mark.asyncio
    async def test_autocomplete_returns_empty_for_no_match(self):
        """Unrecognised input should return no suggestions."""
        from modules.mood_with_roles import Mood
        cog = Mood(MagicMock())
        interaction = MagicMock()
        results = await cog.setvibe_autocomplete(interaction, "zzzzz")
        assert results == []


# ---------------------------------------------------------------------------
# Vibe gate helper
# ---------------------------------------------------------------------------

class TestVibeGate:
    @pytest.fixture(autouse=True)
    def tmp_data(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        os.makedirs("data", exist_ok=True)
        vibes = {"111": {"vibe": "soft"}}
        with open("data/user_vibes.json", "w") as f:
            json.dump(vibes, f)

    def _make_interaction(self, user_id=111):
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = user_id
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    @pytest.mark.asyncio
    async def test_allowed_vibe_returns_true(self):
        from utils.vibe_check import vibe_gate
        interaction = self._make_interaction()
        result = await vibe_gate(interaction, ["soft", "neutral"], "blocked")
        assert result is True
        interaction.response.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blocked_vibe_returns_false_and_replies(self):
        from utils.vibe_check import vibe_gate
        interaction = self._make_interaction()
        result = await vibe_gate(interaction, ["chaotic", "lewd"], "You're too gentle!")
        assert result is False
        interaction.response.send_message.assert_awaited_once()
        call_kwargs = interaction.response.send_message.call_args
        assert "ephemeral" in call_kwargs.kwargs
        assert call_kwargs.kwargs["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_no_vibe_set_is_blocked(self):
        """A user with no vibe stored must be blocked from gated commands."""
        from utils.vibe_check import vibe_gate
        interaction = self._make_interaction(user_id=999)  # not in vibes file
        result = await vibe_gate(interaction, ["chaotic"], "nope")
        assert result is False

    @pytest.mark.asyncio
    async def test_blocked_reply_uses_followup_when_response_done(self):
        from utils.vibe_check import vibe_gate
        interaction = self._make_interaction()
        interaction.response.is_done = MagicMock(return_value=True)
        result = await vibe_gate(interaction, ["chaotic"], "blocked!")
        assert result is False
        interaction.followup.send.assert_awaited_once()
