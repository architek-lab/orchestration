import io
import logging
from datetime import datetime, timezone

import boto3
import paramiko

from config import (AWS_REGION, DEFAULT_CATEGORY, FILE_CATEGORY_MAP,
                    RHINEOPS_SFTP_HOST, RHINEOPS_SFTP_PRIVATE_KEY_FILE,
                    RHINEOPS_SFTP_USERNAME, S3_BUCKET, S3_PARTITION_KEY,
                    S3_RAW_SFTP_PREFIX, SFTP_PORT, SFTP_REMOTE_DIR,
                    configure_logging)

logger = logging.getLogger(__name__)


def connect_sftp(host: str, port: int, username: str, key_file: str):
    """Log in with a private key.

    Returns the SFTP client and the transport so the caller can close both.
    """
    key = paramiko.RSAKey.from_private_key_file(key_file)
    transport = paramiko.Transport((host, port))
    transport.connect(username=username, pkey=key)
    return paramiko.SFTPClient.from_transport(transport), transport


def categorize_file(filename: str) -> str:
    """Return the category whose key appears in the filename."""
    name = filename.lower()
    return next(
        (cat for key, cat in FILE_CATEGORY_MAP.items() if key in name),
        DEFAULT_CATEGORY,
    )


def list_remote_files(sftp) -> list:
    """List the files in the remote folder. Fail if it is empty."""
    files = sftp.listdir(SFTP_REMOTE_DIR)
    if not files:
        raise FileNotFoundError(
            f"No files found in {SFTP_REMOTE_DIR} - refusing an empty run"
        )
    logger.info("Found %s files in %s", len(files), SFTP_REMOTE_DIR)
    return files


def stream_file_to_s3(sftp, s3_client, filename: str, run_date: str) -> str:
    """Pull a file from SFTP into memory and upload it to S3.

    Returns the S3 path of the uploaded file.
    """
    # raw/sftp/shipments/dt=2026-10-04/shipments_01.csv
    key = (
        f"{S3_RAW_SFTP_PREFIX}/{categorize_file(filename)}/"
        f"{S3_PARTITION_KEY}={run_date}/{filename}"
    )

    buffer = io.BytesIO()
    sftp.getfo(f"{SFTP_REMOTE_DIR}/{filename}", buffer)
    buffer.seek(0)
    s3_client.upload_fileobj(buffer, S3_BUCKET, key)

    s3_path = f"s3://{S3_BUCKET}/{key}"
    logger.info("Landed %s to %s", filename, s3_path)
    return s3_path


def extract_sftp(run_date: str) -> str:
    """Pull every file from the SFTP server and land each in S3.

    Args:
        run_date: run date as YYYY-MM-DD, used for the S3 partition.

    Returns:
        The S3 prefix the files were landed under.
    """
    try:
        logger.info("Starting SFTP extraction")
        s3_client = boto3.client("s3", region_name=AWS_REGION)
        sftp, transport = connect_sftp(
            RHINEOPS_SFTP_HOST,
            SFTP_PORT,
            RHINEOPS_SFTP_USERNAME,
            RHINEOPS_SFTP_PRIVATE_KEY_FILE,
        )

        try:
            for name in list_remote_files(sftp):
                stream_file_to_s3(sftp, s3_client, name, run_date)
        finally:
            sftp.close()
            transport.close()

        return f"s3://{S3_BUCKET}/{S3_RAW_SFTP_PREFIX}"
    except Exception as exc:
        logger.error("SFTP extraction failed: %s", exc)
        raise


if __name__ == "__main__":
    configure_logging()
    extract_sftp(datetime.now(timezone.utc).strftime("%Y-%m-%d"))
