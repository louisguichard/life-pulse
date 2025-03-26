import os
import csv
from google.cloud import storage
from datetime import datetime
import io
import json

# Load Cloud Storage env variables
PROJECT_ID = os.getenv("PROJECT_ID")
BUCKET_NAME = os.getenv("BUCKET_NAME")
FILE_NAME = os.getenv("FILE_NAME", "data.csv")

LOCAL_STORAGE = not all([PROJECT_ID, BUCKET_NAME])
if not LOCAL_STORAGE:
    storage_client = storage.Client(project=PROJECT_ID)


def load_config(config_path):
    if config_path.startswith("gs://"):
        bucket_name, blob_name = config_path.split("/")[-2], config_path.split("/")[-1]
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        if not blob.exists():
            return {}
        data = blob.download_as_text()
        return json.loads(data)
    else:
        with open(config_path, mode="r", newline="") as file:
            return json.load(file)


def load_data():
    if LOCAL_STORAGE:
        if not os.path.exists(FILE_NAME):
            return []
        with open(FILE_NAME, mode="r", newline="") as file:
            reader = csv.reader(file)
            return list(reader)
    else:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(FILE_NAME)
        if not blob.exists():
            return []
        data = blob.download_as_text()
        reader = csv.reader(io.StringIO(data))
        return list(reader)


def save_data(row):
    row = [str(item) for item in row]
    if LOCAL_STORAGE:
        if not os.path.exists(FILE_NAME):
            rows = []
        else:
            with open(FILE_NAME, mode="r", newline="") as file:
                reader = csv.reader(file)
                rows = list(reader)
        rows.append(row)
        rows.sort(key=lambda r: r[0])
        with open(FILE_NAME, mode="w", newline="") as file:
            writer = csv.writer(file, quoting=csv.QUOTE_MINIMAL)
            writer.writerows(rows)
    else:
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
    if LOCAL_STORAGE:
        if not os.path.exists(FILE_NAME):
            raise ValueError("Data file does not exist.")
        with open(FILE_NAME, mode="r", newline="") as file:
            reader = csv.reader(file)
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
        with open(FILE_NAME, mode="w", newline="") as file:
            writer = csv.writer(file, quoting=csv.QUOTE_MINIMAL)
            writer.writerows(rows)
    else:
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
    if LOCAL_STORAGE:
        with open("last_failed_attempt.txt", "w") as file:
            current_time = datetime.now().isoformat()
            file.write(current_time)
    else:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob("last_failed_attempt.txt")
        current_time = datetime.now().isoformat()
        blob.upload_from_string(current_time)


def get_last_failed_attempt():
    if LOCAL_STORAGE:
        if not os.path.exists("last_failed_attempt.txt"):
            return None
        with open("last_failed_attempt.txt", "r") as file:
            last_attempt = file.read().strip()
        return datetime.fromisoformat(last_attempt)
    else:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob("last_failed_attempt.txt")
        if not blob.exists():
            return None
        last_attempt = blob.download_as_text().strip()
        return datetime.fromisoformat(last_attempt)
