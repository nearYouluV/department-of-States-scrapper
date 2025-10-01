# ---- Base image ----
FROM python:3.11-slim

# ---- Set workdir ----
WORKDIR /app

# ---- Copy requirements ----
COPY requirements.txt .

# ---- Install dependencies ----
RUN pip install --no-cache-dir -r requirements.txt

# ---- Copy exporter code ----
COPY exporter/ ./exporter/
# Якщо потрібно доступ до моделей/скрейпера:
COPY scraper/models.py ./scraper/models.py
COPY scraper/utils.py ./scraper/utils.py

# ---- Set environment variables ----
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ---- Entrypoint ----
# Запускає щоденний експорт
ENTRYPOINT ["python", "-m", "exporter.daily_export"]
