import io
import logging
import os
from datetime import datetime, timezone

import awswrangler as wr
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
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION"))

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


def stream_file_to_s3(sftp, session, filename: str, run_date: str) -> str:
    """Stream directly from SFTP into S3"""
    category = categorize_file(filename)
    s3_path = (
        f"s3://{S3_BUCKET}/{S3_RAW_PREFIX}/"
        f"{category}/dt={run_date}/{filename}"
    )

    buffer = io.BytesIO()
    sftp.getfo(f"{SFTP_REMOTE_DIR}/{filename}", buffer)
    buffer.seek(0)

    wr.s3.upload(local_file=buffer, path=s3_path, boto3_session=session)
    logger.info(f"Landed {filename} to {s3_path}")
    return s3_path


def extract_sftp(run_date: str) -> list:
    """
    Runs the full extraction: connect to RhineOps' SFTP, pull every file
    found, land each to S3. 
    """
    # RHINEOPS_SFTP_HOST
    if not SFTP_HOST:
        logger.warning(
            "RHINEOPS_SFTP_HOST not set — running extract_sftp in placeholder "
            "mode, no real connection attempted, nothing landed to S3."
        )
        return []

    if not S3_BUCKET:
        raise ValueError(
            "S3_BUCKET not set — refusing to run without a destination bucket")

    logger.info("Starting SFTP extraction: RhineOps nightly files")
    session = boto3.Session(region_name=AWS_REGION)
    sftp, transport = connect_sftp()

    try:
        filenames = list_remote_files(sftp)
        if not filenames:
            raise ValueError(
                "No files found on RhineOps SFTP — refusing an empty run")

        keys = [
            stream_file_to_s3(sftp, session, f, run_date) for f in filenames
        ]
    finally:
        sftp.close()
        transport.close()

    return keys


if __name__ == "__main__":
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    extract_sftp(today)