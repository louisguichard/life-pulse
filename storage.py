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
    print(rows)
    rows = sorted(rows, key=lambda row: row.split(",")[0])
    blob.upload_from_string("\n".join(rows))
