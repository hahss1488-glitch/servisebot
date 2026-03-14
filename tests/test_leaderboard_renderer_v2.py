from datetime import datetime

from PIL import Image

from config import LEADERBOARD_TEMPLATE_PATH
from ui.renderers import leaderboard_renderer as lr


def _payload(name: str = "Длинное имя пользователя для проверки рендера"):
    return {
        "period_text": "1–10 МАРТА",
        "updated_text": datetime(2026, 3, 6, 6, 24),
        "leaders": [
            {"place": 1, "name": name, "amount": "29 529 ₽", "rank_prefix": "ЛЕГЕНДА", "avatar_path": ""},
            {"place": 2, "name": name, "amount": "18 889 ₽", "rank_prefix": "PRO", "avatar_path": ""},
            {"place": 3, "name": "Nikita", "amount": "16 885 ₽", "rank_prefix": "ELITE", "avatar_path": ""},
            {"place": 4, "name": "Артём", "amount": "14 230 ₽"},
            {"place": 5, "name": "Руслан", "amount": "13 980 ₽"},
        ],
    }


def test_template_path_constant():
    assert str(LEADERBOARD_TEMPLATE_PATH).endswith("ui/assets/leaderboard/leaderboard_template_v2.png")


def test_payload_hash_stable():
    p1 = _payload()
    p2 = _payload()
    assert lr.payload_hash(p1) == lr.payload_hash(p2)


def test_render_with_long_name(tmp_path, monkeypatch):
    tpl = tmp_path / "leaderboard_template_v2.png"
    Image.new("RGBA", (1024, 1536), (20, 20, 20, 255)).save(tpl)
    monkeypatch.setattr(lr, "LEADERBOARD_TEMPLATE_PATH", tpl)
    monkeypatch.setattr(lr, "CACHE_DIR", tmp_path / "cache")
    out = lr.render_leaderboard(_payload())
    assert out.exists()


def test_render_fallback_avatar_when_missing(tmp_path, monkeypatch):
    tpl = tmp_path / "leaderboard_template_v2.png"
    Image.new("RGBA", (1024, 1536), (20, 20, 20, 255)).save(tpl)
    monkeypatch.setattr(lr, "LEADERBOARD_TEMPLATE_PATH", tpl)
    monkeypatch.setattr(lr, "CACHE_DIR", tmp_path / "cache")
    payload = _payload()
    payload["leaders"][0]["avatar_path"] = str(tmp_path / "missing.jpg")
    out = lr.render_leaderboard(payload)
    assert out.exists()


def test_render_with_incomplete_top(tmp_path, monkeypatch):
    tpl = tmp_path / "leaderboard_template_v2.png"
    Image.new("RGBA", (1024, 1536), (20, 20, 20, 255)).save(tpl)
    monkeypatch.setattr(lr, "LEADERBOARD_TEMPLATE_PATH", tpl)
    monkeypatch.setattr(lr, "CACHE_DIR", tmp_path / "cache")
    payload = {"period_text": "1–10 МАРТА", "updated_text": "06.03.2026 06:24 МСК", "leaders": [{"place": 1, "name": "A", "amount": "100 ₽", "rank_prefix": "ЛЕГЕНДА", "avatar_path": ""}]}
    out = lr.render_leaderboard(payload)
    assert out.exists()
