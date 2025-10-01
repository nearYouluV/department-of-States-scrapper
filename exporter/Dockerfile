FROM python:3.11-slim

WORKDIR /app

# Скопіювати requirements
COPY exporter/requirements.txt .
# Встановити залежності
RUN pip install --no-cache-dir -r requirements.txt

# Скопіювати код
COPY exporter/ ./exporter/
COPY models/ ./models/
COPY logger.py ./logger.py

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "exporter.daily_export"]


