import io
import json
import logging
import os
from datetime import datetime, timezone

import awswrangler as wr
import boto3
import pandas as pd
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SPREADSHEET_ID = os.getenv("PROCUREMENT_SHEET_ID")
GOOGLE_SERVICE_ACCOUNT_SSM_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_SSM_PATH")

S3_BUCKET = os.getenv("S3_BUCKET")
S3_PREFIX = os.getenv("S3_PROCUREMENT_PREFIX", "raw/google_sheets/procurement")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION"))


def load_google_credentials(
    ssm_parameter_path: str, region_name: str, scopes: list
) -> Credentials:
    """Fetch a service-account JSON from AWS SSM and build Credentials.
    """
    ssm = boto3.client("ssm", region_name=region_name)
    response = ssm.get_parameter(
        Name=ssm_parameter_path, WithDecryption=True
    )
    service_account_info = json.loads(response["Parameter"]["Value"])
    return Credentials.from_service_account_info(
        service_account_info, scopes=scopes
    )


def download_sheet(drive_service, sheet_id: str) -> pd.DataFrame:
    request = drive_service.files().export_media(
        fileId=sheet_id, mimeType="text/csv"
    )
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)
    return pd.read_csv(buffer, dtype=str, keep_default_na=False)


def extract_google_sheet(run_date: str, debug_print: bool = False) -> list:
    """
    Runs the full extraction: authenticate, fetch the sheet, land to S3.

    """
    if not GOOGLE_SERVICE_ACCOUNT_SSM_PATH:
        logger.warning(
            "GOOGLE_SERVICE_ACCOUNT_SSM_PATH not set — running "
            "extract_google_sheet in placeholder mode, nothing "
            "fetched or landed."
        )
        return []

    if not SPREADSHEET_ID:
        raise ValueError(
            "PROCUREMENT_SHEET_ID not set — refusing to run "
            "without a sheet to pull"
        )

    if not S3_BUCKET:
        raise ValueError(
            "S3_BUCKET not set — refusing to run without a destination bucket")

    logger.info("Starting extraction: procurement Google Sheet")
    creds = load_google_credentials(
        GOOGLE_SERVICE_ACCOUNT_SSM_PATH, AWS_REGION, SCOPES
    )
    drive_service = build("drive", "v3", credentials=creds)
    logger.info(f"Authenticated to Google as: {creds.service_account_email}")

    df = download_sheet(drive_service, SPREADSHEET_ID)

    if debug_print:
        print(f"\nRows: {len(df)}, Columns: {list(df.columns)}\n")
        print(df.head(10))
        print()

    s3_path = f"s3://{S3_BUCKET}/{S3_PREFIX}/dt={run_date}/procurement.csv"
    session = boto3.Session(region_name=AWS_REGION)
    wr.s3.to_csv(df, path=s3_path, index=False, boto3_session=session)
    logger.info(f"Landed {len(df)} rows to {s3_path}")

    return [s3_path]


if __name__ == "__main__":
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    extract_google_sheet(today, debug_print=True)