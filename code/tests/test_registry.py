"""Unit tests for church registry."""
from pathlib import Path

import pytest

from registry import UnknownChurchError, get_church, list_church_ids, load_registry


def test_heritage_registered():
    churches = load_registry()
    assert "heritage" in churches
    assert "example" not in churches
    heritage = get_church("heritage")
    assert heritage.domain == "heritagechurch.com"
    assert heritage.start_url.startswith("https://")


def test_unknown_church():
    with pytest.raises(UnknownChurchError):
        get_church("not-a-real-church")


def test_list_ids_sorted():
    ids = list_church_ids()
    assert ids == sorted(ids)
