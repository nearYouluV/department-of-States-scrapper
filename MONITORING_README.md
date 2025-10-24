# Scraper Monitoring and Auto-Restart Setup

## Проблема
Контейнер скрейпера інколи "зависає" і перестає працювати, не падаючи з помилкою.

## Рішення

### 1. Покращений Health Check
- Перевіряє не тільки зовнішнє API, але й стан процесу Python
- Моніторить активність логів
- Перевіряє підключення до бази даних
- Визначає чи потрібен перезапуск на новий день

### 2. Scraper Runner (Wrapper)
- Постійно працюючий wrapper навколо основного скрейпера
- Автоматично перезапускає скрейпер у разі помилок
- Моніторить використання пам'яті
- Ведет облік успішних/неуспішних запусків
- Підтримує graceful shutdown

### 3. Конфігурація через Environment Variables

```bash
# .env файл
SCRAPER_AUTO_RESTART=true
SCRAPER_MAX_MEMORY_MB=2048
SCRAPER_RESTART_ON_FAILURE=true
SCRAPER_DAILY_RESTART=true
HEALTHCHECK_INTERVAL=300
HEALTHCHECK_TIMEOUT=30
HEALTHCHECK_RETRIES=3
ENABLE_PROCESS_MONITORING=true
LOG_ACTIVITY_TIMEOUT=1800
```

### 4. Зовнішній Моніторинг
Скрипт `monitor_scraper.sh` для запуску через cron:

```bash
# Додати в crontab для перевірки кожні 15 хвилин
*/15 * * * * /path/to/monitor_scraper.sh
```

## Як використовувати

### 1. Перебудуйте контейнер:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### 2. Перевірте логи:
```bash
# Основні логи контейнера
docker logs -f scraper_app

# Логи runner'а
docker exec scraper_app tail -f /app/logs/runner.log
```

### 3. Перевірте health check:
```bash
docker inspect scraper_app | grep Health -A 10
```

### 4. Налаштуйте зовнішній моніторинг:
```bash
# Зробіть скрипт виконуваним
chmod +x monitor_scraper.sh

# Додайте в crontab
crontab -e
# Додайте рядок:
*/15 * * * * /home/near_you_luv/work/Riley/monitor_scraper.sh
```

## Особливості

### Health Check
- **Interval**: 5 хвилин (замість 2)
- **Timeout**: 30 секунд (замість 10)
- **Start Period**: 30 секунд
- Перевіряє процес Python, активність логів, API та базу даних

### Memory Management
- Встановлено ліміти пам'яті в docker-compose
- Runner моніторить використання пам'яті
- Автоматичний перезапуск при перевищенні лімітів

### Restart Policies
- **restart: unless-stopped** - автоматичний перезапуск контейнера
- Runner автоматично перезапускає процес скрейпера
- Налаштування через environment variables

### Logging
- Окремі логи для runner'а
- Структуроване логування з timestamps
- Логи зберігаються в змонтованому volume

## Troubleshooting

### Контейнер не стартує:
```bash
docker logs scraper_app
```

### Health check fails:
```bash
docker exec scraper_app /usr/local/bin/healthcheck.sh
```

### Перевірити runner:
```bash
docker exec scraper_app ps aux | grep python
```

### Примусовий перезапуск:
```bash
docker restart scraper_app
```

### Очистити completion markers:
```bash
docker exec scraper_app rm -f /tmp/scraper_completed_*
```
