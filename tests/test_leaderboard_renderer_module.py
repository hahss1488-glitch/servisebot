from io import BytesIO

from PIL import Image

from ui import leaderboard_renderer as lr


def test_render_leaderboard_happy_path(tmp_path):
    template = tmp_path / "leaderboard_template_v2.png"
    Image.new("RGBA", (1024, 1536), (20, 20, 20, 255)).save(template)
    output = tmp_path / "result.png"

    image = lr.render_leaderboard(
        players=[
            {"name": "Некий Лох", "prefix": "ЛЕГЕНДА", "money": 17737, "avatar_path": None},
            {"name": "bro", "prefix": "AXAXAXAX", "money": 14837, "avatar_path": None},
            {"name": "Alex Sholohov", "prefix": "ELITE", "money": 8288, "avatar_path": None},
            {"name": "Неизвестный ге...", "money": 5473},
            {"name": "Rgrxch", "money": 6473},
        ],
        output_path=output,
        template_path=template,
    )

    assert image.size == (1024, 1536)
    assert output.exists()


def test_render_to_bytes(tmp_path):
    template = tmp_path / "leaderboard_template_v2.png"
    Image.new("RGBA", (1024, 1536), (20, 20, 20, 255)).save(template)

    payload = [{"name": "A", "money": 1}]
    data = lr.render_leaderboard_to_bytes(payload, template_path=template)

    assert isinstance(data, BytesIO)
    assert data.getbuffer().nbytes > 0


def test_format_money_and_initials():
    assert lr.format_money(17737) == "17 737 ₽"
    assert lr.format_money("bad") == "0 ₽"
    assert lr.safe_get_initials("Некий Лох") == "НЛ"
    assert lr.safe_get_initials("bro") == "BR"
