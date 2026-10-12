import io
import logging
from datetime import datetime, timezone

import boto3
import paramiko

from config import (
    AWS_REGION,
    DEFAULT_CATEGORY,
    FILE_CATEGORY_MAP,
    RHINEOPS_SFTP_HOST,
    RHINEOPS_SFTP_PRIVATE_KEY_FILE,
    RHINEOPS_SFTP_USERNAME,
    S3_BUCKET,
    S3_PARTITION_KEY,
    S3_RAW_SFTP_PREFIX,
    SFTP_PORT,
    SFTP_REMOTE_DIR,
    configure_logging,
)

logger = logging.getLogger(__name__)


def connect_sftp(host: str, port: int, username: str, key_file: str):
    """Log in with a private key.

    Returns the SFTP client and the transport so the caller can close both.
    """
    key = paramiko.RSAKey.from_private_key_file(key_file)
    transport = paramiko.Transport((host, port))
    transport.connect(username=username, pkey=key)
    return paramiko.SFTPClient.from_transport(transport), transport


def categorize_file(
    filename: str, category_map: dict, default: str = "uncategorized"
) -> str:
    """Return the category whose key appears in the filename."""
    matches = filter(filename.lower().__contains__, category_map)
    try:
        return category_map[next(matches)]
    except StopIteration:
        return default


def list_remote_files(sftp, remote_dir: str) -> list:
    """List the files in a remote folder. Fail if the folder is empty."""
    files = sftp.listdir(remote_dir)
    try:
        files[0]
    except IndexError:
        raise FileNotFoundError(
            f"No files found in {remote_dir} — refusing an empty run"
        ) from None
    logger.info("Found %s files in %s", len(files), remote_dir)
    return files


def stream_file_to_s3(
    sftp,
    s3_client,
    filename: str,
    run_date: str,
    remote_dir: str,
    bucket: str,
    prefix: str,
    category_map: dict,
    default_category: str,
    partition_key: str,
) -> str:
    """Pull a file from SFTP into memory and upload it to S3.

    Returns the S3 path of the uploaded file.
    """
    category = categorize_file(filename, category_map, default_category)
    # raw/sftp/shipments/dt=2026-10-04/shipments_01.csv
    key = f"{prefix}/{category}/{partition_key}={run_date}/{filename}"

    buffer = io.BytesIO()
    sftp.getfo(f"{remote_dir}/{filename}", buffer)
    buffer.seek(0)
    s3_client.upload_fileobj(buffer, bucket, key)

    s3_path = f"s3://{bucket}/{key}"
    logger.info("Landed %s to %s", filename, s3_path)
    return s3_path


def extract_sftp(run_date: str) -> list:
    """Pull every file from the SFTP server and land each in S3.

    Args:
        run_date: run date as YYYY-MM-DD, used for the S3 partition.

    Returns:
        A list of the S3 paths of the uploaded files.
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
            return [
                stream_file_to_s3(
                    sftp, s3_client, name, run_date, SFTP_REMOTE_DIR,
                    S3_BUCKET, S3_RAW_SFTP_PREFIX, FILE_CATEGORY_MAP,
                    DEFAULT_CATEGORY, S3_PARTITION_KEY,
                )
                for name in list_remote_files(sftp, SFTP_REMOTE_DIR)
            ]
        finally:
            sftp.close()
            transport.close()
    except Exception as exc:
        logger.error("SFTP extraction failed: %s", exc)
        raise


if __name__ == "__main__":
    configure_logging()
    extract_sftp(datetime.now(timezone.utc).strftime("%Y-%m-%d"))