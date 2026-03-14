from services.fast_input_service import parse_fast_input


def test_empty_input():
    r = parse_fast_input("", 1, {})
    assert r.error_message


def test_only_number_no_service(monkeypatch):
    from services import fast_input_service as fi
    monkeypatch.setattr(fi.DatabaseManager, "get_user_combos", lambda user_id: [])
    r = parse_fast_input("а123вс777", 1, {})
    assert not r.service_ids


def test_unknown_alias(monkeypatch):
    from services import fast_input_service as fi

    monkeypatch.setattr(fi.DatabaseManager, "get_user_combos", lambda user_id: [])
    r = parse_fast_input("а123вс777 xyz", 1, {1: ["пзз"]})
    assert "Не распознал" in r.error_message
    assert "xyz" in r.unknown_tokens


def test_conflict_alias(monkeypatch):
    from services import fast_input_service as fi

    monkeypatch.setattr(fi.DatabaseManager, "get_user_combos", lambda user_id: [{"id": 1, "alias": "пзз", "service_ids": [1]}])
    r = parse_fast_input("а123вс777 пзз", 1, {1: ["пзз"]})
    assert "Конфликт" in r.error_message


def test_two_combo_rejected(monkeypatch):
    from services import fast_input_service as fi

    combos = [{"id": 1, "alias": "к1", "service_ids": [1]}, {"id": 2, "alias": "к2", "service_ids": [2]}]
    monkeypatch.setattr(fi.DatabaseManager, "get_user_combos", lambda user_id: combos)
    monkeypatch.setattr(fi.DatabaseManager, "get_combo", lambda combo_id, user_id: next(c for c in combos if c["id"] == combo_id))
    r = parse_fast_input("а123вс777 к1 к2", 1, {})
    assert "одно комбо" in r.error_message


def test_combo_plus_service(monkeypatch):
    from services import fast_input_service as fi

    combos = [{"id": 1, "alias": "пзз", "service_ids": [2]}]
    monkeypatch.setattr(fi.DatabaseManager, "get_user_combos", lambda user_id: combos)
    monkeypatch.setattr(fi.DatabaseManager, "get_combo", lambda combo_id, user_id: combos[0])
    r = parse_fast_input("а123вс777 пзз чер", 1, {3: ["чер"]})
    assert r.service_ids == [2, 3]
