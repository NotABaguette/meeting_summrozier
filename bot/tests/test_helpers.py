from datetime import datetime

from bot.helpers import (
    StopPolicy,
    decide_stop,
    normalize_room_url,
    output_filename,
    safe_room_name,
)


def test_normalize_room_url_with_name():
    assert normalize_room_url("https://meet.x.com", "Standup") == "https://meet.x.com/Standup"
    assert normalize_room_url("https://meet.x.com/", "/Standup") == "https://meet.x.com/Standup"


def test_normalize_room_url_with_full_url():
    url = "https://meet.x.com/SomeRoom"
    assert normalize_room_url("https://ignored", url) == url


def test_safe_room_name_from_url():
    assert safe_room_name("https://meet.x.com/Weekly-Sync?jwt=abc#x") == "Weekly-Sync"
    assert safe_room_name("My Room!!") == "My_Room_"
    assert safe_room_name("") == "meeting"


def test_output_filename():
    when = datetime(2026, 6, 18, 10, 15, 0)
    assert output_filename("Standup", when) == "Standup-20260618-101500.ogg"


def test_decide_stop_max_duration():
    p = StopPolicy(max_seconds=100, leave_after_alone_seconds=30, join_grace_seconds=300)
    stop, why = decide_stop(2, 0, 101, True, p)
    assert stop and why == "max_duration"


def test_decide_stop_nobody_joined():
    p = StopPolicy(max_seconds=10000, leave_after_alone_seconds=30, join_grace_seconds=300)
    assert decide_stop(0, 0, 301, False, p) == (True, "nobody_joined")
    # Still within grace -> keep waiting.
    assert decide_stop(0, 0, 100, False, p) == (False, "")


def test_decide_stop_everyone_left():
    p = StopPolicy(max_seconds=10000, leave_after_alone_seconds=30, join_grace_seconds=300)
    # Had people, now alone for 31s -> stop.
    assert decide_stop(0, 31, 600, True, p) == (True, "everyone_left")
    # Alone only 10s -> keep recording.
    assert decide_stop(0, 10, 600, True, p) == (False, "")


def test_decide_stop_active_meeting_continues():
    p = StopPolicy(max_seconds=10000, leave_after_alone_seconds=30, join_grace_seconds=300)
    assert decide_stop(3, 0, 600, True, p) == (False, "")
