"""Unit tests for link validation."""
from link_utils import validate_and_fix_links


def test_keeps_valid_link():
    valid = {"https://heritagechurch.com/give"}
    text = "Please [Give](https://heritagechurch.com/give) online."
    out = validate_and_fix_links(text, valid, "https://heritagechurch.com/contact", "https://heritagechurch.com")
    assert "https://heritagechurch.com/give" in out


def test_rewrites_hallucinated_link_to_fallback():
    valid = {"https://heritagechurch.com/contact"}
    text = "See the [Secret Page](https://heritagechurch.com/totally-fake)."
    out = validate_and_fix_links(text, valid, "https://heritagechurch.com/contact", "https://heritagechurch.com")
    assert "totally-fake" not in out
    assert "https://heritagechurch.com/contact" in out


def test_keyword_fallback_for_giving():
    valid = {"https://heritagechurch.com/giving"}
    text = "Support us via [Donate](https://heritagechurch.com/tithe-now)."
    out = validate_and_fix_links(text, valid, "https://heritagechurch.com/contact", "https://heritagechurch.com")
    assert "https://heritagechurch.com/giving" in out
