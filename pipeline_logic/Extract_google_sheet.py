import io
import json
import logging
from datetime import datetime, timezone

import boto3
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config import (
    AWS_REGION,
    GOOGLE_SCOPES,
    GOOGLE_SERVICE_ACCOUNT_SSM_PATH,
    PROCUREMENT_EXPORT_MIME_TYPE,
    PROCUREMENT_SHEET_ID,
    S3_BUCKET,
    S3_PARTITION_KEY,
    S3_PROCUREMENT_FILENAME,
    S3_PROCUREMENT_PREFIX,
    configure_logging,
)

logger = logging.getLogger(__name__)


def load_service_account_info(
    ssm_parameter_path: str, region_name: str
) -> dict:
    """Fetch the service-account JSON from AWS SSM and return it as a dict."""
    ssm = boto3.client("ssm", region_name=region_name)
    response = ssm.get_parameter(Name=ssm_parameter_path, WithDecryption=True)
    return json.loads(response["Parameter"]["Value"])


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
    """Export the procurement sheet and stream it to S3.

    Args:
        run_date: run date as YYYY-MM-DD, used for the S3 partition.

    Returns:
        The S3 path of the uploaded file.
    """
    try:
        logger.info("Starting extraction: Google Sheet")

        creds = Credentials.from_service_account_info(
            load_service_account_info(
                GOOGLE_SERVICE_ACCOUNT_SSM_PATH, AWS_REGION
            ),
            scopes=GOOGLE_SCOPES,
        )
        drive_service = build("drive", "v3", credentials=creds)

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
    except Exception as exc:
        logger.error("Google Sheet extraction failed: %s", exc)
        raise


if __name__ == "__main__":
    configure_logging()
    extract_google_sheet(datetime.now(timezone.utc).strftime("%Y-%m-%d"))