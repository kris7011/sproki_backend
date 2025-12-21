# Sproki Backend

FastAPI-backend til Sproki: rapporter, øvelser, forældre-overblik, m.m.

## Endpoints (kort)

- `GET /docs` – Swagger UI
- `GET /health` – `{ "ok": true }`

### Reports

- `POST /reports/{child_id}` – upload rapport (body: `{ age_years, age_months, items: [{category, score}] }`)
- `GET  /reports/{child_id}/latest` – seneste pr. kategori (zone, points_to_green, mm.)

### Exercises

- `GET  /exercises` – liste aktive øvelser (valgfri `?category=...`)
- `GET  /exercises/for-child/{child_id}` – anbefalede øvelser baseret på seneste rapport/zone
- `POST /exercises/{exercise_id}/attempts` – log ét forsøg `{ child_id, correct }`
- `GET  /exercises/progression/{child_id}` – overblik (zone, points_to_green, accuracy)

### Parents

- `GET  /parents/{child_id}/overview` – “kort” pr. kategori (score/zone)

> Hvis du også bruger `ppr`/`institutions`, læg dem i en separat sektion.

## Første-gangs setup

```bash
pyenv local 3.10.13
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Flyt DB-modulet til api-pakken (engangskørsel)
mkdir -p api
# kun hvis filen findes i app/: mv app/db.py api/db.py
touch api/__init__.py

# .env (opret i projektroden)
cat > .env << 'ENV'
DATABASE_URL=sqlite:///./sproki_reports.db
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
EMAIL_FROM=noreply@sproki.app
SUPABASE_PROJECT_URL=https://icenwsoauzymexujrqoo.supabase.co
SUPABASE_JWKS_URL=https://icenwsoauzymexujrqoo.supabase.co/auth/v1/keys
SUPABASE_JWT_ISSUER=https://icenwsoauzymexujrqoo.supabase.co/auth/v1
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_ANON_KEY=sb_publishable_1NbDihrYplvqLX-MOrLiZA_4R6d55X9
REQUIRE_SUPABASE=0
ENV

# Start test miljø
source .venv/bin/activate
uvicorn api.main:app --reload
