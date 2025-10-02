from itertools import product
from datetime import datetime, timezone, date
import aiohttp
from logger import logger
from asyncio import Semaphore
import asyncio
from aiohttp import ContentTypeError, ClientError
import json
import random
from models import Company, async_session
from sqlalchemy.dialects.postgresql import insert
import pathlib
from exporter import init_daily_errors_file
TEMP_ERRORS_FILE = init_daily_errors_file(state="NY", base_dir="/tmp")

alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 &()-'./")
def generate_prefixes():
    for combo in product(alphabet, repeat=3):
        yield ''.join(combo)
PREFIXES = list(generate_prefixes())

# ---------------- Helpers ----------------
def safe_get(d: dict, *keys, default=None):
    cur = d
    try:
        for k in keys:
            if cur is None:
                return default
            cur = cur.get(k) if isinstance(cur, dict) else None
        return cur if cur is not None else default
    except Exception:
        return default

def parse_date(s):
    if not s:
        return None
    try:
        # якщо вже date/datetime — повертаємо date()
        if isinstance(s, datetime):
            return s.date()
        # strip milliseconds/Z якщо треба
        return datetime.fromisoformat(s.replace('Z', '+00:00')).date()
    except Exception:
        # остання спроба — короткі формати
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
    return None

def load_error_count() -> int:
    if TEMP_ERRORS_FILE.exists():
        try:
            return int(TEMP_ERRORS_FILE.read_text())
        except Exception:
            return 0
    return 0

def save_error_count(count: int):
    TEMP_ERRORS_FILE.write_text(str(count))

def reset_error_count():
    if TEMP_ERRORS_FILE.exists():
        TEMP_ERRORS_FILE.unlink()

        
async def post_json(
    session: aiohttp.ClientSession,
    url: str,
    json_data: dict,
    max_retries: int = 4,
    base_backoff: float = 0.5,
    timeout: float = 20.0,
    headers=None,
    cookies=None,
    semaphore: Semaphore = Semaphore(10)
) -> dict | list:
    """
    Robust POST + JSON parser with retries, exponential backoff, and semaphore limiting.
    Raises ClientError if permanently failed.
    """
    attempt = 0
    while attempt < max_retries:
        try:
            async with semaphore:
                async with session.post(url, json=json_data, headers=headers, cookies=cookies, timeout=timeout) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        logger.warning(
                            "Bad status %s for %s (attempt %d). Body starts: %.200s",
                            resp.status, url, attempt + 1, text
                        )
                        # Retry only on server errors (5xx)
                        if 500 <= resp.status < 600:

                            raise ClientError(f"Server error {resp.status}")
                        # For 4xx or other codes, fail immediately
                        raise ClientError(f"Non-retriable status {resp.status}")

                    # Parse JSON robustly
                    try:
                        data = await resp.json()
                        if not isinstance(data, (dict, list)):
                            raise ClientError("Response is not dict/list")
                        return data
                    except ContentTypeError:
                        # Fallback if content-type is wrong
                        try:
                            data = json.loads(text)
                            if not isinstance(data, (dict, list)):
                                raise ClientError("Response is not dict/list")
                            return data
                        except Exception:
                            raise ClientError("Invalid JSON body")
        except (ClientError, asyncio.TimeoutError, aiohttp.ServerTimeoutError) as e:
            attempt += 1
            if attempt < max_retries:
                backoff = base_backoff * (2 ** (attempt - 1)) + random.uniform(0, 0.3)
                logger.warning(
                    "Request error to %s: %s — retry %d/%d after %.2fs",
                    url, e, attempt, max_retries, backoff
                )
                await asyncio.sleep(backoff)
            else:
                logger.error("Giving up on %s after %d attempts", url, max_retries)
                current_errors = load_error_count()
                save_error_count(current_errors + 1)
                raise ClientError("Max retries exceeded")
        except Exception as e:
            logger.exception("Unexpected error while POSTing to %s: %s", url, e)
            current_errors = load_error_count()
            save_error_count(current_errors + 1)
            raise ClientError(f"Unexpected error: {e}")


def to_utc(dt):
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    if isinstance(dt, date):
        return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    if isinstance(dt, str):
        try:
            parsed = datetime.fromisoformat(dt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None
    return None


def make_aware(dt):
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if isinstance(dt, str):
        try:
            parsed = datetime.fromisoformat(dt)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None



# ---------------- DB persistence ----------------
async def persist_companies(companies):
    """
    Batched insert using postgres ON CONFLICT DO NOTHING.
    companies: list of Company-like objects or dicts
    """
    rows = []
    for c in companies:
        if c is None:
            continue
        rows.append({
            'source_state': getattr(c, 'source_state', None),
            'entity_number': getattr(c, 'entity_number', None),
            'entity_name': getattr(c, 'entity_name', None),
            'entity_type': getattr(c, 'entity_type', None),
            'entity_subtype': getattr(c, 'entity_subtype', None),
            'status': getattr(c, 'status', None),
            'registration_date': getattr(c, 'registration_date', None),
            'last_filing_date': getattr(c, 'last_filing_date', None),
            'expiration_date': getattr(c, 'expiration_date', None),
            'jurisdiction': getattr(c, 'jurisdiction', None),
            'principal_street': getattr(c, 'principal_street', None),
            'principal_city': getattr(c, 'principal_city', None),
            'principal_state': getattr(c, 'principal_state', None),
            'principal_postal_code': getattr(c, 'principal_postal_code', None),
            'principal_country': getattr(c, 'principal_country', None),
            'mailing_street': getattr(c, 'mailing_street', None),
            'mailing_city': getattr(c, 'mailing_city', None),
            'mailing_state': getattr(c, 'mailing_state', None),
            'mailing_postal_code': getattr(c, 'mailing_postal_code', None),
            'mailing_country': getattr(c, 'mailing_country', None),
            'agent_name': getattr(c, 'agent_name', None),
            'agent_street': getattr(c, 'agent_street', None),
            'agent_city': getattr(c, 'agent_city', None),
            'agent_state': getattr(c, 'agent_state', None),
            'agent_postal_code': getattr(c, 'agent_postal_code', None),
            'agent_country': getattr(c, 'agent_country', None),
            'incorporator_name': getattr(c, 'incorporator_name', None),
            'previous_names': getattr(c, 'previous_names', None),
            'source_detail_url': getattr(c, 'source_detail_url', None),
            'source_last_seen_at': getattr(c, 'source_last_seen_at', None),
        })
    if not rows:
        return
    stmt = insert(Company).on_conflict_do_nothing(index_elements=['entity_number'])
    async with async_session() as session:
        async with session.begin():
            # pass rows as params for bulk insert
            await session.execute(stmt, rows)
    logger.info("Persisted %d companies (duplicates skipped).", len(rows))
