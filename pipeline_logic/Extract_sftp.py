import io
import logging
from datetime import datetime, timezone

import boto3
import paramiko
from Extract_google_sheet import get_ssm_parameter

from config import (AWS_REGION, S3_BUCKET, S3_PARTITION_KEY,
                    S3_RAW_SFTP_PREFIX, SFTP, configure_logging)

logger = logging.getLogger(__name__)


def extract_sftp(run_date: str):
    """Stream every CSV in the SFTP root to S3. run_date is YYYY-MM-DD."""
    raw_private_key = get_ssm_parameter(SFTP["ssm"], AWS_REGION)
    private_key = paramiko.Ed25519Key.from_private_key(
        io.StringIO(raw_private_key)
    )

    transport = paramiko.Transport((SFTP["host"], SFTP["port"]))
    transport.connect(username=SFTP["username"], pkey=private_key)
    sftp = paramiko.SFTPClient.from_transport(transport)
    s3 = boto3.client("s3", region_name=AWS_REGION)

    try:
        csv_files = [f for f in sftp.listdir() if f.lower().endswith(".csv")]

        for csv_file in csv_files:
            key = (
                f"{S3_RAW_SFTP_PREFIX}/"
                f"{S3_PARTITION_KEY}={run_date}/{csv_file}"
            )
            with sftp.open(csv_file, "rb") as remote_file:
                s3.upload_fileobj(remote_file, S3_BUCKET, key)
            logger.info("Landed %s to s3://%s/%s", csv_file, S3_BUCKET, key)
    finally:
        sftp.close()
        transport.close()


if __name__ == "__main__":
    configure_logging()
    extract_sftp(datetime.now(timezone.utc).strftime("%Y-%m-%d"))
