import sys
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.sdk import dag, task

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_LOGIC_DIR = str(PROJECT_ROOT / "pipeline_logic")


@dag(
    dag_id="nordtextil_extract_raw",
    schedule="0 4 * * *",
    start_date=pendulum.datetime(2026, 10, 31, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "ossai",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["nordtextil", "extract", "s3"],
)
def nordtextil_extract_raw():
    @task
    def extract_google_sheet_to_s3(ds=None) -> str:
        sys.path.insert(0, PIPELINE_LOGIC_DIR)
        from Extract_google_sheet import extract_google_sheet

        return extract_google_sheet(ds)

    @task
    def extract_sftp_to_s3(ds=None) -> None:
        sys.path.insert(0, PIPELINE_LOGIC_DIR)
        from Extract_sftp import extract_sftp

        extract_sftp(ds)

    extract_google_sheet_to_s3()
    extract_sftp_to_s3()


nordtextil_extract_raw()
