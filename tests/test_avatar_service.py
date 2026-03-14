from io import BytesIO

from PIL import Image

from services.avatar_service import get_avatar_source, get_effective_avatar, reset_avatar, save_custom_avatar


def test_save_custom_avatar_square(tmp_path, monkeypatch):
    from services import avatar_service as av

    monkeypatch.setattr(av.DatabaseManager, "set_custom_avatar", lambda user_id, path: None)
    img = Image.new("RGB", (800, 400), "red")
    b = BytesIO()
    img.save(b, format="PNG")
    out = save_custom_avatar(1, b.getvalue(), tmp_path)
    with Image.open(out) as saved:
        assert saved.size == (512, 512)


def test_reset_avatar(monkeypatch):
    from services import avatar_service as av

    monkeypatch.setattr(av.DatabaseManager, "reset_avatar_source", lambda user_id: None)
    monkeypatch.setattr(av, "get_avatar_source", lambda user_id: "default")
    assert reset_avatar(1) == "default"


def test_fallback_avatar_source(tmp_path, monkeypatch):
    from services import avatar_service as av

    tg = tmp_path / "tg.jpg"
    Image.new("RGB", (10, 10), "blue").save(tg)
    monkeypatch.setattr(
        av.DatabaseManager,
        "get_avatar_settings",
        lambda user_id: {"avatar_source": "custom", "custom_avatar_path": str(tmp_path / "missing.jpg"), "telegram_avatar_path": str(tg)},
    )
    assert get_avatar_source(1) == "telegram"
    assert get_effective_avatar(1) == str(tg)
