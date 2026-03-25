"""Unit tests for yaam.utils."""

from yaam.utils import sanitize_name


def test_sanitize_name_replaces_slash():
    assert sanitize_name("feat/my-feature") == "feat-my-feature"


def test_sanitize_name_replaces_all_unsafe_chars():
    assert sanitize_name(r'/\:*?"<>|') == "---------"


def test_sanitize_name_leaves_safe_string_unchanged():
    assert sanitize_name("plain-name") == "plain-name"
