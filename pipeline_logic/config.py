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


AWS_REGION = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION"))
S3_BUCKET = os.getenv("S3_BUCKET")
S3_PARTITION_KEY = os.getenv("S3_PARTITION_KEY", "dt")

GOOGLE_SERVICE_ACCOUNT_SSM_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_SSM_PATH")
PROCUREMENT_SHEET_ID = os.getenv("PROCUREMENT_SHEET_ID")
GOOGLE_SCOPES = os.getenv(
    "GOOGLE_SCOPES", "https://www.googleapis.com/auth/drive.readonly"
).split(",")
PROCUREMENT_EXPORT_MIME_TYPE = os.getenv(
    "PROCUREMENT_EXPORT_MIME_TYPE", "text/csv"
)
S3_PROCUREMENT_PREFIX = os.getenv(
    "S3_PROCUREMENT_PREFIX", "raw/google_sheets/procurement"
).strip("/")
S3_PROCUREMENT_FILENAME = os.getenv(
    "S3_PROCUREMENT_FILENAME", "procurement.csv"
)

RHINEOPS_SFTP_HOST = os.getenv("RHINEOPS_SFTP_HOST")
RHINEOPS_SFTP_USERNAME = os.getenv("RHINEOPS_SFTP_USERNAME")
RHINEOPS_SFTP_PRIVATE_KEY_FILE = os.getenv("RHINEOPS_SFTP_PRIVATE_KEY_FILE")
SFTP_PORT = int(os.getenv("RHINEOPS_SFTP_PORT", "22"))
SFTP_REMOTE_DIR = os.getenv("RHINEOPS_SFTP_REMOTE_DIR", "/outbound")
S3_RAW_SFTP_PREFIX = os.getenv("S3_RAW_SFTP_PREFIX", "raw/sftp").strip("/")

FILE_CATEGORY_MAP = {
    "shipment": "shipments",
    "quality": "quality_inspections",
    "finance": "finance_reconciliation",
}
DEFAULT_CATEGORY = os.getenv("SFTP_DEFAULT_CATEGORY", "uncategorized")
