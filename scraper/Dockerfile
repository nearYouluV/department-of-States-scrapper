FROM python:3.11-slim

WORKDIR /app

COPY scraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get upgrade -y && apt-get clean
RUN apt-get update \
    && apt-get install -y curl procps \
    && apt-get upgrade -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY scraper/ ./scraper/
COPY exporter/ ./exporter/
COPY models/ ./models/
COPY logger.py ./logger.py
COPY healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod +x /usr/local/bin/healthcheck.sh

# Create logs directory
RUN mkdir -p /app/logs

ENV PYTHONUNBUFFERED=1

# Use the runner script instead of directly running the scraper
CMD ["python", "-m", "scraper.scraper_runner"]