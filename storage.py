import csv
from google.cloud import storage
from datetime import datetime


PROJECT_ID = "louisguichard"
BUCKET_NAME = "life_pulse"
FILE_NAME = "data.csv"

storage_client = storage.Client(project=PROJECT_ID)


def load_data():
    """
    Loads data from the CSV file.

    Returns:
        list: A list of rows, where each row is a list of fields.
    """
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(FILE_NAME)
    if not blob.exists():
        return []
    data = blob.download_as_text()
    reader = csv.reader(data.strip().split("\n"))
    return list(reader)


def save_data(row):
    """
    Adds a row to the CSV file.

    Args:
        row (list): The row to save, e.g., [date_time, type, value, comment].
    """
    row = [str(item) for item in row]
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(FILE_NAME)
    if not blob.exists():
        rows = []
    else:
        data = blob.download_as_text()
        rows = data.strip().split("\n")
    rows.append(",".join(row))
    rows = sorted(rows, key=lambda row: row.split(",")[0])
    blob.upload_from_string("\n".join(rows))


def delete_data(target_row):
    """
    Deletes a specific row from the CSV file.

    Args:
        target_row (list): The row to delete, e.g., [date_time, type, value, comment].

    Raises:
        ValueError: If the row is not found.
    """
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(FILE_NAME)
    if not blob.exists():
        raise ValueError("Data file does not exist.")

    data = blob.download_as_text().strip().split("\n")
    rows = [row.split(",") for row in data]

    # Find the row to delete
    initial_length = len(rows)
    for i in range(len(rows)):
        if rows[i] == target_row:
            del rows[i]
            break
    if len(rows) == initial_length:
        raise ValueError("Record not found.")

    # Sort and save back
    rows = sorted(rows, key=lambda row: row[0])
    blob.upload_from_string("\n".join([",".join(row) for row in rows]))


def get_latest_mood():
    """
    Retrieves the most recent Mood entry from the data.

    Returns:
        dict or None: A dictionary with 'date_time', 'value', and 'comment' if found, else None.
    """
    data = load_data()
    # Filter for 'Mood' entries
    mood_entries = [row for row in data if row[1] == "Mood"]
    if not mood_entries:
        return None
    # Sort by date_time descending
    mood_entries.sort(
        key=lambda x: datetime.strptime(x[0], "%Y-%m-%dT%H:%M"), reverse=True
    )
    latest = mood_entries[0]
    return {"date_time": latest[0], "value": latest[2], "comment": latest[3]}


def log_failed_attempt():
    """
    Logs the current timestamp as a failed login attempt.
    """
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob("last_failed_attempt.txt")
    current_time = datetime.now().isoformat()
    blob.upload_from_string(current_time)


def get_last_failed_attempt():
    """
    Retrieves the timestamp of the last failed login attempt.

    Returns:
        datetime or None: The datetime of the last failed attempt, or None if not found.
    """
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob("last_failed_attempt.txt")
    if not blob.exists():
        return None
    last_attempt = blob.download_as_text().strip()
    return datetime.fromisoformat(last_attempt)
