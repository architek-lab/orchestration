import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s [%(levelname)s] %(message)s")
LOG_DATE_FORMAT = os.getenv("LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S")

NOISY_LOGGERS = (
    "boto3",
    "botocore",
    "s3transfer",
    "urllib3",
    "googleapiclient",
    "paramiko",
)


def configure_logging() -> None:
    """Set up logging. Call once, at the entry point of a script."""
    logging.basicConfig(
        level=LOG_LEVEL, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT
    )
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


AWS_REGION = "eu-central-1"
S3_BUCKET = "architek-lab-test-datalake"
S3_PARTITION_KEY = "dt"

GOOGLE_SERVICE_ACCOUNT_SSM_PATH = "/architek/service-account/credentials"
PROCUREMENT_SHEET_ID = "1x31wcMPQQ7dNATLQqxDfQSOUfwKgNPgQu_Xcs1-hifM"
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
PROCUREMENT_EXPORT_MIME_TYPE = "text/csv"
S3_PROCUREMENT_PREFIX = "raw/google_sheets/procurement"
S3_PROCUREMENT_FILENAME = "procurement.csv"

SFTP = {
    "host": "s-d68a304aef57489ab.server.transfer.eu-central-1.amazonaws.com",
    "port": 22,
    "username": "nordtextil",
    "ssm": "/architek/sftp-user/private-key",
}
S3_RAW_SFTP_PREFIX = "raw/sftp"

FILE_CATEGORY_MAP = {
    "shipment": "shipments",
    "quality": "quality_inspections",
    "finance": "finance_reconciliation",
}
DEFAULT_CATEGORY = "uncategorized"
