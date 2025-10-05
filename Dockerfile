FROM python:3.10-slim

# Systempakker inkl. Tesseract (med dansk sprogdata) til OCR fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libc6-dev libffi-dev libjpeg62-turbo-dev zlib1g-dev \
    tesseract-ocr tesseract-ocr-dan \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Sørg for at upload-mappen findes (Render disk mounts til /data)
RUN mkdir -p /data/uploads

EXPOSE 8080
ENV PORT=8080
ENV UPLOAD_DIR=/data/uploads

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
