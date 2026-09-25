

# required import
import io
import os
import logging
from datetime import datetime, timezone

import boto3
import paramiko
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Key based auth only: no password in env vars for an unattended nightly job
SFTP_HOST = os.getenv("RHINEOPS_SFTP_HOST")
SFTP_PORT = int(os.getenv("RHINEOPS_SFTP_PORT", "22"))
SFTP_USERNAME = os.getenv("RHINEOPS_SFTP_USERNAME")
SFTP_PRIVATE_KEY_FILE = os.getenv("RHINEOPS_SFTP_PRIVATE_KEY_FILE")
SFTP_REMOTE_DIR = os.getenv("RHINEOPS_SFTP_REMOTE_DIR", "/outbound")

S3_BUCKET = os.getenv("S3_BUCKET")
S3_RAW_PREFIX = "raw/sftp"

FILE_CATEGORY_MAP = {
    "shipment": "shipments",
    "quality": "quality_inspections",
    "finance": "finance_reconciliation",
}


def connect_sftp():
    key = paramiko.RSAKey.from_private_key_file(SFTP_PRIVATE_KEY_FILE)
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    transport.connect(username=SFTP_USERNAME, pkey=key)
    return paramiko.SFTPClient.from_transport(transport), transport


def categorize_file(filename: str) -> str:
    lname = filename.lower()
    for pattern, category in FILE_CATEGORY_MAP.items():
        if pattern in lname:
            return category
    return "uncategorized"


def list_remote_files(sftp) -> list:
    files = sftp.listdir(SFTP_REMOTE_DIR)
    logger.info(f"Found {len(files)} files on RhineOps SFTP")
    return files


def stream_file_to_s3(sftp, s3, filename: str, run_date: datetime) -> str:
    """Stream directly from SFTP into S3 — no temp files on the worker's disk."""
    category = categorize_file(filename)
    date_str = run_date.strftime("%Y-%m-%d")
    key = f"{S3_RAW_PREFIX}/{category}/dt={date_str}/{filename}"

    remote_path = f"{SFTP_REMOTE_DIR}/{filename}"
    buffer = io.BytesIO()
    sftp.getfo(remote_path, buffer)
    buffer.seek(0)

    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=buffer.getvalue())
    logger.info(f"Landed {filename} to s3://{S3_BUCKET}/{key}")
    return key


def extract_sftp() -> list:
    """
    Runs the full extraction: connect to RhineOps' SFTP, pull every file found,
    land each to S3. Returns the list of S3 keys that were written.
    """
    run_date = datetime.now(timezone.utc)

    # RHINEOPS_SFTP_HOST 
    if not SFTP_HOST:
        logger.warning(
            "RHINEOPS_SFTP_HOST not set — running extract_sftp in placeholder "
            "mode, no real connection attempted, nothing landed to S3."
        )
        return []

    if not S3_BUCKET:
        raise ValueError("S3_BUCKET not set — refusing to run without a destination bucket")

    logger.info("Starting SFTP extraction: RhineOps nightly files")
    sftp, transport = connect_sftp()
    s3 = boto3.client("s3")

    try:
        filenames = list_remote_files(sftp)
        if not filenames:
            raise ValueError("No files found on RhineOps SFTP — refusing an empty run")

        keys = [stream_file_to_s3(sftp, s3, f, run_date) for f in filenames]
    finally:
        sftp.close()
        transport.close()

    return keys


if __name__ == "__main__":
    extract_sftp()