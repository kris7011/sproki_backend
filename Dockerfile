FROM python:3.10-slim

# Systempakker inkl. Tesseract (med dansk sprogdata) til OCR fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libc6-dev libffi-dev \
    libjpeg62-turbo-dev zlib1g-dev \
    tesseract-ocr tesseract-ocr-dan \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installer Python afhængigheder først (bedre layer cache)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Kopiér resten af appen
COPY . /app

# Render mounter /data først ved runtime, så vi sikrer mappen i appen (main.py)
# (ingen mkdir her – det håndteres i koden via os.makedirs)

# Eksponér en port (ikke strengt nødvendig, men informativ)
EXPOSE 8080

# VIGTIGT: Brug Render's PORT env — IKKE hardcode 8080
CMD ["bash", "-c", "uvicorn api.main:app --host 0.0.0.0 --port $PORT"]
