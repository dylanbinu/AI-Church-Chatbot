"""Unit tests for context building."""
from context_manager import build_context, is_useful_page


def test_is_useful_page_filters_404():
    assert not is_useful_page("404 page not found")
    assert is_useful_page("Join us Sundays at 9am for worship and community with our church family.")


def test_build_context_uses_registry_keyword():
    records = [
        {
            "source": "https://church.com/locations/imlay-city",
            "content": "Campus details and service times every Sunday morning with kids ministry available.",
        },
        {
            "source": "https://church.com/give",
            "content": "Give online or in person this weekend through our secure giving portal.",
        },
    ]
    ctx = build_context(records, preferred_keyword=None)
    assert ctx.preferred_keyword is None
    assert "https://church.com/give" in ctx.valid_urls
    assert ctx.main_domain == "https://church.com"
