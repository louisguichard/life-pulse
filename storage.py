import os
from dotenv import load_dotenv
import csv
from google.cloud import storage
from datetime import datetime
import io

# Load Cloud Storage env variables
load_dotenv()
PROJECT_ID = os.getenv("PROJECT_ID")
BUCKET_NAME = os.getenv("BUCKET_NAME")
FILE_NAME = os.getenv("FILE_NAME")

storage_client = storage.Client(project=PROJECT_ID)


def load_data():
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(FILE_NAME)
    if not blob.exists():
        return []
    data = blob.download_as_text()
    reader = csv.reader(io.StringIO(data))
    return list(reader)


def save_data(row):
    row = [str(item) for item in row]
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(FILE_NAME)
    if not blob.exists():
        rows = []
    else:
        data = blob.download_as_text()
        reader = csv.reader(io.StringIO(data))
        rows = list(reader)
    rows.append(row)
    rows.sort(key=lambda r: r[0])
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerows(rows)
    blob.upload_from_string(output.getvalue())


def delete_data(target_row):
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(FILE_NAME)
    if not blob.exists():
        raise ValueError("Data file does not exist.")

    data = blob.download_as_text()
    reader = csv.reader(io.StringIO(data))
    rows = list(reader)

    # Attempt to find and remove the target row
    row_found = False
    for existing_row in rows:
        if existing_row == target_row:
            rows.remove(existing_row)
            row_found = True
            break

    if not row_found:
        raise ValueError("Record not found.")

    # Write the updated rows back to the CSV
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerows(rows)
    blob.upload_from_string(output.getvalue())


def get_latest_mood():
    data = load_data()
    mood_entries = [row for row in data if row[1] == "Mood"]
    if not mood_entries:
        return None
    mood_entries.sort(
        key=lambda x: datetime.strptime(x[0], "%Y-%m-%d - %Hh"), reverse=True
    )
    latest_mood = mood_entries[0][2]
    return latest_mood


def log_failed_attempt():
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob("last_failed_attempt.txt")
    current_time = datetime.now().isoformat()
    blob.upload_from_string(current_time)


def get_last_failed_attempt():
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob("last_failed_attempt.txt")
    if not blob.exists():
        return None
    last_attempt = blob.download_as_text().strip()
    return datetime.fromisoformat(last_attempt)
