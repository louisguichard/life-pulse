import csv
from google.cloud import storage


PROJECT_ID = "louisguichard"
BUCKET_NAME = "life_pulse"
FILE_NAME = "data.csv"

storage_client = storage.Client(project=PROJECT_ID)


def load_data():
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(FILE_NAME)
    if not blob.exists():
        return []
    data = blob.download_as_text()
    reader = csv.reader(data.strip().split("\n"))
    return list(reader)


def save_data(row):
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
        target_row (list): The row to delete, e.g., [date, type, value].

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
    rows = [row for row in rows if row != target_row]

    if len(rows) == initial_length:
        raise ValueError("Record not found.")

    # Sort and save back
    rows = sorted(rows, key=lambda row: row[0])
    blob.upload_from_string("\n".join([",".join(row) for row in rows]))
