"""
Google Sheets test — credentials pulled from AWS SSM Parameter Store
(SecureString), not a local JSON file. This is the "real" way described in
the earlier test scripts' docstrings.

Requires (in .env or environment):
    PROCUREMENT_SHEET_ID
    GOOGLE_SERVICE_ACCOUNT_SSM_PATH   e.g. /architek/service-account/credentials
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    AWS_DEFAULT_REGION                e.g. eu-central-1

The SSM parameter must contain the full service-account JSON as its value
(the same content as the .json key file you downloaded from Google Cloud).

Usage:
    python test_google_sheet_ssm.py
"""

import io
import json
import os
import sys

import boto3
import pandas as pd
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SPREADSHEET_ID = os.getenv("PROCUREMENT_SHEET_ID")
SSM_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_SSM_PATH")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION"))


def clean_column_names(columns):
    return (
        columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace(r"[().]", "", regex=True)
    )


def load_google_credentials_from_ssm() -> Credentials:
    if not SSM_PATH:
        print("ERROR: GOOGLE_SERVICE_ACCOUNT_SSM_PATH not found in .env")
        sys.exit(1)

    print(f"Fetching Google credentials from SSM: {SSM_PATH} (region={AWS_REGION})...")
    ssm = boto3.client("ssm", region_name=AWS_REGION)

    try:
        response = ssm.get_parameter(Name=SSM_PATH, WithDecryption=True)
    except ssm.exceptions.ParameterNotFound:
        print(f"ERROR: No SSM parameter found at path: {SSM_PATH}")
        sys.exit(1)

    raw_value = response["Parameter"]["Value"]

    try:
        service_account_info = json.loads(raw_value)
    except json.JSONDecodeError:
        print("ERROR: SSM parameter value is not valid JSON — check what's stored there.")
        sys.exit(1)

    print("Google credentials loaded from SSM.")
    return Credentials.from_service_account_info(service_account_info, scopes=SCOPES)


def main():
    if not SPREADSHEET_ID:
        print("ERROR: PROCUREMENT_SHEET_ID not found in .env")
        sys.exit(1)

    creds = load_google_credentials_from_ssm()
    drive_service = build("drive", "v3", credentials=creds)
    print(f"Authenticated as: {creds.service_account_email}")
    print("(If you get a 404 below, share the sheet with this email as Viewer.)")

    print(f"\nFetching sheet {SPREADSHEET_ID}...")
    request = drive_service.files().export_media(
        fileId=SPREADSHEET_ID, mimeType="text/csv"
    )
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)
    df = pd.read_csv(buffer)
    df.columns = clean_column_names(df.columns)

    print(f"\nRows: {len(df)}, Columns: {list(df.columns)}\n")
    print(df.head(10))


if __name__ == "__main__":
    main()