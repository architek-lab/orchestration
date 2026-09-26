
import io
import json
import logging
import os
from datetime import datetime, timezone

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


def clean_column_names(columns):
    return (
        columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace(r"[().]", "", regex=True)
    )


def load_google_credentials() -> Credentials:
    """Pull the service-account JSON from AWS SSM Parameter Store and build Credentials from it."""
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    response = ssm.get_parameter(
        Name=GOOGLE_SERVICE_ACCOUNT_SSM_PATH,
        WithDecryption=True)
    service_account_info = json.loads(response["Parameter"]["Value"])
    return Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES)


def fetch_sheet_as_dataframe() -> pd.DataFrame:
    creds = load_google_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    logger.info(f"Authenticated to Google as: {creds.service_account_email}")

    logger.info(f"Fetching sheet {SPREADSHEET_ID}...")
    request = drive_service.files().export_media(
        fileId=SPREADSHEET_ID, mimeType="text/csv"
    )
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)
    df = pd.read_csv(buffer)
    df.columns = clean_column_names(df.columns)
    return df


def push_dataframe_to_s3(s3, df: pd.DataFrame, run_date: datetime) -> str:
    date_str = run_date.strftime("%Y-%m-%d")
    key = f"{S3_PREFIX}/dt={date_str}/procurement.csv"

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)

    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=csv_buffer.getvalue())
    logger.info(f"Landed procurement sheet to s3://{S3_BUCKET}/{key}")
    return key


def extract_google_sheet(debug_print: bool = False) -> list:
    """
    Runs the full extraction: connect to Google, pull the
    sheet, land it to S3. Returns the list of S3 keys that were written.

    debug_print=True also prints the DataFrame to the terminal — handy
    for local testing, not used when this runs unattended in the pipeline.
    """
    run_date = datetime.now(timezone.utc)

    # connection
    if not GOOGLE_SERVICE_ACCOUNT_SSM_PATH:
        logger.warning(
            "GOOGLE_SERVICE_ACCOUNT_SSM_PATH not set — running "
            "extract_google_sheet in placeholder mode, nothing fetched or landed.")
        return []

    if not SPREADSHEET_ID:
        raise ValueError(
            "PROCUREMENT_SHEET_ID not set — refusing to run without a sheet to pull")

    if not S3_BUCKET:
        raise ValueError(
            "S3_BUCKET not set — refusing to run without a destination bucket")

    logger.info("Starting extraction: procurement Google Sheet")
    df = fetch_sheet_as_dataframe()

    if debug_print:
        print(f"\nRows: {len(df)}, Columns: {list(df.columns)}\n")
        print(df.head(10))
        print()

    s3 = boto3.client("s3", region_name=AWS_REGION)
    key = push_dataframe_to_s3(s3, df, run_date)

    return [key]


if __name__ == "__main__":
    extract_google_sheet(debug_print=True)
