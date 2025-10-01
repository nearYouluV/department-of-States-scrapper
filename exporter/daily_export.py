# exporter/daily_export.py
import asyncio
from datetime import datetime, timezone
from sqlalchemy import text
from models import Company, async_session
from logger import logger
from exporter.export_utils import export_data, generate_manifest, ensure_daily_folder, get_companies_for_today
import os

async def main():
    start_time = datetime.now(timezone.utc)
    output_dir = ensure_daily_folder(state="NY", base_dir="/app/data")

    all_companies = await get_companies_for_today(session=async_session, state="NY")

    # Експортуємо CSV та NDJSON
    export_data(all_companies, output_dir)

    # Створюємо manifest.json
    await generate_manifest(
        companies=all_companies,
        output_dir=output_dir,
        crawl_errors=get_crawl_errors(),  # підключаємо логіку помилок через tmp файл
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
