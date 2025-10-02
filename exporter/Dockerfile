FROM python:3.11-slim

WORKDIR /app

COPY exporter/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY exporter/ ./exporter/
COPY models/ ./models/
COPY logger.py ./logger.py

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "exporter.daily_export"]


