import asyncio
from datetime import datetime, timedelta, timezone
import json
import aiohttp
from sqlalchemy import select
from config import PREFIXES, to_utc
from models import Company, async_session
import logging
MAX_CONCURRENT_REQUESTS = 25
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

cookies = {
    'TS00000000076': '084c043756ab2800bb5cf21272e2eba01bf08c47dc8ffa189ba90f426f0e1a925ce4a7cb80c50d5fa988de85bffaf92d084cde5f8e09d0008a4e669d39bf507b14e53dcf0c129365258b5ff33b4ad5e05a9206638a8276abfd9a4ccff6faa693a90e8709ba48897caf709fc93221a834b8071c8a3621d77356c9b3c9246873abbeaf4632b860f90c8d3224f5334575dfbf91a0e98ee91d2fa99ef362a6845183d024ad80ad766f4082d05dfbdced8092ba873e3f592c18188b7f3845822214db641e8c04c11e62f8ccd95edc1355a4235c583162f3cfc733fc85f7f28c5161853fe10c47c082735c74313a23257abfb2d9dc268cc1e8db43ef4438eb3de56e392c4e13f345e34968',
    'TSPD_101_DID': '084c043756ab2800bb5cf21272e2eba01bf08c47dc8ffa189ba90f426f0e1a925ce4a7cb80c50d5fa988de85bffaf92d084cde5f8e063800193be9166c79fe2bff02759deae06987bef09c14f17648cac8a69e0f166ac9379acec3d6613213b89033620a0537727c6f46ccbde5229f27',
    'TSPD_101': '084c043756ab280072da5475736bac09e042c5dea0f2d00280c773d2472e305e980e0e22a039720529639e4c38109bc208849e71c6051800cde0721b34993f3ddfa0af9ff479231cb5f81b2c69193ec5',
    'TS969a1eaa027': '084c043756ab2000b2da58ef5cc052f98cdebe6a52ad01fd40e39233b801ace962057d461aa40428088b85b8881130001d56c3b8c1313b22c9c62720d68ede263f236471ac3b15b0a63a4a8e61c7c511e126fe89e5ebe7b79555429bbb2adce1',
    'TSbb0d7d7a077': '084c043756ab2800b2f8ce31814603f24c814c1e0f609182c46008e72e6734c38ea626b85a010088f620043378df82c208f71aec9117200012c8fa86c7749007024918158e7f32b1183655e58a8f28cac31db0bdc6f957eb',
}

headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json;charset=UTF-8',
    'Origin': 'https://apps.dos.ny.gov',
    'Referer': 'https://apps.dos.ny.gov/publicInquiry/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
}


async def get_entities_data(session: aiohttp.ClientSession, prefix: str, semaphore: asyncio.Semaphore):
    json_data = {
        'searchValue': prefix,
        'searchByTypeIndicator': 'EntityName',
        'searchExpressionIndicator': 'CONTAINS',
        'entityStatusIndicator': 'AllStatuses',
        'entityTypeIndicator': ['Corporation','LimitedLiabilityCompany','LimitedPartnership','LimitedLiabilityPartnership'],
        'listPaginationInfo': {'listStartRecord': 1,'listEndRecord': 50},
    }
    logger.info(f"Fetching entities for prefix: {prefix}")

    async with semaphore:
        async with session.post(
            'https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetComplexSearchMatchingEntities',
            cookies=cookies,
            headers=headers,
            json=json_data
        ) as response:
            data = await response.json()
            entities = []

            try:
                entities = [
                    entity for entity in data.get('entitySearchResultList', [])
                    if entity.get("initialFilingDate") and
                    datetime.fromisoformat(entity["initialFilingDate"]).date() >= datetime.now().date() - timedelta(days=1)
                ]
                logger.info(f"Found {len(entities)} entities for prefix {prefix}")
                tasks = [get_detailed_entity_data(session, entity, semaphore) for entity in entities]
                await asyncio.gather(*tasks)
            except Exception as e:
                logger.error(f"Error fetching entities for prefix {prefix}: {e} trying again")
                retries = 3
                while retries > 0:
                    await asyncio.sleep(0.5)
                    async with session.post(
                        'https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetComplexSearchMatchingEntities',
                        cookies=cookies,
                        headers=headers,
                        json=json_data
                    ) as response:
                        data = await response.json()
                        if type(data) == str:
                            continue
                        try:
                            entities = [
                                entity for entity in data.get('entitySearchResultList', [])
                            ]
                        except:
                            continue
                        if entities:
                            entities = [
                                entity for entity in entities
                                if entity.get("initialFilingDate") and
                                datetime.fromisoformat(entity["initialFilingDate"]).date() >= datetime.now().date() - timedelta(days=1)
                            ]
                            logger.info(f"Found {len(entities)} entities for prefix {prefix} on retry")
                            tasks = [get_detailed_entity_data(session, entity, semaphore) for entity in entities]
                            await asyncio.gather(*tasks)
                    retries -= 1

                return []

