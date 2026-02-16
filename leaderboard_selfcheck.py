from bot import build_leaderboard_image_bytes


def main() -> int:
    decade_title = "1-10 февраля"
    decade_leaders = [
        {"name": "Иван", "total_amount": 12345, "shift_count": 3},
        {"name": "Петр", "total_amount": 9800, "shift_count": 2},
    ]
    active_leaders = [
        {"name": "Анна", "total_amount": 4500, "shift_count": 1},
    ]

    image = build_leaderboard_image_bytes(decade_title, decade_leaders, active_leaders)
    if image is None:
        print("FAIL")
        return 1

    payload = image.getvalue()
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        print("FAIL")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
