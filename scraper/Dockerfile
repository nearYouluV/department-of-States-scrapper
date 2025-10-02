FROM python:3.11-slim

WORKDIR /app

COPY scraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get upgrade -y && apt-get clean


COPY scraper/ ./scraper/
COPY exporter/ ./exporter/
COPY models/ ./models/
COPY logger.py ./logger.py
COPY healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod +x /usr/local/bin/healthcheck.sh
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "scraper.new_york_scrapper"]