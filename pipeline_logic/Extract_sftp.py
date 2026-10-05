
import io
import logging
from datetime import datetime, timezone

import boto3
import paramiko

import config

logger = logging.getLogger(__name__)


def connect_sftp(host: str, port: int, username: str, key_file: str):
    """Log in with a private key.

    Returns the SFTP client, and the transport (the underlying connection)
    so the caller can close both when finished.
    """
    key = paramiko.RSAKey.from_private_key_file(key_file)
    transport = paramiko.Transport((host, port))
    transport.connect(username=username, pkey=key)
    return paramiko.SFTPClient.from_transport(transport), transport


def categorize_file(
    filename: str, category_map: dict, default: str = "uncategorized"
) -> str:
    """Return the category whose key appears in the filename."""
    # Keys of the map that appear in the lowercased filename.
    matches = filter(filename.lower().__contains__, category_map)
    try:
        # The first match wins.
        return category_map[next(matches)]
    except StopIteration:
        # Nothing matched.
        return default


def list_remote_files(sftp, remote_dir: str) -> list:
    """List the files in a remote folder. Fail if the folder is empty."""
    files = sftp.listdir(remote_dir)
    try:
        # Asking for the first item fails when the folder is empty.
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
    """Pull a file from SFTP into memory and upload it straight to S3.

    Returns the S3 path of the uploaded file.
    """
    # Build the S3 key. Example:
    # raw/sftp/shipments/dt=2026-10-04/shipments_01.csv
    category = categorize_file(filename, category_map, default_category)
    partition = f"{partition_key}={run_date}"
    key = f"{prefix.strip('/')}/{category}/{partition}/{filename}"

    # Read the remote file into memory, then rewind and upload it.
    buffer = io.BytesIO()
    sftp.getfo(f"{remote_dir}/{filename}", buffer)
    buffer.seek(0)
    s3_client.upload_fileobj(buffer, bucket, key)

    s3_path = f"s3://{bucket}/{key}"
    logger.info("Landed %s to %s", filename, s3_path)
    return s3_path


def extract_sftp(
    run_date: str,
    host: str | None = None,
    port: int | None = None,
    username: str | None = None,
    key_file: str | None = None,
    remote_dir: str | None = None,
    bucket: str | None = None,
    prefix: str | None = None,
    category_map: dict | None = None,
    default_category: str | None = None,
    region: str | None = None,
) -> list:
    """Connect to the SFTP server, pull every file, land each to S3.

    Every argument except run_date falls back to config.py.

    Args:
        run_date: date of the run as YYYY-MM-DD, used for the S3 folder.

    Returns:
        A list of the S3 paths of the uploaded files.
    """
    try:
        # Use the argument if it was given, otherwise fall back to config.
        host = host or config.required("RHINEOPS_SFTP_HOST")
        username = username or config.required("RHINEOPS_SFTP_USERNAME")
        key_file = key_file or config.required(
            "RHINEOPS_SFTP_PRIVATE_KEY_FILE"
        )
        bucket = bucket or config.required("S3_BUCKET")
        port = port or config.SFTP_PORT
        remote_dir = remote_dir or config.SFTP_REMOTE_DIR
        prefix = prefix or config.S3_RAW_SFTP_PREFIX
        category_map = category_map or config.FILE_CATEGORY_MAP
        default_category = default_category or config.DEFAULT_CATEGORY
        region = region or config.AWS_REGION

        logger.info("Starting SFTP extraction")
        s3_client = boto3.client("s3", region_name=region)
        sftp, transport = connect_sftp(host, port, username, key_file)

        try:
            filenames = list_remote_files(sftp, remote_dir)
            # Upload every file and collect the S3 paths.
            return [
                stream_file_to_s3(
                    sftp, s3_client, name, run_date, remote_dir, bucket,
                    prefix, category_map, default_category,
                    config.S3_PARTITION_KEY,
                )
                for name in filenames
            ]
        finally:
            # Always close the connection, even after an error.
            sftp.close()
            transport.close()
    except Exception as exc:
        # Log one clear line, then re-raise so the caller (for example
        # Airflow) sees that the run failed.
        logger.error("SFTP extraction failed: %s", exc)
        raise


# Runs only when the file is executed directly, not when it is imported.
if __name__ == "__main__":
    config.configure_logging()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    extract_sftp(today)