"""Configuration constants for Chopper.

This module centralizes all configuration constants, magic strings,
and default values used throughout the Chopper application.
"""

from typing import NamedTuple

# File extension constants
CHOPPER_FILE_EXTENSION = ".chopper.html"

# Configuration search settings
MAX_CONFIG_SEARCH_DEPTH = 5
CONFIG_FILE_NAMES = [
    ".chopper",
    "chopper.conf",
    ".env.chopper",
    ".env",
]

# File size limits (10MB default)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


class Comment(NamedTuple):
    """Comment style definition with opening and closing markers."""

    open: str
    close: str


# Client-side comment styles (for files that run in browser)
COMMENT_CLIENT_STYLES = {
    "php": Comment("<!-- ", " -->"),
    "html": Comment("<!-- ", " -->"),
    "antlers": Comment("<!-- ", " -->"),
    "twig": Comment("<!-- ", " -->"),
    "js": Comment("// ", ""),
    "mjs": Comment("// ", ""),
    "ts": Comment("// ", ""),
    "tsx": Comment("// ", ""),
    "jsx": Comment("// ", ""),
    "css": Comment("/* ", " */"),
    "scss": Comment("/* ", " */"),
    "json": Comment("", ""),
    "none": Comment("", ""),
}

# Server-side comment styles (for template engines)
COMMENT_SERVER_STYLES = {
    "php": Comment("/* ", " */"),
    "html": Comment("{# ", " #}"),
    "antlers": Comment("{{# ", " #}}"),
    "twig": Comment("{# ", " #}"),
    "js": Comment("// ", ""),
    "ts": Comment("// ", ""),
    "tsx": Comment("// ", ""),
    "jsx": Comment("// ", ""),
    "css": Comment("/* ", " */"),
    "scss": Comment("/* ", " */"),
    "json": Comment("", ""),
    "none": Comment("", ""),
}


def parse_comment_overrides(value: str) -> dict[str, "Comment"]:
    """Parse a CHOPPER_COMMENT_STYLE_OVERRIDE string.

    Format: "type:open,close;type:open,close;"
    Example: "php:{{#,#}};css://,;"
    """
    overrides: dict[str, Comment] = {}
    for entry in value.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        type_part, _, style_spec = entry.partition(":")
        open_marker, _, close_marker = style_spec.partition(",")
        overrides[type_part.strip()] = Comment(open_marker, close_marker)
    return overrides


# Tree output symbols
TREE_BRANCH = "├─ "
TREE_LAST = "└─ "
TREE_PIPE = "┆ "
