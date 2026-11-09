from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from Extract_google_sheet import extract_google_sheet
from Extract_sftp import extract_sftp

with DAG(
    dag_id="nordtextil_extract_raw",
    start_date=datetime(2026, 10, 31),
    schedule="0 4 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "ossai",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["nordtextil", "extract", "s3"],
) as dag:

    PythonOperator(
        task_id="extract_google_sheet_to_s3",
        python_callable=extract_google_sheet,
    )

    PythonOperator(
        task_id="extract_sftp_to_s3",
        python_callable=extract_sftp,
    )