# exporter/daily_export.py
import asyncio
from datetime import datetime, timezone
from models import Company, async_session
from logger import logger
from exporter.export_utils import export_data, generate_manifest, ensure_daily_folder
import os

async def main():
    start_time = datetime.now(timezone.utc)
    output_dir = ensure_daily_folder(state="NY")  # автоматично YYYY/MM/DD

    async with async_session() as session:
        # Отримуємо всі компанії за сьогоднішній день
        result = await session.execute(
            """
            SELECT * FROM companies
            WHERE source_state = 'NY'
            AND DATE(source_last_seen_at) = CURRENT_DATE
            """
        )
        all_companies = result.scalars().all()

    # Експортуємо CSV та NDJSON
    export_data(all_companies, output_dir)

    # Створюємо manifest.json
    generate_manifest(
        companies=all_companies,
        output_dir=output_dir,
        crawl_errors=get_crawl_errors(),  # тут підключаємо логіку помилок через tmp файл
        start_time=start_time
    )

    logger.info("Daily export finished for %s companies", len(all_companies))

def get_crawl_errors():
    """Зчитуємо тимчасовий файл з помилками контейнера"""
    tmp_file = "/tmp/crawl_errors.txt"
    if os.path.exists(tmp_file):
        with open(tmp_file) as f:
            try:
                return int(f.read().strip())
            except Exception:
                return 0
    return 0

if __name__ == "__main__":
    asyncio.run(main())
