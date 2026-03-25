import re

_UNSAFE = re.compile(r'[/\\:*?"<>|]')


def sanitize_name(s: str) -> str:
    """Replace filesystem-unsafe characters with hyphens."""
    return _UNSAFE.sub("-", s)
