from meeting_intel.engine import merge


def test_format_timestamp():
    assert merge.format_timestamp(0) == "00:00:00"
    assert merge.format_timestamp(65) == "00:01:05"
    assert merge.format_timestamp(3661) == "01:01:01"
    assert merge.format_timestamp(None) == "00:00:00"
    assert merge.format_timestamp(-5) == "00:00:00"


def test_assign_speakers_by_overlap():
    segments = [
        {"start": 0.0, "end": 2.0, "text": "hello"},
        {"start": 2.5, "end": 4.0, "text": "world"},
    ]
    turns = [
        {"start": 0.0, "end": 2.2, "speaker": "Speaker 1"},
        {"start": 2.2, "end": 5.0, "speaker": "Speaker 2"},
    ]
    out = merge.assign_speakers(segments, turns)
    assert out[0]["speaker"] == "Speaker 1"
    assert out[1]["speaker"] == "Speaker 2"


def test_assign_speakers_no_turns_returns_copy():
    segments = [{"start": 0, "end": 1, "text": "x"}]
    out = merge.assign_speakers(segments, [])
    assert out[0]["text"] == "x"
    assert out is not segments


def test_assign_speakers_nearest_when_no_overlap():
    segments = [{"start": 10.0, "end": 11.0, "text": "late"}]
    turns = [
        {"start": 0.0, "end": 1.0, "speaker": "Speaker 1"},
        {"start": 9.0, "end": 9.5, "speaker": "Speaker 2"},
    ]
    out = merge.assign_speakers(segments, turns)
    assert out[0]["speaker"] == "Speaker 2"


def test_group_segments_merges_consecutive_same_speaker():
    segments = [
        {"start": 0, "end": 1, "speaker": "A", "text": "hi"},
        {"start": 1, "end": 2, "speaker": "A", "text": "there"},
        {"start": 2, "end": 3, "speaker": "B", "text": "yo"},
    ]
    blocks = merge.group_segments(segments)
    assert len(blocks) == 2
    assert blocks[0]["text"] == "hi there"
    assert blocks[0]["end"] == 2
    assert blocks[1]["speaker"] == "B"


def test_group_segments_skips_empty():
    segments = [{"start": 0, "end": 1, "speaker": "A", "text": "   "}]
    assert merge.group_segments(segments) == []


def test_build_transcript_text():
    segments = [
        {"start": 0, "end": 1, "speaker": "Speaker 1", "text": "hello"},
        {"start": 65, "end": 66, "speaker": None, "text": "no speaker"},
    ]
    text = merge.build_transcript_text(segments)
    assert "[00:00:00] Speaker 1: hello" in text
    assert "[00:01:05] no speaker" in text


def test_list_speakers_order():
    segments = [
        {"speaker": "B", "text": "a"},
        {"speaker": "A", "text": "b"},
        {"speaker": "B", "text": "c"},
    ]
    assert merge.list_speakers(segments) == ["B", "A"]
