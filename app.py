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
import functools
from dotenv import load_dotenv
from googleapiclient.discovery import build
from werkzeug.middleware.proxy_fix import ProxyFix

from utils.storage import (
    load_config,
    load_data,
    save_data,
    delete_data,
    get_latest_mood,
    log_failed_attempt,
    get_last_failed_attempt,
)
from utils.fitbit import (
    fitbit_login,
    fitbit_callback,
    get_fitbit_data,
    save_fitbit_data,
)
from utils.calendar_api import (
    calendar_login,
    calendar_callback,
    get_weekly_summary,
    get_calendar_events,
    get_credentials,
)
from feedback import FeedbackSystem

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "secret_key")
app.debug = os.getenv("APP_ENV", "local").lower() == "local"
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


# Timezone for Paris
paris_tz = pytz.timezone("Europe/Paris")

# Load config
config_path = os.getenv("CONFIG_PATH", "config.json")
config = load_config(config_path)

# Initialize the feedback system
feedback_system = FeedbackSystem(exit_on_feedback=True)
feedback_system.init_app(app, enable_in_debug=True, enable_in_prod=False)


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
    return render_template("home.html", current_mood=current_mood)


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


# Utility functions for formatting time displays
def format_hours_to_int(dict_obj):
    """Format decimal hours to integer hours"""
    if isinstance(dict_obj, dict):
        return {k: format_hours_to_int(v) for k, v in dict_obj.items()}
    elif isinstance(dict_obj, float):
        return int(round(dict_obj))
    else:
        return dict_obj


def format_sleep_time(hours):
    """Format sleep time from decimal hours to hours and minutes (e.g., 7h45)"""
    hours_int = int(hours)
    minutes = int((hours - hours_int) * 60)
    return f"{hours_int}h{minutes:02d}"


@app.route("/dashboard")
@login_required
def dashboard():
    fitbit_configured = all(
        [os.getenv("FITBIT_CLIENT_ID"), os.getenv("FITBIT_CLIENT_SECRET")]
    )
    calendar_configured = all(
        [os.getenv("CALENDAR_CLIENT_ID"), os.getenv("CALENDAR_CLIENT_SECRET")]
    )

    # Check if calendar authentication is required
    calendar_events = None
    calendar_auth_required = False
    weekly_summary = None

    if calendar_configured:
        calendar_events = get_calendar_events()
        if calendar_events is None:
            calendar_auth_required = True
        else:
            # Get weekly summary for categories
            credentials = get_credentials()
            service = build("calendar", "v3", credentials=credentials)
            weekly_summary = get_weekly_summary(service)

    # Check if Fitbit authentication is required
    steps = None
    sleep = None
    fitbit_auth_required = False

    if fitbit_configured:
        now = datetime.now(paris_tz)
        try:
            if ("last_fitbit_check" not in session) or (
                now - session["last_fitbit_check"] >= timedelta(days=1)
            ):
                save_fitbit_data(timezone=paris_tz)
                session["last_fitbit_check"] = now
            steps, sleep = get_fitbit_data(now.strftime("%Y-%m-%d"))
            # Format sleep time as hours and minutes
            if sleep is not None:
                sleep = format_sleep_time(sleep)
        except ValueError:
            fitbit_auth_required = True

    # Apply integer hours formatting to weekly_summary data
    if weekly_summary:
        weekly_summary = format_hours_to_int(weekly_summary)

    return render_template(
        "dashboard.html",
        steps=steps,
        sleep=sleep,
        events=calendar_events,
        weekly_summary=weekly_summary,
        fitbit_required=fitbit_auth_required,
        calendar_required=calendar_auth_required,
    )


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

# Calendar routes
app.add_url_rule("/calendar_login", "calendar_login", calendar_login)
app.add_url_rule("/calendar_callback", "calendar_callback", calendar_callback)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