async def get_detailed_entity_data(session: aiohttp.ClientSession, entity, semaphore: asyncio.Semaphore):
    async with semaphore:
        try:
            
            json_data = {'SearchID': entity['dosID'],'EntityName': entity['entityName'],'AssumedNameFlag': 'false'}
            async with session.post(
                'https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetEntityRecordByID',
                cookies=cookies,
            headers=headers,
            json=json_data
            ) as response:
                data = await response.json()

            company = Company(
                source_state='NY',
                entity_number=int(data['entityGeneralInfo']['dosID']),
                entity_name=data['entityGeneralInfo']['entityName'],
                entity_type=data['entityGeneralInfo']['entityType'],
                entity_subtype=data['entityGeneralInfo'].get('entitySubtype'),
                status=data['entityGeneralInfo'].get('entityStatus'),

                registration_date=datetime.fromisoformat(data['entityGeneralInfo']['dateOfInitialDosFiling']).date() if data['entityGeneralInfo']['dateOfInitialDosFiling'] else None,
                last_filing_date=datetime.fromisoformat(data['entityGeneralInfo']['nextStatementDueDate']).date() if data['entityGeneralInfo']['nextStatementDueDate'] else None,
                expiration_date=datetime.fromisoformat(data['entityGeneralInfo'].get('inactiveDate')).date() if data['entityGeneralInfo'].get('inactiveDate') else None,

                jurisdiction=data['entityGeneralInfo'].get('jurisdiction'),

                principal_street=data['sopAddress']['address']['streetAddress'],
                principal_city=data['sopAddress']['address']['city'],
                principal_state=data['sopAddress']['address']['state'],
                principal_postal_code=data['sopAddress']['address']['zipCode'],
                principal_country=data['sopAddress']['address']['country'],

                mailing_street=data['poExecAddress']['address']['streetAddress'],
                mailing_city=data['poExecAddress']['address']['city'],
                mailing_state=data['poExecAddress']['address']['state'],
                mailing_postal_code=data['poExecAddress']['address']['zipCode'],
                mailing_country=data['poExecAddress']['address']['country'],

                agent_name=data['registeredAgent'].get('name'),
                agent_street=data['registeredAgent']['address'].get('streetAddress'),
                agent_city=data['registeredAgent']['address'].get('city'),
                agent_state=data['registeredAgent']['address'].get('state'),
                agent_postal_code=data['registeredAgent']['address'].get('zipCode'),
                agent_country=data['registeredAgent']['address'].get('country'),

                incorporator_name=data['ceo'].get('name'),
                previous_names=[],
                source_detail_url='',
                source_last_seen_at=datetime.now(timezone.utc)
            )


            # get past names
            json_data = {
                'SearchID': entity['dosID'],
                'AssumedNameFlag': 'false',
                'ListSortedBy': 'ALL',
                'EntityName': entity['entityName'],
                'listPaginationInfo': {'listStartRecord': 1,'listEndRecord': 50},
            }
            async with session.post(
                'https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetNameHistoryByID',
                cookies=cookies,
                headers=headers,
                json=json_data
            ) as response:
                history_data = await response.json()
                company.previous_names = [name.get('entityName') for name in history_data.get('nameHistoryResultList', [])]

            logger.info(f"Prepared company data: {company.entity_name}")
            # return company
            await save_company_to_db(company)
        except Exception as e:
            logger.error(f"Error fetching detailed entity data: {e}")
            return None

from sqlalchemy.dialects.postgresql import insert

async def save_companies_to_db(companies):
    async with async_session() as session:
        async with session.begin():
            for company in companies:
                if company is None:
                    continue

                stmt = insert(Company).values(
                    source_state=company.source_state,
                    entity_number=company.entity_number,
                    entity_name=company.entity_name,
                    entity_type=company.entity_type,
                    entity_subtype=company.entity_subtype,
                    status=company.status,
                    registration_date=company.registration_date,
                    last_filing_date=company.last_filing_date,
                    expiration_date=company.expiration_date,
                    jurisdiction=company.jurisdiction,
                    principal_street=company.principal_street,
                    principal_city=company.principal_city,
                    principal_state=company.principal_state,
                    principal_postal_code=company.principal_postal_code,
                    principal_country=company.principal_country,
                    # ... інші поля
                ).on_conflict_do_nothing(
                    index_elements=['entity_number']  # унікальний індекс на entity_number
                )

                await session.execute(stmt)
    logger.info(f"Saved companies to DB (duplicates automatically skipped)")


async def save_company_to_db(company):
    async with async_session() as session:
        async with session.begin():
            stmt = insert(Company).values(
                source_state=company.source_state,
                entity_number=company.entity_number,
                entity_name=company.entity_name,
                entity_type=company.entity_type,
                entity_subtype=company.entity_subtype,
                status=company.status,
                registration_date=company.registration_date,
                last_filing_date=company.last_filing_date,
                expiration_date=company.expiration_date,
                jurisdiction=company.jurisdiction,
                principal_street=company.principal_street,
                principal_city=company.principal_city,
                principal_state=company.principal_state,
                principal_postal_code=company.principal_postal_code,
                principal_country=company.principal_country,
                # ... інші поля
            ).on_conflict_do_nothing(
                index_elements=['entity_number']  # унікальний індекс на entity_number
            )

            await session.execute(stmt)
    logger.info(f"Saved company to DB (duplicates automatically skipped): {company.entity_name}")


async def main():
    
    async with aiohttp.ClientSession() as session:
        tasks = [get_entities_data(session, prefix, semaphore) for prefix in PREFIXES]
        results = await asyncio.gather(*tasks)

        logger.info("All done!")

if __name__ == '__main__':
    asyncio.run(main())
