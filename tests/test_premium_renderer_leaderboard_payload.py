from ui.premium_renderer import _leaderboard_payload, sanitize_rank_prefix


def test_payload_uses_rank_prefix_from_source():
    payload = _leaderboard_payload(
        "2-я декада: 11-20 марта",
        [{"name": "Иван", "total_amount": 15741, "rank_prefix": "ЛЕГЕНДА+", "avatar_path": "x.jpg"}],
        None,
    )
    assert payload["leaders"][0]["rank_prefix"] == "ЛЕГЕНДА+"
    assert payload["leaders"][0]["avatar_path"] == "x.jpg"


def test_payload_falls_back_to_default_prefixes():
    payload = _leaderboard_payload("Период", [{"name": "Иван", "total_amount": 100}], None)
    assert payload["leaders"][0]["rank_prefix"] == "ЛЕГЕНДА"


def test_payload_sanitizes_bad_rank_prefix():
    payload = _leaderboard_payload("Период", [{"name": "Иван", "total_amount": 100, "rank_prefix": "👤 Профиль"}], None)
    assert payload["leaders"][0]["rank_prefix"] == "ЛЕГЕНДА"


def test_sanitize_rank_prefix_trim_and_limit():
    assert sanitize_rank_prefix("   KING   OF   ROAD   ", 2) == "KING OF ROAD"
    assert len(sanitize_rank_prefix("X" * 100, 3)) <= 20
