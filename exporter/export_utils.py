from pathlib import Path
from datetime import datetime, timezone
import json
import hashlib
from typing import List
import pandas as pd
from models import Company
from logger import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

async def get_companies_for_today(session: AsyncSession, state: str = "NY") -> List[dict]:
    """
    """
    query = text("""
        SELECT * FROM companies
        WHERE source_state = :state
        AND DATE(source_last_seen_at) = CURRENT_DATE
    """)
    result = await session.execute(query, {"state": state})
    companies = result.mappings().all()  
    return companies


# ---------------- Daily Folder ----------------
def ensure_daily_folder(state: str, base_dir: str = "/scraper_data") -> Path:
    """
    {base_dir}/{state_lower}_new_business/YYYY/MM/DD
    """
    today = datetime.now(timezone.utc)
    daily_folder = Path(base_dir) / f"{state.lower()}_new_business" / f"{today:%Y/%m/%d}"
    daily_folder.mkdir(parents=True, exist_ok=True)
    return daily_folder

def init_daily_errors_file(state: str, base_dir: str = "/scraper_data") -> Path:
    """

    """
    daily_folder = ensure_daily_folder(state, base_dir=base_dir)
    errors_file = daily_folder / "crawl_errors_count_ny.txt"
    if not errors_file.exists():
        errors_file.touch()
    return errors_file


def init_runtime_log_file(state: str, base_dir: str = "/scraper_data") -> Path:
    """
    """
    daily_folder = ensure_daily_folder(state, base_dir=base_dir)
    runtime_file = daily_folder / "runtime_log.txt"
    if not runtime_file.exists():
        runtime_file.touch()
    return runtime_file

# ---------------- Export CSV + NDJSON ----------------
def export_data(companies: List[dict], output_dir: str, prefix: str = "entities") -> tuple[Path, Path]:
    """
    Exports list of company dicts to CSV and NDJSON using pandas.
    Returns tuple of file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_file = output_dir / f"{prefix}.csv"
    ndjson_file = output_dir / f"{prefix}.ndjson"

    if not companies:
        logger.error("No companies found for export")
        return csv_file, ndjson_file

    # DataFrame
    df = pd.DataFrame(companies)
    
    # CSV
    df.to_csv(csv_file, index=False, encoding="utf-8")
    
    # NDJSON
    df.to_json(ndjson_file, orient="records", lines=True, force_ascii=False)

    return csv_file, ndjson_file

# ---------------- Checksums ----------------
def sha256_file(file_path: Path) -> str:
    """Returns SHA256 checksum of a file"""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(
    source_state: str,
    entities_total: int,
    officer_rows_total: int,
    pdfs_total: int,
    officer_data_available: int,
    pdfs_available: int,
    coverage_notes: str,
    crawl_duration_seconds: float,
    crawl_errors_total: int,
    generator: str = "ny_scraper_v1",
    output_dir: str = "/ny_new_business"
):
    """
    Creates manifest.json in daily output folder (YYYY/MM/DD).
    Date is automatically today UTC.
    """
    now = datetime.now(timezone.utc)

    # Daily folder path
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "date": now.strftime("%Y-%m-%d"),
        "timezone": "UTC",
        "source_state": source_state,
        "entities_total": entities_total,
        "officer_rows_total": officer_rows_total,
        "pdfs_total": pdfs_total,
        "officer_data_available": officer_data_available,
        "pdfs_available": pdfs_available,
        "coverage_notes": coverage_notes,
        "crawl_duration_seconds": crawl_duration_seconds,
        "crawl_errors_total": crawl_errors_total,
        "generated_at": now.isoformat(),
        "generator": generator
    }

    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest_file


async def generate_manifest(companies: list[Company], crawl_errors: int, start_time: datetime, output_dir: str = "/ny_new_business", generator:str = "ny_exporter_v1"):
    now = datetime.now(timezone.utc)
    crawl_duration_seconds = (now - start_time).total_seconds()

    entities_total = len(companies)
    officer_rows_total = 0
    pdfs_total = 0 
    officer_data_available = officer_rows_total 
    pdfs_available = 0 

    coverage_notes = "Includes Statements of Information (Initial + Amendments)"

    manifest_file = write_manifest(
        source_state="NY",
        entities_total=entities_total,
        officer_rows_total=officer_rows_total,
        pdfs_total=pdfs_total,
        officer_data_available=officer_data_available,
        pdfs_available=pdfs_available,
        coverage_notes=coverage_notes,
        crawl_duration_seconds=crawl_duration_seconds,
        crawl_errors_total=crawl_errors,
        output_dir=output_dir,
        generator=generator
    )

    logger.info("Manifest created: %s", manifest_file)