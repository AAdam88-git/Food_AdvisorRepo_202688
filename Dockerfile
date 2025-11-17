# ── Dockerfile (repo‑root) ───────────────────────────────────────
FROM python:3.11-slim

WORKDIR /srv

# 1️⃣ Install dependencies
COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 2️⃣ Copy the single‑file app
COPY backend/app.py .

# 3️⃣ Port that Railway will override (default to 8000 if omitted)
ENV PORT 8000
EXPOSE $PORT

# ── <– this is the critical change! ───────────────────────────────
# Run the app via a shell so $PORT gets expanded at runtime
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:$PORT app:app"]
