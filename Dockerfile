
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

# Cài torch/torchvision bản CPU-only TRƯỚC — wheel mặc định của PyPI cho Linux luôn
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -e ".[dev,mineru]" six

# Stage 2: Production — image cuối cùng
FROM python:3.11-slim AS production

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000 \
    MINERU_DEVICE_MODE=cpu \
    MINERU_MODEL_SOURCE=huggingface

WORKDIR /app

# texlive: pdflatex để compile bundle .tex của PDF Agent khi export PDF (Phase 3)
# libgl1/libglib2.0-0/libgomp1: runtime deps của OpenCV/PaddleOCR (MinerU pipeline backend)
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base texlive-latex-extra \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Tạo non-root user CÓ home dir (-m) — mineru-models-download cần ghi cache/config
# (mineru.json) vào $HOME, phải chạy đúng dưới appuser để tránh lệch quyền sở hữu
# nếu chạy lúc còn là root.
RUN groupadd -r appuser && useradd -r -m -g appuser appuser

# Copy virtual environment từ builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy source code
COPY . .

# Tạo thư mục data và chown trước khi switch user
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Chuyển sang non-root user
USER appuser

RUN mineru-models-download -s huggingface -m pipeline

EXPOSE 8000

# Health check — kiểm tra API còn sống
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Chạy ứng dụng với uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
