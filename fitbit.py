import os
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
from flask import request, session, redirect, url_for
from urllib.parse import urlencode

from storage import load_data, save_data

load_dotenv()
SCHEME = "http" if os.getenv("APP_ENV", "local") == "local" else "https"
FITBIT_CLIENT_ID = os.getenv("FITBIT_CLIENT_ID")
FITBIT_CLIENT_SECRET = os.getenv("FITBIT_CLIENT_SECRET")


def fitbit_login():
    redirect_uri = url_for("fitbit_callback", _external=True, _scheme=SCHEME)
    scope = "activity sleep heartrate weight"
    params = {
        "response_type": "code",
        "client_id": FITBIT_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": scope,
    }
    auth_url = "https://www.fitbit.com/oauth2/authorize?" + urlencode(params)
    return redirect(auth_url)


def fitbit_callback():
    code = request.args.get("code")
    if not code:
        return "Error: Missing authorization code"

    redirect_uri = url_for("fitbit_callback", _external=True, _scheme=SCHEME)

    # Exchange code for access token
    token_url = "https://api.fitbit.com/oauth2/token"
    data = {
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code": code,
    }
    auth_header = HTTPBasicAuth(FITBIT_CLIENT_ID, FITBIT_CLIENT_SECRET)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(token_url, data=data, auth=auth_header, headers=headers)
    token_info = response.json()

    if response.status_code != 200:
        error_message = token_info.get("errors", [{"message": "Unknown error"}])[0][
            "message"
        ]
        return f"Error: {error_message}"

    # Save tokens in session
    session["fitbit_access_token"] = token_info["access_token"]
    session["fitbit_refresh_token"] = token_info["refresh_token"]
    session["fitbit_expires_at"] = (
        datetime.utcnow() + timedelta(seconds=token_info["expires_in"])
    ).isoformat()

    return redirect(url_for("home"))


def refresh_fitbit_token():
    refresh_token = session.get("fitbit_refresh_token")
    if not refresh_token:
        return False

    token_url = "https://api.fitbit.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    auth_header = HTTPBasicAuth(FITBIT_CLIENT_ID, FITBIT_CLIENT_SECRET)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(token_url, data=data, auth=auth_header, headers=headers)
    token_info = response.json()

    if response.status_code != 200:
        return False

    # Update tokens in session
    session["fitbit_access_token"] = token_info["access_token"]
    session["fitbit_refresh_token"] = token_info["refresh_token"]
    session["fitbit_expires_at"] = (
        datetime.utcnow() + timedelta(seconds=token_info["expires_in"])
    ).isoformat()
    return True


def get_fitbit_data(date):
    access_token = session.get("fitbit_access_token")
    if not access_token:
        raise ValueError("Fitbit connection is required.")

    expires_at_str = session.get("fitbit_expires_at")
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
    else:
        expires_at = datetime.utcnow()

    if datetime.utcnow() >= expires_at:
        if not refresh_fitbit_token():
            raise ValueError("Unable to refresh access token.")
        access_token = session.get("fitbit_access_token")

    headers = {"Authorization": f"Bearer {access_token}"}

    # Get steps data
    activity_url = f"https://api.fitbit.com/1/user/-/activities/date/{date}.json"
    activity_response = requests.get(activity_url, headers=headers)
    if activity_response.status_code != 200:
        raise ConnectionError(
            f"Activity API Error: {activity_response.status_code} {activity_response.text}"
        )
    steps = activity_response.json().get("summary", {}).get("steps", 0)

    # Get sleep data
    sleep_url = f"https://api.fitbit.com/1.2/user/-/sleep/date/{date}.json"
    sleep_response = requests.get(sleep_url, headers=headers)
    if sleep_response.status_code != 200:
        raise ConnectionError(
            f"Sleep API Error: {sleep_response.status_code} {sleep_response.text}"
        )
    sleep_data = sleep_response.json()
    total_minutes_asleep = sleep_data.get("summary", {}).get("totalMinutesAsleep", 0)
    sleep_hours = total_minutes_asleep / 60

    return steps, sleep_hours


def save_fitbit_data(timezone):
    "Saves Fitbit data for the past 7 days if not already saved"

    # Load existing data
    data = load_data()

    # Days to check
    date = datetime.now(timezone) - timedelta(hours=6)
    dates_to_check = [
        (date - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 8)
    ]

    # Check and retrieve missing data
    for past_date in dates_to_check:
        existing_data = [entry for entry in data if entry[0][:10] == past_date]
        existing_types = [entry[1] for entry in existing_data]
        fitbit_types = ["Sleep", "Steps"]
        if any([data_type not in existing_types for data_type in fitbit_types]):
            steps, sleep = get_fitbit_data(past_date)
            if "Sleep" not in existing_types:
                save_data([f"{past_date}T00:00", "Sleep", sleep, ""])
            if "Steps" not in existing_types:
                save_data([f"{past_date}T00:00", "Steps", steps, ""])
