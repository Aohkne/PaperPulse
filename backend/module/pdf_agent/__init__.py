"""PDF Agent — module độc lập (pdf-agent_PLAN_2.0.md).

Nhận PDF/.tex/.tex_bundle do user upload, parse thành .tex editable,
chạy critic + citation verification + link check song song, build
annotation store (suggest/warning), cho user accept/reject/dismiss/
explain/rewrite, rồi lưu vào bảng `reviews` đã có.

KHÔNG sửa `backend/module/research_agent/` — chỉ import service functions
từ đó (semantic_scholar/openalex/arxiv_search) ở mode "lookup 1 paper".
"""
