from ui.renderers.dashboard_renderer import payload_hash, render_dashboard


def test_payload_hash_stable():
    p1 = {"a": 1, "b": 2}
    p2 = {"b": 2, "a": 1}
    assert payload_hash(p1) == payload_hash(p2)


def test_render_fallback_without_template(tmp_path, monkeypatch):
    from ui.renderers import dashboard_renderer as dr

    monkeypatch.setattr(dr, "DASHBOARD_TEMPLATE_PATH", tmp_path / "missing.png")
    monkeypatch.setattr(dr, "CACHE_DIR", tmp_path / "cache")
    out = render_dashboard({"title": "T", "revenue_text": "1 ₽", "target_text": "из 2 ₽"})
    assert out.exists()
