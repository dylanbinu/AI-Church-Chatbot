"""Retrieval ranking, follow-up queries, and per-church path rules."""
from langchain_core.documents import Document

from registry import DEFAULT_RETRIEVAL, get_church, load_registry
from retrieval import build_search_query, retrieve_and_rank, urls_for_intent


class _Store:
    def __init__(self, scored, stored):
        self.scored = scored
        self.stored = stored
        self.searches = 0

    def similarity_search_with_relevance_scores(self, query, k=4, filter=None):
        self.searches += 1
        self.last_query = query
        self.last_filter = filter
        return self.scored[:k]

    def similarity_search(self, *args, **kwargs):
        raise AssertionError("intent pages must be loaded by metadata, not re-embedded")

    def get(self, where=None, include=None):
        return {
            "documents": [doc.page_content for doc in self.stored],
            "metadatas": [doc.metadata for doc in self.stored],
        }


def _doc(url: str, text: str) -> Document:
    return Document(page_content=text, metadata={"source": url, "church_id": "heritage"})


def test_follow_up_includes_previous_user_turn():
    history = [
        {"role": "user", "content": "What are the service times?"},
        {"role": "assistant", "content": "Sundays at 9 and 11."},
    ]
    query = build_search_query("What about Saturday?", history)
    assert query == "What are the service times?\nWhat about Saturday?"


def test_same_question_is_not_repeated():
    history = [{"role": "user", "content": "Service times"}]
    assert build_search_query("Service times", history) == "Service times"


def test_intent_pages_load_without_a_second_embedding():
    visit = _doc("https://heritagechurch.com/visit", "Sundays at 9:00 AM and 11:00 AM.")
    sermon = _doc("https://heritagechurch.com/sermons/hope", "A sermon about hope and grace.")
    store = _Store(scored=[(sermon, 0.96)], stored=[visit, sermon])
    docs = retrieve_and_rank(
        "What are the service times?",
        store,
        {
            "https://heritagechurch.com/visit",
            "https://heritagechurch.com/sermons/hope",
        },
        church_id="heritage",
        profile=DEFAULT_RETRIEVAL,
    )
    assert store.searches == 1
    assert docs[0].metadata["source"] == "https://heritagechurch.com/visit"


def test_close_semantic_match_beats_a_weaker_high_value_page():
    sermon = _doc("https://heritagechurch.com/sermons/hope", "Hope and grace in the message.")
    give = _doc("https://heritagechurch.com/give", "Give online or in person.")
    store = _Store(scored=[(sermon, 0.93), (give, 0.40)], stored=[])
    docs = retrieve_and_rank(
        "what was the message about hope",
        store,
        {
            "https://heritagechurch.com/sermons/hope",
            "https://heritagechurch.com/give",
        },
        church_id="heritage",
        profile=DEFAULT_RETRIEVAL,
    )
    assert docs[0].metadata["source"].endswith("/hope")


def test_who_alone_does_not_force_staff_pages():
    staff = _doc("https://heritagechurch.com/team", "Pastor Ann leads the team.")
    about_faith = _doc("https://heritagechurch.com/beliefs", "We believe in grace.")
    store = _Store(scored=[(about_faith, 0.8)], stored=[staff])
    docs = retrieve_and_rank(
        "who is Jesus",
        store,
        {"https://heritagechurch.com/team", "https://heritagechurch.com/beliefs"},
        church_id="heritage",
        profile=DEFAULT_RETRIEVAL,
    )
    assert [doc.metadata["source"] for doc in docs] == ["https://heritagechurch.com/beliefs"]


def test_named_campus_outranks_a_generic_high_value_page():
    downtown = _doc("https://heritagechurch.com/locations/downtown", "Downtown meets at 10.")
    give = _doc("https://heritagechurch.com/give", "Give online.")
    store = _Store(scored=[(downtown, 0.55), (give, 0.57)], stored=[])
    docs = retrieve_and_rank(
        "downtown service",
        store,
        {
            "https://heritagechurch.com/locations/downtown",
            "https://heritagechurch.com/give",
        },
        church_id="heritage",
        profile=DEFAULT_RETRIEVAL,
    )
    assert docs[0].metadata["source"].endswith("/downtown")


def test_result_cap():
    scored = [
        (_doc(f"https://heritagechurch.com/page-{i}", f"page {i} content"), 0.9 - i * 0.01)
        for i in range(12)
    ]
    store = _Store(scored=scored, stored=[])
    urls = {doc.metadata["source"] for doc, _ in scored}
    docs = retrieve_and_rank("hello", store, urls, church_id="heritage", profile=DEFAULT_RETRIEVAL)
    assert len(docs) == 6


def test_custom_church_paths(tmp_path):
    registry = tmp_path / "churches.json"
    registry.write_text(
        """
        {
          "churches": {
            "grace": {
              "name": "Grace",
              "domain": "grace.example",
              "start_url": "https://grace.example",
              "retrieval": {
                "intents": [
                  {"any": ["give"], "paths": ["/offerings"], "limit": 1}
                ]
              }
            }
          }
        }
        """,
        encoding="utf-8",
    )
    grace = get_church("grace", registry)
    assert grace.retrieval.intents[0].paths == ("/offerings",)
    assert grace.retrieval.high_value == DEFAULT_RETRIEVAL.high_value

    offering = _doc("https://grace.example/offerings", "Place gifts in the offering.")
    other = _doc("https://grace.example/blog/news", "A news post.")
    store = _Store(scored=[(other, 0.4)], stored=[offering])
    docs = retrieve_and_rank(
        "where can I give",
        store,
        {"https://grace.example/offerings", "https://grace.example/blog/news"},
        church_id="grace",
        profile=grace.retrieval,
    )
    assert any(doc.metadata["source"].endswith("/offerings") for doc in docs)


def test_service_times_prefer_campus_pages_over_the_locations_index():
    intent = next(item for item in DEFAULT_RETRIEVAL.intents if item.prefer_specific)
    urls = urls_for_intent(
        {
            "https://heritagechurch.com",
            "https://heritagechurch.com/locations",
            "https://heritagechurch.com/contact",
            "https://heritagechurch.com/visit",
            "https://heritagechurch.com/locations/sterling-heights",
            "https://heritagechurch.com/locations/stoney-creek",
            "https://heritagechurch.com/locations/imlay-city",
        },
        intent,
    )
    assert set(urls[:3]) == {
        "https://heritagechurch.com/locations/sterling-heights",
        "https://heritagechurch.com/locations/stoney-creek",
        "https://heritagechurch.com/locations/imlay-city",
    }


def test_service_time_chunk_beats_a_longer_events_chunk():
    times = _doc(
        "https://heritagechurch.com/locations/stoney-creek",
        "Service Times\nSundays\n9:30 am\n11 am",
    )
    events = _doc(
        "https://heritagechurch.com/locations/stoney-creek",
        "Upcoming events " + ("calendar item " * 80),
    )
    store = _Store(scored=[], stored=[events, times])
    docs = retrieve_and_rank(
        "What are your service times?",
        store,
        {"https://heritagechurch.com/locations/stoney-creek"},
        church_id="heritage",
        profile=DEFAULT_RETRIEVAL,
    )
    assert "9:30 am" in docs[0].page_content


def test_heritage_team_rule_is_specific():
    heritage = load_registry()["heritage"]
    team = next(intent for intent in heritage.retrieval.intents if "/team" in intent.paths)
    assert "who" not in team.any_terms
    assert "pastor" in team.any_terms
