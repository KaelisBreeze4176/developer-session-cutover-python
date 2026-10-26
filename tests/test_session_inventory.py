from src.session_inventory import SessionRecord, decide_cutover


def test_cutover_keeps_selected_session_and_orders_other_sessions() -> None:
    sessions = [
        SessionRecord("session-current", "user-123", "password"),
        SessionRecord("session-laptop", "user-123", "oauth"),
        SessionRecord("session-phone", "user-123", "password"),
    ]

    assert decide_cutover(sessions, "session-current") == ["session-laptop", "session-phone"]

