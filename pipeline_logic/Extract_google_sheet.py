
import io
import json
import logging
from datetime import datetime, timezone

import boto3
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

import config

logger = logging.getLogger(__name__)


def load_google_credentials(
    ssm_parameter_path: str, region_name: str, scopes: list
) -> Credentials:
    """Fetch a service-account JSON string from AWS SSM and build a
    Credentials object (not a string)."""
    ssm = boto3.client("ssm", region_name=region_name)
    # WithDecryption unlocks the value when it is stored as a SecureString.
    response = ssm.get_parameter(Name=ssm_parameter_path, WithDecryption=True)
    # The parameter holds the key file as text. Turn it into a dictionary.
    service_account_info = json.loads(response["Parameter"]["Value"])
    return Credentials.from_service_account_info(
        service_account_info, scopes=scopes
    )


def export_drive_file(
    drive_service, file_id: str, mime_type: str
) -> io.BytesIO:
    """Export a Google file into an in memory buffer (no local file)."""
    request = drive_service.files().export_media(
        fileId=file_id, mimeType=mime_type
    )
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    # Google sends the file in chunks. Keep asking until it is all there.
    done = False
    while not done:
        _, done = downloader.next_chunk()

    # Rewind so the next reader starts at the beginning of the file.
    buffer.seek(0)
    return buffer


def extract_google_sheet(
    run_date: str,
    sheet_id: str | None = None,
    bucket: str | None = None,
    prefix: str | None = None,
    filename: str | None = None,
    mime_type: str | None = None,
    ssm_path: str | None = None,
    region: str | None = None,
    scopes: list | None = None,
) -> list:
    """Authenticate, export the sheet, and stream it straight to S3.

    Every argument except run_date falls back to config.py, so this can be
    reused for any sheet by passing different values.

    Args:
        run_date: date of the run as YYYY-MM-DD, used for the S3 folder.

    Returns:
        A list holding the S3 path of the uploaded file.
    """
    try:
        # Use the argument if it was given, otherwise fall back to config.
        ssm_path = ssm_path or config.required(
            "GOOGLE_SERVICE_ACCOUNT_SSM_PATH"
        )
        sheet_id = sheet_id or config.required("PROCUREMENT_SHEET_ID")
        bucket = bucket or config.required("S3_BUCKET")
        prefix = prefix or config.S3_PROCUREMENT_PREFIX
        filename = filename or config.S3_PROCUREMENT_FILENAME
        mime_type = mime_type or config.PROCUREMENT_EXPORT_MIME_TYPE
        region = region or config.AWS_REGION
        scopes = scopes or config.GOOGLE_SCOPES

        logger.info("Starting extraction: Google Sheet")

        # Log in to Google with the key stored in SSM.
        creds = load_google_credentials(ssm_path, region, scopes)
        drive_service = build("drive", "v3", credentials=creds)
        logger.info(
            "Authenticated to Google as: %s", creds.service_account_email
        )

        # Download the sheet into memory.
        buffer = export_drive_file(drive_service, sheet_id, mime_type)
        size = buffer.getbuffer().nbytes
        logger.info("Exported sheet: %s bytes", size)
        # The preview only shows when LOG_LEVEL=DEBUG.
        logger.debug(
            "Preview: %s",
            buffer.getvalue()[:500].decode("utf-8", errors="replace"),
        )

        # Upload to S3. Example key:
        # raw/google_sheets/procurement/dt=2026-10-04/procurement.csv
        partition = f"{config.S3_PARTITION_KEY}={run_date}"
        key = f"{prefix.strip('/')}/{partition}/{filename}"
        s3 = boto3.client("s3", region_name=region)
        s3.upload_fileobj(buffer, bucket, key)

        s3_path = f"s3://{bucket}/{key}"
        logger.info("Landed %s", s3_path)
        return [s3_path]
    except Exception as exc:
        # Log one clear line, then re-raise so the caller (for example
        # Airflow) sees that the run failed.
        logger.error("Google Sheet extraction failed: %s", exc)
        raise


# Runs only when the file is executed directly, not when it is imported.
if __name__ == "__main__":
    config.configure_logging()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    extract_google_sheet(today)
