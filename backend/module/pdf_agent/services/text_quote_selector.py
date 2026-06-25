"""W3C Web Annotation TextQuoteSelector — anchor bằng quote+context (PLAN §7 Phase 5).

Annotation không neo bằng offset số tuyệt đối — exact/prefix/suffix cho phép
"refind" đúng vị trí dù text trước/sau đã bị user sửa.
"""

from __future__ import annotations

import re

from backend.config import get_settings
from backend.module.pdf_agent.graph.state import TextQuoteSelector


def build_anchor(full_text: str, start: int, end: int, context_chars: int | None = None) -> TextQuoteSelector:
    n = context_chars if context_chars is not None else get_settings().pdf_agent_anchor_context_chars
    return {
        "exact": full_text[start:end],
        "prefix": full_text[max(0, start - n):start],
        "suffix": full_text[end:end + n],
    }


def refind_anchor(current_text: str, anchor: TextQuoteSelector) -> int | None:
    """Trả offset hiện tại của anchor['exact'] trong current_text.

    Disambiguated bởi prefix/suffix nếu exact lặp lại nhiều nơi. None nếu
    không còn tồn tại (user đã tự sửa đúng đoạn đó) — caller nên ẩn
    annotation thay vì báo lỗi.
    """
    exact = anchor.get("exact", "")
    if not exact:
        return None

    candidates = [m.start() for m in re.finditer(re.escape(exact), current_text)]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    prefix = anchor.get("prefix", "")
    suffix = anchor.get("suffix", "")
    for pos in candidates:
        prefix_ok = current_text[max(0, pos - len(prefix)):pos].endswith(prefix[-32:]) if prefix else True
        end = pos + len(exact)
        suffix_ok = current_text[end:end + len(suffix)].startswith(suffix[:32]) if suffix else True
        if prefix_ok and suffix_ok:
            return pos

    # No disambiguation matched — ambiguous, treat as not-found rather than guess wrong.
    return None
