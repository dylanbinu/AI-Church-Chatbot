"""Standalone questions are cached. Follow-ups are not."""
from server import (
    ChatResponse,
    answer_cache_key,
    clear_answer_cache,
    get_cached_answer,
    normalize_question,
    store_cached_answer,
)


def setup_function():
    clear_answer_cache()


def test_normalize_collapses_wording():
    assert normalize_question("  When are service times?? ") == "when are service times"


def test_follow_ups_are_not_cached():
    history = [type("Msg", (), {"role": "user", "content": "service times"})()]
    assert answer_cache_key("heritage", "1", "built", "Saturday?", history) is None


def test_repeat_question_hits_cache():
    key = answer_cache_key("heritage", "1", "built", "When are service times?", [])
    stored = ChatResponse(response="Sundays at 9.", sources=["https://heritagechurch.com/visit"], church_id="heritage")
    store_cached_answer(key, stored)
    hit = get_cached_answer(key)
    assert hit is not None
    assert hit.response == "Sundays at 9."
    hit.response = "changed"
    again = get_cached_answer(key)
    assert again.response == "Sundays at 9."


def test_new_data_version_misses():
    first = answer_cache_key("heritage", "1", "built", "service times", [])
    second = answer_cache_key("heritage", "2", "built", "service times", [])
    store_cached_answer(first, ChatResponse(response="old", sources=[], church_id="heritage"))
    assert get_cached_answer(second) is None
