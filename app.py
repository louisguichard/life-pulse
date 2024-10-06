import os
from flask import Flask, session, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
import pytz

from storage import (
    load_data,
    save_data,
    delete_data,
    get_latest_mood,
    log_failed_attempt,
    get_last_failed_attempt,
)
from fitbit import (
    fitbit_login,
    fitbit_callback,
    get_fitbit_data,
)

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY")

# Timezone for Paris
paris_tz = pytz.timezone("Europe/Paris")


def round_to_hour(dt):
    "Rounds datetime to hour."
    if dt.minute >= 30:
        dt += timedelta(hours=1)
    return dt.replace(minute=0, second=0, microsecond=0)


@app.route("/")
def home():
    now = datetime.now(paris_tz)
    current_mood = get_latest_mood()
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
        date = request.form["date"]
        hour = request.form["hour"]
        mood_value = request.form["mood"]
        comment = request.form.get("comment", "")
        date_time = f"{date} - {hour}h"
        save_data([date_time, "Mood", mood_value, comment])
        flash("Mood logged successfully.", "success")
        return redirect(url_for("home"))
    else:
        now = datetime.now(paris_tz)
        current_date = now.strftime("%Y-%m-%d")
        current_hour = now.hour
        return render_template(
            "mood.html", current_date=current_date, current_hour=current_hour
        )


@app.route("/events", methods=["GET", "POST"])
def events():
    if request.method == "POST":
        date = request.form["date"]
        hour = request.form["hour"]
        event = request.form["event"]
        date_time = f"{date} - {hour}h"
        save_data([date_time, "Event", event, ""])
        flash("Event logged successfully.", "success")
        return redirect(url_for("home"))
    else:
        now = datetime.now(paris_tz)
        current_date = now.strftime("%Y-%m-%d")
        current_hour = now.hour
        return render_template(
            "events.html", current_date=current_date, current_hour=current_hour
        )


@app.route("/health", methods=["GET", "POST"])
def health():
    if request.method == "POST":
        date = request.form["date"]
        hour = request.form["hour"]
        condition = request.form["condition"]
        date_time = f"{date} - {hour}h"
        save_data([date_time, "Health", condition, ""])
        flash("Health condition logged successfully.", "success")
        return redirect(url_for("home"))
    else:
        now = datetime.now(paris_tz)
        current_date = now.strftime("%Y-%m-%d")
        current_hour = now.hour
        return render_template(
            "health.html", current_date=current_date, current_hour=current_hour
        )


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
    last_attempt = get_last_failed_attempt()
    if last_attempt and datetime.now() < last_attempt + timedelta(hours=24):
        flash("Try again later.", "error")
        return render_template("home.html")
    if request.method == "POST":
        if request.form["password"] == os.getenv("PASSWORD"):
            session["logged_in"] = True
            return redirect(url_for("history"))
        else:
            log_failed_attempt()
            flash("Invalid password", "error")
            return render_template("home.html")
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
