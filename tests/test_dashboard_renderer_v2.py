from datetime import datetime

from PIL import Image

from ui.renderers import dashboard_renderer as dr
from ui.renderers.font_manager import font_supports_text, get_font


def test_payload_hash_stable():
    p1 = {"a": 1, "b": 2}
    p2 = {"b": 2, "a": 1}
    assert dr.payload_hash(p1) == dr.payload_hash(p2)


def test_template_loading_from_config_path(tmp_path, monkeypatch):
    tpl = tmp_path / "dashboard_template_v2.png"
    Image.new("RGBA", (1536, 1024), (10, 10, 10, 255)).save(tpl)
    monkeypatch.setattr(dr, "DASHBOARD_TEMPLATE_PATH", tpl)
    image = dr.load_template()
    assert image.size == (1536, 1024)


def test_render_fallback_without_template(tmp_path, monkeypatch):
    monkeypatch.setattr(dr, "DASHBOARD_TEMPLATE_PATH", tmp_path / "missing.png")
    monkeypatch.setattr(dr, "CACHE_DIR", tmp_path / "cache")
    out = dr.render_dashboard({"title": "Дашборд", "revenue_text": "123 456 ₽", "target_text": "из 500 000 ₽", "progress": 0.61})
    assert out.exists()


def test_cyrillic_font_supported():
    font = get_font(36, "bold")
    assert font_supports_text(font, "Дашборд Смена Выручка Осталось Обновлено")


def test_render_long_sum(tmp_path, monkeypatch):
    monkeypatch.setattr(dr, "DASHBOARD_TEMPLATE_PATH", tmp_path / "missing.png")
    monkeypatch.setattr(dr, "CACHE_DIR", tmp_path / "cache")
    out = dr.render_dashboard(
        {
            "title": "Дашборд",
            "status": "Смена активна",
            "period": "1-я декада • 1–10 марта",
            "revenue_text": "123 456 789 012 ₽",
            "target_text": "из 999 999 999 999 ₽",
            "progress": 0.35,
            "updated_at": datetime.now(),
        }
    )
    assert out.exists()
