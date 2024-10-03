from flask import Flask, session, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
import pytz

from storage import load_data, save_data, delete_data
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
    "Rounds datetime to hour." ""
    if dt.minute > 300:
        dt += timedelta(hours=1)
    return dt.replace(minute=0, second=0, microsecond=0)


@app.route("/")
def home():
    now = datetime.now(paris_tz)
    if ("last_fitbit_check" not in session) or (
        now - session["last_fitbit_check"] >= timedelta(days=1)
    ):
        try:
            save_fitbit_data()
            session["last_fitbit_check"] = now
        except ValueError:
            return render_template("home.html", fitbit_required=True)
    return render_template("home.html")


@app.route("/mood", methods=["GET", "POST"])
def mood():
    if request.method == "POST":
        date_time = request.form["datetime"]
        mood_value = request.form["mood"]
        save_data([date_time, "Mood", mood_value])
        return redirect(url_for("home"))
    else:
        current_time = round_to_hour(datetime.now(paris_tz)).strftime("%Y-%m-%dT%H:00")
        return render_template("mood.html", current_time=current_time)


@app.route("/events", methods=["GET", "POST"])
def events():
    if request.method == "POST":
        date_time = request.form["datetime"]
        event = request.form["event"]
        save_data([date_time, "Event", event])
        return redirect(url_for("home"))
    else:
        current_time = round_to_hour(datetime.now(paris_tz)).strftime("%Y-%m-%dT%H:00")
        return render_template("events.html", current_time=current_time)


@app.route("/health", methods=["GET", "POST"])
def health():
    if request.method == "POST":
        date_time = request.form["datetime"]
        condition = request.form["condition"]
        save_data([date_time, "Health", condition])
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
        return render_template("dashboard.html", fitbit_required=True)
    return render_template("dashboard.html", steps=steps, sleep=sleep)


@app.route("/history")
def history():
    data = load_data()
    recent_data = data[::-1][:20]
    return render_template("history.html", data=recent_data)


@app.route("/delete", methods=["POST"])
def delete_record():
    date = request.form.get("date")
    record_type = request.form.get("type")
    value = request.form.get("value")

    if not date or not record_type or not value:
        flash("Invalid data for deletion.")
        return redirect(url_for("history"))

    row = [date, record_type, value]
    try:
        delete_data(row)
        flash("Record deleted successfully.")
    except ValueError as e:
        flash(str(e))

    return redirect(url_for("history"))


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
                save_data([f"{past_date}T00:00", "Sleep", sleep])
            if "Steps" not in existing_types:
                save_data([f"{past_date}T00:00", "Steps", steps])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
