import os
import datetime
from dateutil.parser import parse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from flask import request, session, redirect, url_for, flash
from storage import load_config

# Set OAUTHLIB_INSECURE_TRANSPORT for local development
if os.getenv("APP_ENV", "local") == "local":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

SCHEME = "http" if os.getenv("APP_ENV", "local") == "local" else "https"
CALENDAR_CLIENT_ID = os.getenv("CALENDAR_CLIENT_ID")
CALENDAR_CLIENT_SECRET = os.getenv("CALENDAR_CLIENT_SECRET")


# Create OAuth flow
def create_flow(redirect_uri):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CALENDAR_CLIENT_ID,
                "client_secret": CALENDAR_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    )
    flow.redirect_uri = redirect_uri
    return flow


def calendar_login():
    redirect_uri = url_for("calendar_callback", _external=True, _scheme=SCHEME)
    flow = create_flow(redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    session["calendar_state"] = state
    return redirect(authorization_url)


def calendar_callback():
    redirect_uri = url_for("calendar_callback", _external=True, _scheme=SCHEME)
    try:
        flow = create_flow(redirect_uri)
        flow.fetch_token(authorization_response=request.url)

        # Store credentials in the session
        credentials = flow.credentials
        session["calendar_credentials"] = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }
        flash("Successfully connected to Google Calendar", "success")
        return redirect(url_for("dashboard"))
    except Exception as e:
        flash(f"Authorization failed: {str(e)}", "error")
        return redirect(url_for("dashboard"))


def get_credentials():
    if "calendar_credentials" not in session:
        return None

    credentials_info = session["calendar_credentials"]

    if credentials_info.get("expiry") and isinstance(credentials_info["expiry"], str):
        credentials_info["expiry"] = parse(credentials_info["expiry"])

    return Credentials(
        token=credentials_info["token"],
        refresh_token=credentials_info["refresh_token"],
        token_uri=credentials_info["token_uri"],
        client_id=credentials_info["client_id"],
        client_secret=credentials_info["client_secret"],
        scopes=credentials_info["scopes"],
        expiry=credentials_info.get("expiry"),
    )


def get_calendar_events():
    credentials = get_credentials()
    if not credentials:
        return None

    service = build("calendar", "v3", credentials=credentials)

    # Get the start and end dates for the current week
    now = datetime.datetime.utcnow()
    start_of_week = now - datetime.timedelta(days=now.weekday())
    start_of_week = (
        start_of_week.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        + "Z"
    )
    end_of_week = now + datetime.timedelta(days=6 - now.weekday())
    end_of_week = (
        end_of_week.replace(
            hour=23, minute=59, second=59, microsecond=999999
        ).isoformat()
        + "Z"
    )

    try:
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_of_week,
                timeMax=end_of_week,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        formatted_events = []
        for event in events:
            start = event.get("start", {}).get(
                "dateTime", event.get("start", {}).get("date")
            )
            end = event.get("end", {}).get("dateTime", event.get("end", {}).get("date"))

            # Format dates
            if "T" in start:  # This is a dateTime
                start_dt = parse(start)
                end_dt = parse(end)
                duration = (end_dt - start_dt).total_seconds() / 3600  # Hours
                start_formatted = start_dt.strftime("%Y-%m-%d %H:%M")
            else:  # This is a date (all-day event)
                start_dt = parse(start)
                start_formatted = start_dt.strftime("%Y-%m-%d (all day)")
                duration = 24  # All day

            formatted_events.append(
                {
                    "title": event.get("summary", "(No title)"),
                    "start": start_formatted,
                    "duration": duration,
                    "raw_start": start,  # Keep the raw date for sorting
                }
            )

        # Sort events by start time
        formatted_events.sort(key=lambda x: x["raw_start"])

        return formatted_events
    except Exception as e:
        print(f"Error fetching calendar events: {e}")
        return None


def get_week_time_range(weeks_ago=0):
    """
    Returns the ISO formatted start and end dates for a specific week.
    weeks_ago=0 means current week, weeks_ago=1 means last week, etc.
    """
    now = datetime.datetime.utcnow()

    # Calculate the start of the week (Monday)
    start_of_week = now - datetime.timedelta(days=now.weekday() + (7 * weeks_ago))
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

    # Calculate the end of the week (Sunday)
    end_of_week = start_of_week + datetime.timedelta(days=6)
    end_of_week = end_of_week.replace(hour=23, minute=59, second=59, microsecond=999999)

    return start_of_week.isoformat() + "Z", end_of_week.isoformat() + "Z"


