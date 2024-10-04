import os
from flask import Flask, session, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
import pytz
from babel.dates import format_datetime

from storage import load_data, save_data, delete_data, get_latest_mood
from fitbit import (
    fitbit_login,
    fitbit_callback,
    get_fitbit_data,
)

app = Flask(__name__)
app.secret_key = "my_secret_key"

# Timezone for Paris
paris_tz = pytz.timezone("Europe/Paris")


def round_to_hour(dt):
    "Rounds datetime to hour."
    if dt.minute >= 30:
        dt += timedelta(hours=1)
    return dt.replace(minute=0, second=0, microsecond=0)


def format_date_french(date_str):
    """
    Formats a date string from 'YYYY-MM-DDTHH:MM' to 'EEEE d MMMM yyyy - HHh'
    Example: '2024-10-03T16:00' -> 'Jeudi 3 Octobre 2024 - 16h'
    """
    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M")
    dt = paris_tz.localize(dt)
    return format_datetime(dt, "EEEE d MMMM yyyy - HH'h'", locale="fr")


@app.route("/")
def home():
    now = datetime.now(paris_tz)
    current_mood = get_latest_mood()
    current_mood["date_time"] = format_date_french(current_mood["date_time"])
    if ("last_fitbit_check" not in session) or (
        now - session["last_fitbit_check"] >= timedelta(days=1)
    ):
        try:
            save_fitbit_data()
            session["last_fitbit_check"] = now
        except ValueError:
            return render_template(
                "home.html", fitbit_required=True, current_mood=current_mood
            )
    return render_template("home.html", current_mood=current_mood)


@app.route("/mood", methods=["GET", "POST"])
def mood():
    if request.method == "POST":
        date_time = request.form["datetime"]
        mood_value = request.form["mood"]
        comment = request.form.get("comment", "")
        save_data([date_time, "Mood", mood_value, comment])
        return redirect(url_for("home"))
    else:
        current_time = round_to_hour(datetime.now(paris_tz)).strftime("%Y-%m-%dT%H:00")
        return render_template("mood.html", current_time=current_time)


@app.route("/events", methods=["GET", "POST"])
def events():
    if request.method == "POST":
        date_time = request.form["datetime"]
        event = request.form["event"]
        save_data([date_time, "Event", event, ""])
        return redirect(url_for("home"))
    else:
        current_time = round_to_hour(datetime.now(paris_tz)).strftime("%Y-%m-%dT%H:00")
        return render_template("events.html", current_time=current_time)


@app.route("/health", methods=["GET", "POST"])
def health():
    if request.method == "POST":
        date_time = request.form["datetime"]
        condition = request.form["condition"]
        save_data([date_time, "Health", condition, ""])
        return redirect(url_for("home"))
    else:
        current_time = round_to_hour(datetime.now(paris_tz)).strftime("%Y-%m-%dT%H:00")
        return render_template("health.html", current_time=current_time)


# Fitbit routes
app.add_url_rule("/fitbit_login", "fitbit_login", fitbit_login)
app.add_url_rule("/fitbit_callback", "fitbit_callback", fitbit_callback)


@app.route("/dashboard")
def dashboard():
    date = datetime.now(paris_tz).strftime("%Y-%m-%d")
    try:
        steps, sleep = get_fitbit_data(date)
    except ValueError:
        flash("Failed to retrieve Fitbit data.", "error")
        return render_template("dashboard.html", fitbit_required=True)
    return render_template("dashboard.html", steps=steps, sleep=sleep)


@app.route("/history")
def history():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    data = load_data()
    recent_data = data[::-1][:20]
    # Undo date formatting for deletion to work correctly
    # formatted_data = []
    # for row in recent_data:
    # formatted_date = format_date_french(row[0])
    # formatted_row = [formatted_date, row[1], row[2], row[3]]
    # formatted_data.append(formatted_row)
    return render_template("history.html", data=recent_data)


@app.route("/delete", methods=["POST"])
def delete_record():
    date = request.form.get("date")
    record_type = request.form.get("type")
    value = request.form.get("value")
    comment = request.form.get("comment")
    row = [date, record_type, value, comment]
    try:
        delete_data(row)
        flash("Record deleted successfully.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("history"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["password"] == os.getenv("PASSWORD"):
            session["logged_in"] = True
            return redirect(url_for("history"))
        else:
            flash("Invalid password", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("home"))


def save_fitbit_data():
    "Saves Fitbit data for the past 7 days if not already saved"

    # Load existing data
    data = load_data()

    # Days to check
    date = datetime.now(paris_tz) - timedelta(hours=6)
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
