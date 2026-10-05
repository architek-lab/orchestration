
import logging
import os

from dotenv import load_dotenv

# Load the .env file, if there is one, into the process environment.
load_dotenv()


class ConfigError(Exception):
    """Raised when a required setting is missing."""


def required(name: str) -> str:
    """Return the environment variable `name`, or raise ConfigError."""
    try:
        return os.environ[name]
    except KeyError:
        raise ConfigError(
            f"Missing required setting {name}. "
            "Set it in your environment or .env file."
        ) from None


# Logging. Set LOG_LEVEL=DEBUG to also see the sheet preview.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s [%(levelname)s] %(message)s")
LOG_DATE_FORMAT = os.getenv("LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S")

# Libraries that log a lot. Only their warnings and errors are shown.
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


# AWS. With no region set, boto3 uses its own default.
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION"))

# Name of the date folder in S3, which gives paths like dt=2026-10-04.
S3_PARTITION_KEY = os.getenv("S3_PARTITION_KEY", "dt")

# Google Sheets (procurement). Read-only Drive access, exported as CSV.
# GOOGLE_SCOPES is comma-separated in the environment and a list here.
GOOGLE_SCOPES = os.getenv(
    "GOOGLE_SCOPES", "https://www.googleapis.com/auth/drive.readonly"
).split(",")
PROCUREMENT_EXPORT_MIME_TYPE = os.getenv(
    "PROCUREMENT_EXPORT_MIME_TYPE", "text/csv"
)

# Where the exported sheet lands in S3.
S3_PROCUREMENT_PREFIX = os.getenv(
    "S3_PROCUREMENT_PREFIX", "raw/google_sheets/procurement"
)
S3_PROCUREMENT_FILENAME = os.getenv(
    "S3_PROCUREMENT_FILENAME", "procurement.csv"
)

# SFTP (RhineOps): server port, folder to read, and where files land in S3.
SFTP_PORT = int(os.getenv("RHINEOPS_SFTP_PORT", "22"))
SFTP_REMOTE_DIR = os.getenv("RHINEOPS_SFTP_REMOTE_DIR", "/outbound")
S3_RAW_SFTP_PREFIX = os.getenv("S3_RAW_SFTP_PREFIX", "raw/sftp")

# A file goes to the folder whose key appears in its name. For example a
# name containing "shipment" lands in shipments. With no match, the file
# goes to DEFAULT_CATEGORY so it is never lost.
FILE_CATEGORY_MAP = {
    "shipment": "shipments",
    "quality": "quality_inspections",
    "finance": "finance_reconciliation",
}
DEFAULT_CATEGORY = os.getenv("SFTP_DEFAULT_CATEGORY", "uncategorized")