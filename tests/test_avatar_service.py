from io import BytesIO

from PIL import Image

from services.avatar_service import save_custom_avatar


def test_save_custom_avatar_square(tmp_path, monkeypatch):
    from services import avatar_service as av

    monkeypatch.setattr(av.DatabaseManager, "set_custom_avatar", lambda user_id, path: None)
    img = Image.new("RGB", (800, 400), "red")
    b = BytesIO()
    img.save(b, format="PNG")
    out = save_custom_avatar(1, b.getvalue(), tmp_path)
    with Image.open(out) as saved:
        assert saved.size == (512, 512)
