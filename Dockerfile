
# Stage 1: Builder — cài đặt dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Cài build tools cần thiết cho compile C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml trước — tận dụng Docker layer caching
COPY pyproject.toml .

# Cài Python dependencies vào virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# KHÔNG cài torch/mineru ở production image (optimize_Plan.html §4) — backend
# chạy trên Google Cloud Run, image nhẹ giúp cold start nhanh hơn nhiều khi
# scale-to-zero. PDF Agent tự fallback sang PyMuPDF khi thiếu mineru binary
# (xem backend/module/pdf_agent/services/mineru_client.py is_available()).
# Muốn test MinerU thật → chạy local qua docker-compose.dev.yml (service `mineru`,
# build từ Dockerfile.mineru) + MINERU_MODE=http, không phải image này.
RUN pip install --no-cache-dir -e ".[dev]"

# Stage 2: Production — image cuối cùng
FROM python:3.11-slim AS production

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

WORKDIR /app

# texlive: pdflatex để compile bundle .tex của PDF Agent khi export PDF (Phase 3).
# (libgl1/libglib2.0-0/libgomp1 — runtime deps của OpenCV/PaddleOCR — đã bỏ cùng
# với MinerU, không còn dependency nào trong image này cần chúng.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base texlive-latex-extra \
    && rm -rf /var/lib/apt/lists/*

# Non-root user, có home dir (-m) — một số lib Python (HF cache, matplotlib config)
# vẫn muốn ghi vào $HOME dù không có MinerU.
RUN groupadd -r appuser && useradd -r -m -g appuser appuser

# Copy virtual environment từ builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy source code
COPY . .

# Tạo thư mục data và chown trước khi switch user
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Chuyển sang non-root user
USER appuser

EXPOSE 8000

# Health check — kiểm tra API còn sống
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Chạy ứng dụng với uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
