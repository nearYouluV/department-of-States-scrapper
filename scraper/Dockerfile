FROM python:3.11-slim

WORKDIR /app

# копіюємо requirements та встановлюємо
COPY scraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get upgrade -y && apt-get clean
# копіюємо весь код scraper та models
COPY scraper/ ./scraper/
COPY models/ ./models/
COPY logger.py ./logger.py

# встановлюємо змінну, щоб логи одразу були виведені у консоль
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "scraper.new_york_scrapper"]