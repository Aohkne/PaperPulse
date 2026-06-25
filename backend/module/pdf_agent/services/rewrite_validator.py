"""Exact-match guard before applying a Step P5 "Viết lại" patch (PLAN §7 Phase 7).

Same pattern as IDE diff-apply tools (Cursor/Copilot/Claude Code Edit tool):
the LLM's `old_text` must match the buffer verbatim at apply time, otherwise
the user edited that spot since they selected it and we must refuse rather
than silently overwrite the wrong text.
"""

from __future__ import annotations


def validate(old_text: str, current_doc: str) -> bool:
    return bool(old_text) and old_text in current_doc


def apply_patch(current_doc: str, old_text: str, new_text: str) -> str:
    """Replace the FIRST occurrence of old_text only — call validate() first.

    If old_text could appear more than once, callers should resolve the exact
    occurrence via the selection's TextQuoteSelector offset before calling this
    (PLAN §9 Rủi ro) rather than relying on `str.replace(..., 1)` blindly.
    """
    return current_doc.replace(old_text, new_text, 1)
