import asyncio
from datetime import datetime, timezone
from models import async_session
from logger import logger
from exporter.export_utils import export_data, generate_manifest, ensure_daily_folder, get_companies_for_today, init_daily_errors_file
import os

async def main():
    start_time = datetime.now(timezone.utc)
    output_dir = ensure_daily_folder(state="NY", base_dir="/scraper_data")

    async with async_session() as session:
        all_companies = await get_companies_for_today(session=session, state="NY")
        export_data(all_companies, output_dir)

    await generate_manifest(
        companies=all_companies,
        output_dir=output_dir,
        crawl_errors=get_crawl_errors(),  
        start_time=start_time
    )

    logger.info("Daily export finished for %s companies", len(all_companies))

def get_crawl_errors():
    TEMP_ERRORS_FILE = init_daily_errors_file(state="NY", base_dir="/tmp")

    if os.path.exists(TEMP_ERRORS_FILE):
        with open(TEMP_ERRORS_FILE) as f:
            try:
                return int(f.read().strip())
            except Exception:
                return 0
    return 0

if __name__ == "__main__":
    asyncio.run(main())
