# Sproki Backend

## Setup

```bash
pyenv shell 3.10.13   # eller din 3.10.x
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
