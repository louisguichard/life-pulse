import os
from flask import (
    Flask,
    session,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    make_response,
)
from datetime import datetime, timedelta
import pytz
import time
import functools
from dotenv import load_dotenv
from storage import (
    load_config,
    load_data,
    save_data,
    delete_data,
    get_latest_mood,
    log_failed_attempt,
    get_last_failed_attempt,
)
from fitbit import fitbit_login, fitbit_callback, get_fitbit_data, save_fitbit_data

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "secret_key")

# Timezone for Paris
paris_tz = pytz.timezone("Europe/Paris")

# Load config
config_path = os.getenv("CONFIG_PATH", "config.json")
config = load_config(config_path)


# Login verification decorator
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        auth_cookie = request.cookies.get("auth_token")
        password = os.getenv("PASSWORD")
        if auth_cookie and auth_cookie == password:
            return f(*args, **kwargs)
        return redirect(url_for("login", next=request.url))

    return decorated_function


@app.route("/")
@login_required
def home():
    current_mood = get_latest_mood()
    return render_template(
        "home.html", current_mood=current_mood, enable_feedback=app.debug
    )


@app.route("/mood", methods=["GET", "POST"])
@login_required
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
        mood_config = config.get("moods", {})
        return render_template(
            "mood.html",
            current_date=current_date,
            current_hour=current_hour,
            moods=mood_config,
        )


@app.route("/events", methods=["GET", "POST"])
@login_required
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
        events = config.get("events", {})
        return render_template(
            "events.html",
            current_date=current_date,
            current_hour=current_hour,
            events=events,
        )


@app.route("/health", methods=["GET", "POST"])
@login_required
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
        events = config.get("health", {})
        return render_template(
            "health.html",
            current_date=current_date,
            current_hour=current_hour,
            events=events,
        )


@app.route("/dashboard")
@login_required
def dashboard():
    if not all([os.getenv("FITBIT_CLIENT_ID"), os.getenv("FITBIT_CLIENT_SECRET")]):
        flash("Fitbit is not configured.", "error")
        return redirect(url_for("home"))
    now = datetime.now(paris_tz)
    try:
        if ("last_fitbit_check" not in session) or (
            now - session["last_fitbit_check"] >= timedelta(days=1)
        ):
            save_fitbit_data(timezone=paris_tz)
            session["last_fitbit_check"] = now
        steps, sleep = get_fitbit_data(now.strftime("%Y-%m-%d"))
    except ValueError:
        return render_template("dashboard.html", fitbit_required=True)
    return render_template("dashboard.html", steps=steps, sleep=sleep)


@app.route("/history")
@login_required
def history():
    data = load_data()[::-1]
    show_all = request.args.get("show_all") == "true"
    if show_all:
        recent_data = data
    else:
        recent_data = data[:20]
    return render_template("history.html", data=recent_data)


@app.route("/delete", methods=["POST"])
@login_required
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
    password = os.getenv("PASSWORD")
    if not password:
        return redirect(url_for("home"))
    last_attempt = get_last_failed_attempt()
    if last_attempt and datetime.now() < last_attempt + timedelta(hours=24):
        flash("Try again later.", "error")
    if request.method == "POST":
        if request.form["password"] == password:
            next_page = request.args.get("next", url_for("history"))
            response = make_response(redirect(next_page))
            expires = datetime.now() + timedelta(days=365 * 2)  # 2 years expiration
            response.set_cookie(
                "auth_token",
                password,
                expires=expires,
                httponly=True,
                secure=not app.debug,
                samesite="Lax",
            )

            return response
        else:
            log_failed_attempt()
            flash("Invalid password", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    response = make_response(redirect(url_for("home")))
    response.delete_cookie("auth_token")
    return response


# Fitbit routes
app.add_url_rule("/fitbit_login", "fitbit_login", fitbit_login)
app.add_url_rule("/fitbit_callback", "fitbit_callback", fitbit_callback)


@app.route("/feedback", methods=["POST"])
def feedback():
    feedback_type = request.json.get("type")
    message = request.json.get("message", "")

    if feedback_type == "good":
        print("\n--- SUCCESS: User feedback is good! ---\n")
        time.sleep(0.5)  # Brief delay to ensure response is sent
        os._exit(0)
    elif feedback_type == "issue":
        print(f"\n--- ERROR: User reported an issue: {message} ---\n")
        time.sleep(0.5)  # Brief delay to ensure response is sent
        os._exit(1)

    return {"status": "error", "message": "Invalid feedback type"}


if __name__ == "__main__":
    # Set debug mode based on APP_ENV
    app.debug = os.getenv("APP_ENV", "local").lower() == "local"
    app.run(host="0.0.0.0", port=8080)
