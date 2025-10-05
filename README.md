# Sproki Backend

En lille FastAPI-backend til at gemme rapporter og generere træningsplaner – inkl. PDF-upload, **OCR fallback** for scannede PDF’er og fil-lagring på disk.

## Endpoints (kort)

- `GET /` → ping
- `GET /health` → `{ "ok": true }`
- `POST /children/{child_id}` → opret/opdatér barn
- `POST /children/{child_id}/reports` → gem rapport (JSON: scores + ageMonths)
- `POST /children/{child_id}/analyze` → opret + analyzér i ét kald
- `GET /children/{child_id}/plan` → seneste plan
- `GET /children/{child_id}/reports` → historik
- `GET /children/{child_id}/reports/{report_id}` → enkelt rapport
- `POST /children/{child_id}/reports/upload` → **multipart** upload: `file=<pdf>`, valgfrit `ageMonths`, `name`

## Kør lokalt

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="sqlite:///./sproki_reports.db"
export UPLOAD_DIR="./uploads"
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
