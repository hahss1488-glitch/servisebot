from datetime import date

from services.dashboard_state_service import DashboardStateService


def test_snapshot_consistency(monkeypatch):
    from services import dashboard_state_service as ds

    monkeypatch.setattr(ds.DatabaseManager, "get_decade_goal", lambda user_id: 50000)
    monkeypatch.setattr(ds.DatabaseManager, "get_user_total_between_dates", lambda user_id, s, e: 30000)
    monkeypatch.setattr(ds.DatabaseManager, "get_cars_count_between_dates", lambda user_id, s, e: 100)
    monkeypatch.setattr(ds.DatabaseManager, "get_shifts_count_between_dates", lambda user_id, s, e: 10)
    monkeypatch.setattr(ds.DatabaseManager, "get_active_shift", lambda user_id: {"id": 7, "shift_target": 4000})
    monkeypatch.setattr(ds.DatabaseManager, "get_shift_total", lambda shift_id: 1500)

    snapshot = DashboardStateService.build_snapshot(1, today=date(2026, 3, 7))
    assert snapshot.decade_goal == 50000
    assert snapshot.current_revenue == 30000
    assert snapshot.remaining_to_goal == 20000
    assert snapshot.needed_per_shift >= 0
    assert snapshot.status == "Смена активна"
