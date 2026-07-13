# Arranque local: solo observa app/ (no .venv) para evitar reloads basura.
python -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000
