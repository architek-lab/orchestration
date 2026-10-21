import io
import logging
from datetime import datetime, timezone

import boto3
import paramiko

from config import (AWS_REGION, DEFAULT_CATEGORY, FILE_CATEGORY_MAP, S3_BUCKET,
                    S3_PARTITION_KEY, S3_RAW_SFTP_PREFIX, SFTP,
                    configure_logging)

logger = logging.getLogger(__name__)


def extract_sftp():
    dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pem = boto3.client("ssm", region_name=AWS_REGION).get_parameter(
        Name=SFTP["ssm"], WithDecryption=True)["Parameter"]["Value"]
    pkey = paramiko.RSAKey.from_private_key(io.StringIO(pem))

    transport = paramiko.Transport((SFTP["host"], SFTP["port"]))
    transport.connect(username=SFTP["username"], pkey=pkey)
    sftp = paramiko.SFTPClient.from_transport(transport)
    s3 = boto3.client("s3", region_name=AWS_REGION)

    try:
        for name in sftp.listdir():
            try:
                buf = io.BytesIO()
                sftp.getfo(name, buf)  # fails on folders, so they are skipped
                buf.seek(0)
                cat = next(
                    (c for k, c in FILE_CATEGORY_MAP.items()
                     if k in name.lower()),
                    DEFAULT_CATEGORY,
                )
                key = (f"{S3_RAW_SFTP_PREFIX}/{cat}/"
                       f"{S3_PARTITION_KEY}={dt}/{name}")
                s3.upload_fileobj(buf, S3_BUCKET, key)
                logger.info("Landed %s to s3://%s/%s", name, S3_BUCKET, key)
            except IOError:
                continue
    finally:
        sftp.close()
        transport.close()


if __name__ == "__main__":
    configure_logging()
    extract_sftp()
