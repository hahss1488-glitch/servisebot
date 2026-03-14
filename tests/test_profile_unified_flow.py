import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import bot


def test_account_entrypoints_use_unified_renderer(monkeypatch):
    db_user = {"id": 7, "name": "User"}
    monkeypatch.setattr(bot.DatabaseManager, "get_user", lambda telegram_id: db_user)

    render = AsyncMock()
    monkeypatch.setattr(bot, "_render_profile_view", render)

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=77),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    context = SimpleNamespace(user_data={"awaiting_profile_avatar": True})

    asyncio.run(bot.account_message(update, context))
    render.assert_awaited_once()


def test_account_info_callback_routes_to_unified_renderer(monkeypatch):
    show = AsyncMock()
    monkeypatch.setattr(bot, "_show_unified_profile_from_callback", show)

    query = SimpleNamespace(from_user=SimpleNamespace(id=99))
    asyncio.run(bot.account_info_callback(query, SimpleNamespace()))
    show.assert_awaited_once()


@pytest.mark.parametrize(
    "cb",
    ["profile_avatar_upload", "profile_avatar_reset", "profile_change_rank_prefix"],
)
def test_profile_keyboard_has_expected_callbacks(cb, monkeypatch):
    monkeypatch.setattr(bot, "get_section_photo_file_id", lambda section: "")
    kb = bot.build_profile_keyboard({"id": 1}, 11)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert cb in callbacks


def test_expired_subscription_allows_profile_callbacks():
    assert bot.is_allowed_when_expired_callback("profile_avatar_upload")
    assert bot.is_allowed_when_expired_callback("profile_avatar_reset")
    assert bot.is_allowed_when_expired_callback("profile_change_rank_prefix")
