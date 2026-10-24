import io
import json
import logging
from datetime import datetime, timezone

import boto3
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config import (AWS_REGION, GOOGLE_SCOPES, GOOGLE_SERVICE_ACCOUNT_SSM_PATH,
                    PROCUREMENT_EXPORT_MIME_TYPE, PROCUREMENT_SHEET_ID,
                    S3_BUCKET, S3_PARTITION_KEY, S3_PROCUREMENT_FILENAME,
                    S3_PROCUREMENT_PREFIX, configure_logging)

logger = logging.getLogger(__name__)


def get_ssm_parameter(parameter_name: str, region_name: str) -> str:
    """Fetch a decrypted SSM parameter and return its raw string value."""
    ssm = boto3.client("ssm", region_name=region_name)
    response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
    return response["Parameter"]["Value"]


def export_drive_file(
    drive_service, file_id: str, mime_type: str
) -> io.BytesIO:
    """Export a Google file into an in-memory buffer."""
    request = drive_service.files().export_media(
        fileId=file_id, mimeType=mime_type
    )
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)
    return buffer


def extract_google_sheet(run_date: str) -> str:
    """Stream the procurement sheet to S3. run_date is YYYY-MM-DD."""
    logger.info("Starting extraction: Google Sheet")

    service_account_json = get_ssm_parameter(
        GOOGLE_SERVICE_ACCOUNT_SSM_PATH, AWS_REGION
    )
    credentials = Credentials.from_service_account_info(
        json.loads(service_account_json), scopes=GOOGLE_SCOPES
    )
    drive_service = build("drive", "v3", credentials=credentials)

    buffer = export_drive_file(
        drive_service, PROCUREMENT_SHEET_ID, PROCUREMENT_EXPORT_MIME_TYPE
    )
    logger.info("Exported sheet: %s bytes", buffer.getbuffer().nbytes)

    key = (
        f"{S3_PROCUREMENT_PREFIX}/{S3_PARTITION_KEY}={run_date}/"
        f"{S3_PROCUREMENT_FILENAME}"
    )
    boto3.client("s3", region_name=AWS_REGION).upload_fileobj(
        buffer, S3_BUCKET, key
    )

    s3_path = f"s3://{S3_BUCKET}/{key}"
    logger.info("Landed %s", s3_path)
    return s3_path


if __name__ == "__main__":
    configure_logging()
    extract_google_sheet(datetime.now(timezone.utc).strftime("%Y-%m-%d"))