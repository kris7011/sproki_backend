# Sproki Backend

En lille FastAPI-backend til at gemme rapporter og generere træningsplaner – inkl. PDF-upload og simpel analyse.

## Endpoints (kort)

- `GET /` → ping (tekst)
- `GET /health` → `{ "ok": true }`
- `POST /children/{child_id}` → opret/opdatér barn
- `POST /children/{child_id}/reports` → gem rapport (scores + ageMonths)
- `GET /children/{child_id}/plan` → hent plan for seneste rapport
- `POST /children/{child_id}/analyze` → opret + analyzér i ét kald
- `POST /children/{child_id}/reports/upload` (form-data: `file=<pdf>`) → parse PDF og gem
- `GET /children/{child_id}/reports` → list historik (NY)
- `GET /children/{child_id}/reports/{report_id}` → hent specifik rapport (NY)

## Kør lokalt

```bash
pyenv shell 3.10.13        # eller en anden 3.10.x
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Lokal DB (SQLite-fil i projektmappen)
export DATABASE_URL="sqlite:///./sproki_reports.db"

uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
