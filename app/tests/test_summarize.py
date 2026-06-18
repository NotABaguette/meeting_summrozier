import json

from meeting_intel.engine import summarize


def test_chunk_text_small_returns_single():
    assert summarize.chunk_text("hello world", 100) == ["hello world"]


def test_chunk_text_empty():
    assert summarize.chunk_text("", 100) == []
    assert summarize.chunk_text("   ", 100) == []


def test_chunk_text_splits_on_lines():
    text = "\n".join(f"line {i}" for i in range(100))
    chunks = summarize.chunk_text(text, 50)
    assert len(chunks) > 1
    assert all(len(c) <= 60 for c in chunks)  # roughly bounded
    # No content lost.
    assert "line 0" in chunks[0]
    assert "line 99" in "".join(chunks)


def test_chunk_text_hard_splits_long_line():
    text = "x" * 250
    chunks = summarize.chunk_text(text, 100)
    assert len(chunks) == 3
    assert "".join(chunks) == text


def test_parse_summary_clean_json():
    raw = json.dumps(
        {
            "title": "T",
            "executive_summary": "summary",
            "key_points": ["a", "b"],
            "decisions": ["d"],
            "action_items": [{"owner": "Ali", "task": "do x", "due": "Mon"}],
            "topics": ["t"],
            "next_steps": ["n"],
            "journal": [{"heading": "h", "details": "x"}],
            "participants": ["Speaker 1"],
        }
    )
    out = summarize.parse_summary(raw)
    assert out["executive_summary"] == "summary"
    assert out["key_points"] == ["a", "b"]
    assert out["action_items"][0]["owner"] == "Ali"
    assert out["journal"][0]["heading"] == "h"


def test_parse_summary_json_embedded_in_text():
    raw = 'Sure! Here is the JSON:\n{"executive_summary": "hi", "key_points": ["x"]}\nDone.'
    out = summarize.parse_summary(raw)
    assert out["executive_summary"] == "hi"
    assert out["key_points"] == ["x"]


def test_parse_summary_garbage_falls_back_to_raw():
    out = summarize.parse_summary("totally not json")
    assert out["executive_summary"] == "totally not json"
    assert out["key_points"] == []
    assert out["action_items"] == []


def test_parse_summary_action_items_as_strings():
    raw = json.dumps({"action_items": ["just do it", {"task": "and this"}]})
    out = summarize.parse_summary(raw)
    tasks = [a["task"] for a in out["action_items"]]
    assert "just do it" in tasks
    assert "and this" in tasks


def test_parse_summary_normalizes_string_lists():
    raw = json.dumps({"key_points": "single string"})
    out = summarize.parse_summary(raw)
    assert out["key_points"] == ["single string"]


def test_lang_instruction_auto_mentions_persian():
    inst = summarize._lang_instruction("auto")
    assert "same language" in inst.lower()
    assert "persian" in inst.lower()


def test_lang_instruction_explicit_persian():
    inst = summarize._lang_instruction("fa")
    assert "Persian" in inst


def test_prompts_include_schema_and_language():
    p = summarize.build_single_prompt("transcript here", ["Speaker 1"], "fa")
    assert "executive_summary" in p
    assert "transcript here" in p
    assert "Persian" in p
    assert "Speaker 1" in p

    rp = summarize.build_reduce_prompt("notes", None, "auto")
    assert "executive_summary" in rp
    assert "same language" in rp.lower()

    mp = summarize.build_map_prompt("chunk text", "fa")
    assert "chunk text" in mp
    assert "Persian" in mp
