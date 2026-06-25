"""Shared helpers for building/escaping LaTeX source from plain text."""

from __future__ import annotations

_ESCAPE_MAP = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(text: str) -> str:
    """Escape LaTeX-special characters in plain text before embedding it in a .tex document."""
    if not text:
        return ""
    return "".join(_ESCAPE_MAP.get(ch, ch) for ch in text)


# Longest tokens first so e.g. "\textbackslash{}" is consumed whole before any
# shorter token could spuriously match a substring of it.
_UNESCAPE_ORDER = [
    (r"\textasciitilde{}", "~"),
    (r"\textasciicircum{}", "^"),
    (r"\textbackslash{}", "\\"),
    (r"\&", "&"),
    (r"\%", "%"),
    (r"\$", "$"),
    (r"\#", "#"),
    (r"\_", "_"),
    (r"\{", "{"),
    (r"\}", "}"),
]


def unescape_latex(text: str) -> str:
    """Reverse `escape_latex` — used when converting stored LaTeX prose back to plain text."""
    if not text:
        return ""
    for token, plain in _UNESCAPE_ORDER:
        text = text.replace(token, plain)
    return text
