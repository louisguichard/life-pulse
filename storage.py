import csv
from google.cloud import storage
from datetime import datetime
import io


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
    reader = csv.reader(io.StringIO(data))
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
        reader = csv.reader(io.StringIO(data))
        rows = list(reader)
    rows.append(row)
    rows.sort(key=lambda r: r[0])
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerows(rows)
    blob.upload_from_string(output.getvalue())


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

    # Sort the remaining rows by date_time
    rows.sort(key=lambda r: r[0])

    # Write the updated rows back to the CSV
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerows(rows)
    blob.upload_from_string(output.getvalue())


def get_latest_mood():
    """
    Retrieves the most recent Mood entry from the data.

    Returns:
        dict or None: A dictionary with 'date_time', 'value', and 'comment' if found, else None.
    """
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
