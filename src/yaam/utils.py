"""Shared utilities for yaam.

``sanitize_name`` output is the canonical internal session key used as the
store key, tmux session name, and for all internal lookups.  The original
unsanitized name is preserved as ``AgentSession.display_name`` for display
purposes only.
"""

import re

_UNSAFE = re.compile(r'[/\\:*?"<>|]')


def sanitize_name(s: str) -> str:
    """Replace filesystem-unsafe characters with hyphens.

    The return value is the canonical internal session key — it is used as the
    ``AgentSession.key``, the tmux session name, and the ``SessionStore`` dict
    key.  Two names that differ only in unsafe characters (e.g. ``my/feature``
    and ``my-feature``) produce the same key and are therefore treated as the
    same session.
    """
    return _UNSAFE.sub("-", s)