def get_events_summary(
    service, time_min, time_max, config_categories, current_time=None
):
    """
    Process calendar events for a given time period and return category summaries.
    Only considers events that are at least 1 hour long.
    """
    try:
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        # If no events found, return empty summary
        if not events:
            return {
                "categories": {
                    category: {"completed": 0, "scheduled": 0, "total": 0}
                    for category in config_categories.keys()
                },
                "events_by_category": {
                    category: [] for category in config_categories.keys()
                },
                "total": {"completed": 0, "scheduled": 0, "total": 0},
            }

        # Initialize hours for each category
        summary = {
            category: {"completed": 0, "scheduled": 0, "total": 0}
            for category in config_categories.keys()
        }
        summary["Other"] = {"completed": 0, "scheduled": 0, "total": 0}

        # Track events by category
        events_by_category = {category: [] for category in config_categories.keys()}
        events_by_category["Other"] = []

        # Totals for all categories excluding "Other"
        total_summary = {"completed": 0, "scheduled": 0, "total": 0}

        # Count hours for each category
        for event in events:
            start = event.get("start", {}).get(
                "dateTime", event.get("start", {}).get("date")
            )
            end = event.get("end", {}).get("dateTime", event.get("end", {}).get("date"))
            title = event.get("summary", "")

            # Skip all-day events
            if "T" not in start:
                continue

            # Calculate event duration
            start_dt = parse(start)
            end_dt = parse(end)

            # Make sure datetime objects are timezone-aware for comparison
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=datetime.timezone.utc)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)

            duration = (end_dt - start_dt).total_seconds() / 3600  # Hours

            # Skip events shorter than 1 hour
            if duration < 1:
                continue

            # Determine if the event is completed
            is_completed = False
            if current_time:
                current_time_utc = current_time.replace(tzinfo=datetime.timezone.utc)
                is_completed = end_dt <= current_time_utc

            # Assign to category based on keywords from config
            category_found = False
            for category, category_data in config_categories.items():
                keywords = category_data.get("keywords", [])
                if any(keyword.lower() in title.lower() for keyword in keywords):
                    # Add to total hours for all events
                    summary[category]["total"] += duration

                    # Now "scheduled" means all events of the week (no longer future events)
                    summary[category]["scheduled"] += duration

                    # "completed" remains only completed events
                    if is_completed:
                        summary[category]["completed"] += duration

                    # Add to events list for this category
                    events_by_category[category].append(
                        {
                            "title": title,
                            "start": start_dt.strftime("%A")
                            if "T" in start
                            else start_dt.strftime("%A (all day)"),
                            "duration": duration,
                            "is_completed": is_completed,
                        }
                    )

                    category_found = True
                    break

            if not category_found:
                summary["Other"]["total"] += duration
                summary["Other"]["scheduled"] += duration
                if is_completed:
                    summary["Other"]["completed"] += duration

                events_by_category["Other"].append(
                    {
                        "title": title,
                        "start": start_dt.strftime("%A")
                        if "T" in start
                        else start_dt.strftime("%A (all day)"),
                        "duration": duration,
                        "is_completed": is_completed,
                    }
                )

        # Calculate totals for all categories excluding "Other"
        for category, data in summary.items():
            if category != "Other":
                total_summary["total"] += data["total"]
                total_summary["completed"] += data["completed"]
                total_summary["scheduled"] += data["scheduled"]

        return {
            "categories": summary,
            "events_by_category": events_by_category,
            "total": total_summary,
        }
    except Exception as e:
        print(f"Error processing events: {e}")
        # Return empty summaries
        return {
            "categories": {
                category: {"completed": 0, "scheduled": 0, "total": 0}
                for category in config_categories.keys()
            },
            "events_by_category": {
                category: [] for category in config_categories.keys()
            },
            "total": {"completed": 0, "scheduled": 0, "total": 0},
        }


def get_weekly_summary(service):
    """
    Gets a summary of calendar events for the current and previous week, grouped by category.

    Args:
        service: Google Calendar API service instance.

    Returns:
        Dictionary with event categories as keys and hours as values, or None if error.
    """
    # Load categories from config
    config_path = os.getenv("CONFIG_PATH", "config.json")
    config = load_config(config_path)
    config_categories = config.get("calendar_events", {})

    # Extract targets from config
    target_hours = {
        category: data.get("target", 0) for category, data in config_categories.items()
    }
    target_hours["Other"] = 0

    # Get current time for determining completed events
    current_time = datetime.datetime.utcnow()

    # Get current week time range
    curr_week_start, curr_week_end = get_week_time_range(weeks_ago=0)

    # Get last week time range
    prev_week_start, prev_week_end = get_week_time_range(weeks_ago=1)

    # Get summaries for current week
    curr_week_summary = get_events_summary(
        service, curr_week_start, curr_week_end, config_categories, current_time
    )

    # Get summaries for previous week (all events are completed)
    prev_week_summary = get_events_summary(
        service, prev_week_start, prev_week_end, config_categories
    )

    # Calculate total target hours (excluding "Other")
    total_target = sum(
        hours for category, hours in target_hours.items() if category != "Other"
    )

    # Return formatted response
    return {
        "projected_week": curr_week_summary["categories"],
        "previous_week": {
            category: data["total"]
            for category, data in prev_week_summary["categories"].items()
        },
        "curr_week_events": curr_week_summary["events_by_category"],
        "targets": target_hours,
        "total": {
            "current_week": curr_week_summary["total"],
            "previous_week": prev_week_summary["total"]["total"],
            "target": total_target,
        },
    }
