import asyncio
from datetime import datetime, timedelta, timezone, date
import aiohttp
from sqlalchemy import text
from scraper.utils import PREFIXES, load_error_count, parse_date, post_json, reset_error_count, safe_get, persist_companies
from models import Company, ScraperCheckpoint, async_session
from logger import logger
from dotenv import load_dotenv
import os
from models import Base, engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from exporter import get_companies_for_today, generate_manifest, ensure_daily_folder, export_data


load_dotenv()
MAX_CONCURRENT_REQUESTS = 8
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# cookies = {
#     "TS00000000076": os.getenv("API_COOKIE_TS00000000076"),
#     "TSPD_101_DID": os.getenv("API_COOKIE_TSPD_101_DID"),
#     "TSPD_101": os.getenv("API_COOKIE_TSPD_101"),
#     "TS969a1eaa027": os.getenv("API_COOKIE_TS969a1eaa027"),
#     "TSbb0d7d7a077": os.getenv("API_COOKIE_TSbb0d7d7a077"),
# }

headers = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru,en-US;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://apps.dos.ny.gov",
    "Referer": "https://apps.dos.ny.gov/publicInquiry/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
}


# ---------------- Main scraping logic ----------------
async def get_entities_data(session: aiohttp.ClientSession, prefix: str):
    json_data = {
        "searchValue": prefix,
        "searchByTypeIndicator": "EntityName",
        "searchExpressionIndicator": "CONTAINS",
        "entityStatusIndicator": "AllStatuses",
        "entityTypeIndicator": [
            "Corporation",
            "LimitedLiabilityCompany",
            "LimitedPartnership",
            "LimitedLiabilityPartnership",
        ],
        "listPaginationInfo": {"listStartRecord": 1, "listEndRecord": 50},
    }
    url = "https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetComplexSearchMatchingEntities"
    # data = await post_json(
    #     session, url, json_data, headers=headers, cookies=cookies, semaphore=semaphore, max_retries=8
    # )
    data = await post_json(
        session, url, json_data, headers=headers, semaphore=semaphore, max_retries=8
    )
    if not data:
        logger.warning("No data for prefix %s", prefix)
        return

    raw_list = data.get("entitySearchResultList") if isinstance(data, dict) else None
    if not raw_list:
        logger.info("Empty searchResultList for prefix %s", prefix)
        return

    # filter recent by initialFilingDate (>= yesterday)
    cutoff = datetime.now().date() - timedelta(days=1)
    entities = []
    for entity in raw_list:
        try:
            d = parse_date(entity.get("initialFilingDate"))
            if d and d >= cutoff:
                entities.append(entity)
        except Exception:
            continue

    logger.info("Found %d new-ish entities for prefix %s", len(entities), prefix)
    if not entities:
        return

    tasks = [
        asyncio.create_task(get_detailed_entity_data(session, ent)) for ent in entities
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # collect successful Company objects
    companies = [r for r in results if not isinstance(r, Exception) and r is not None]
    if companies:
        await persist_companies(companies)


async def get_detailed_entity_data(session: aiohttp.ClientSession, entity):
    try:
        json_data = {
            "SearchID": entity["dosID"],
            "EntityName": entity["entityName"],
            "AssumedNameFlag": "false",
        }
        url = "https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetEntityRecordByID"
        data = await post_json(session, url, json_data)
        if not data:
            logger.warning("No detail for dosID %s", entity.get("dosID"))
            return None

        # build Company-like object
        company = Company(
            source_state="NY",
            entity_number=int(safe_get(data, "entityGeneralInfo", "dosID") or 0),
            entity_name=safe_get(data, "entityGeneralInfo", "entityName"),
            entity_type=safe_get(data, "entityGeneralInfo", "entityType"),
            entity_subtype=safe_get(data, "entityGeneralInfo", "entitySubtype"),
            status=safe_get(data, "entityGeneralInfo", "entityStatus"),
            registration_date=parse_date(
                safe_get(data, "entityGeneralInfo", "dateOfInitialDosFiling")
            ),
            last_filing_date=parse_date(
                safe_get(data, "entityGeneralInfo", "nextStatementDueDate")
            ),
            expiration_date=parse_date(
                safe_get(data, "entityGeneralInfo", "inactiveDate")
            ),
            jurisdiction=safe_get(data, "entityGeneralInfo", "jurisdiction"),
            principal_street=safe_get(data, "sopAddress", "address", "streetAddress"),
            principal_city=safe_get(data, "sopAddress", "address", "city"),
            principal_state=safe_get(data, "sopAddress", "address", "state"),
            principal_postal_code=safe_get(data, "sopAddress", "address", "zipCode"),
            principal_country=safe_get(data, "sopAddress", "address", "country"),
            mailing_street=safe_get(data, "poExecAddress", "address", "streetAddress"),
            mailing_city=safe_get(data, "poExecAddress", "address", "city"),
            mailing_state=safe_get(data, "poExecAddress", "address", "state"),
            mailing_postal_code=safe_get(data, "poExecAddress", "address", "zipCode"),
            mailing_country=safe_get(data, "poExecAddress", "address", "country"),
            agent_name=safe_get(data, "registeredAgent", "name"),
            agent_street=safe_get(data, "registeredAgent", "address", "streetAddress"),
            agent_city=safe_get(data, "registeredAgent", "address", "city"),
            agent_state=safe_get(data, "registeredAgent", "address", "state"),
            agent_postal_code=safe_get(data, "registeredAgent", "address", "zipCode"),
            agent_country=safe_get(data, "registeredAgent", "address", "country"),
            incorporator_name=safe_get(data, "ceo", "name"),
            previous_names=[],
            source_detail_url="",
            source_last_seen_at=datetime.now(timezone.utc),
        )

        # name history
        json_data = {
            "SearchID": entity["dosID"],
            "AssumedNameFlag": "false",
            "ListSortedBy": "ALL",
            "EntityName": entity["entityName"],
            "listPaginationInfo": {"listStartRecord": 1, "listEndRecord": 50},
        }
        history = await post_json(
            session,
            "https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetNameHistoryByID",
            json_data,
        )
        if isinstance(history, dict):
            company.previous_names = [
                safe_get(n, "entityName")
                for n in history.get("nameHistoryResultList", [])
            ]

        logger.info("Prepared company: %s", company.entity_name)
        return company

    except Exception as e:
        logger.exception(
            "Error in get_detailed_entity_data for %s: %s", entity.get("dosID"), e
        )
        return None


async def load_checkpoint(session: AsyncSession):
    result = await session.execute(
        select(ScraperCheckpoint).where(
            ScraperCheckpoint.id == f"daily_{date.today()}_newyork"
        )
    )
    checkpoint = result.scalar_one_or_none()
    if checkpoint and checkpoint.updated_at == date.today():
        return checkpoint.last_prefix
    return None


async def save_checkpoint(session: AsyncSession, prefix: str):
    result = await session.execute(
        select(ScraperCheckpoint).where(
            ScraperCheckpoint.id == f"daily_{date.today()}_newyork"
        )
    )
    checkpoint = result.scalar_one_or_none()
    if checkpoint:
        checkpoint.last_prefix = prefix
        checkpoint.updated_at = date.today()
    else:
        checkpoint = ScraperCheckpoint(
            id=f"daily_{date.today()}_newyork",
            last_prefix=prefix,
            updated_at=date.today(),
        )
        session.add(checkpoint)
    await session.commit()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------------- Runner ----------------
async def main():
    start_time = datetime.now(timezone.utc)
    await init_db()
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session, async_session() as db:
        last_prefix = await load_checkpoint(db)
        start_index = 0
        if last_prefix and last_prefix in PREFIXES:
            start_index = PREFIXES.index(last_prefix) + 1
            logger.info("Resuming from prefix %s", last_prefix)

        async def sem_task(prefix):
            async with semaphore:
                await get_entities_data(session, prefix)
                await save_checkpoint(db, prefix)
        try:
            tasks = []
            for prefix in PREFIXES[start_index:]:
                tasks.append(asyncio.create_task(sem_task(prefix)))

            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error("Error occurred: %s", e)
            raise
    output_dir = ensure_daily_folder(state="NY")
    csv_file, ndjson_file = await asyncio.to_thread(export_data, all_companies, output_dir)
    all_companies = await get_companies_for_today(session=async_session, state="NY")
    crawl_errors = load_error_count()
    reset_error_count()
    await generate_manifest(all_companies=all_companies, crawl_errors=crawl_errors, start_time=start_time, output_dir=output_dir)
    logger.info("Daily export finished for %s companies", len(all_companies))
    # delete checkpoint after successful run
    async with async_session() as db:
        checkpoint_id = f"daily_{date.today()}_newyork"
        await db.execute(
            text("DELETE FROM scraper_checkpoints WHERE id = :id"),
            {"id": checkpoint_id},
        )
        await db.commit()

    logger.info("Scraping completed successfully, checkpoint cleared.")

if __name__ == "__main__":
    asyncio.run(main())
