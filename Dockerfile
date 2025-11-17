# Dockerfile (repo‑root)

# 0️⃣ Base image — minimal Python 3.11
FROM python:3.11-slim

# 1️⃣ Working directory inside the container
WORKDIR /srv

# 2️⃣ Install dependencies
COPY backend/requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 3️⃣ Copy the actual app code
COPY backend/app.py .

# 4️⃣ Optional: copy the seed script (only if you added it)
# COPY backend/seed_db.py .

# 5️⃣ Port that Railway sets via the $PORT env var
ENV PORT 8000
EXPOSE 8000

# 6️⃣ Run with Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:${PORT}", "app:app"]
