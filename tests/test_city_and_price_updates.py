import database
import bot
from config import SERVICES, validate_car_number


def test_supported_cities_have_their_expected_timezones():
    cities = dict(bot.CITIES)
    assert list(cities) == [
        "Москва", "Санкт-Петербург", "Нижний Новгород", "Екатеринбург", "Самара",
        "Казань", "Новосибирск", "Челябинск", "Сочи", "Пермь", "Краснодар",
        "Ярославль", "Ростов-на-Дону", "Тольятти", "Тула", "Уфа",
    ]
    assert cities["Новосибирск"] == "Asia/Novosibirsk"
    assert cities["Екатеринбург"] == cities["Челябинск"] == cities["Пермь"] == cities["Уфа"] == "Asia/Yekaterinburg"


def test_city_is_saved_with_timezone(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "city.sqlite"))
    database.init_database()
    database.DatabaseManager.register_user(101, "Андрей")
    user = database.DatabaseManager.get_user(101)
    database.DatabaseManager.set_user_city(user["id"], "Новосибирск", "Asia/Novosibirsk")
    prefs = database.DatabaseManager.get_price_preferences(user["id"])
    assert prefs["city"] == "Новосибирск"
    assert prefs["timezone"] == "Asia/Novosibirsk"


def test_short_and_full_car_numbers_are_accepted():
    assert validate_car_number("А123ВС")[0]
    assert validate_car_number("А123ВС777")[0]


def test_requested_nested_services_and_prices_are_in_price_text():
    assert SERVICES[34]["children"] == [35, 36, 37, 38]
    assert SERVICES[39]["children"] == [41, 42, 43, 44]
    assert SERVICES[48]["day_price"] == 1406
    assert SERVICES[48]["night_price"] == 1111
    assert "Обкатка ТС — 6 часов - 1406₽ / 1111₽" in bot.build_price_text()
    assert "Вывод в город - 31₽ / 25₽" in bot.build_price_text()


def test_leaderboard_includes_city_next_to_name():
    text = bot.build_leaderboard_text("1-я декада", [{"name": "Андрей", "city": "Новосибирск", "total_amount": 100}])
    assert "Андрей (Новосибирск)" in text
