FROM python:3.10-slim

# System packages incl. Tesseract (with Danish language data) for OCR fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libc6-dev libffi-dev libjpeg62-turbo-dev zlib1g-dev \
    tesseract-ocr tesseract-ocr-dan \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && pip show python-multipart >/dev/null || pip install --no-cache-dir python-multipart

# Copy the app
COPY . /app

# Ensure upload directory exists (Render disk is mounted at /data)
RUN mkdir -p /data/uploads

EXPOSE 8080
ENV PORT=8080
ENV UPLOAD_DIR=/data/uploads

# On Render, DATABASE_URL is provided via render.yaml (sqlite on /data)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
