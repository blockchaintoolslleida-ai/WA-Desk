"""
Calendar Template Service — renders reminder message templates with event data.
"""
import re
from datetime import datetime
from typing import Optional


def render_template(
    template: str,
    client_name: str = "",
    event_title: str = "",
    event_date: str = "",
    event_time: str = "",
    event_location: str = "",
    event_description: str = "",
) -> str:
    """Replace template variables with actual values.

    Supported variables:
      {{client_name}}  — contact's display name
      {{event_title}}  — calendar event title/summary
      {{event_date}}   — formatted date (DD/MM/YYYY)
      {{event_time}}   — formatted time (HH:MM)
      {{event_location}} — event location
      {{event_description}} — event description
    """
    result = template

    result = result.replace("{{client_name}}", client_name or "client")

    if event_title:
        result = result.replace("{{event_title}}", event_title)
    else:
        result = re.sub(r"\{\{event_title\}\}", "cita", result)

    result = result.replace("{{event_date}}", event_date or "")
    result = result.replace("{{event_time}}", event_time or "")
    result = result.replace("{{event_location}}", event_location or "")
    result = result.replace("{{event_description}}", event_description or "")

    # Clean up any unreplaced placeholders
    result = re.sub(r"\{\{\w+\}\}", "", result)
    # Collapse multiple spaces
    result = re.sub(r" {2,}", " ", result)
    # Clean up double commas, empty parens
    result = re.sub(r",\s*,", ",", result)
    result = re.sub(r"\(\s*\)", "", result)
    # Clean up leading/trailing whitespace and punctuation artifacts
    result = result.strip().strip(",").strip()

    return result


def format_event_datetime(
    iso_string: Optional[str],
    fmt_date: str = "%d/%m/%Y",
    fmt_time: str = "%H:%M",
) -> tuple:
    """Parse an ISO 8601 datetime string and return (date_str, time_str).

    Returns ("", "") if the string is None or unparseable.
    """
    if not iso_string:
        return "", ""

    try:
        # Handle ISO 8601 with timezone
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime(fmt_date), dt.strftime(fmt_time)
    except (ValueError, AttributeError):
        pass

    # Fallback: try dateutil
    try:
        from dateutil.parser import parse as dt_parse
        dt = dt_parse(iso_string)
        return dt.strftime(fmt_date), dt.strftime(fmt_time)
    except Exception:
        return "", ""


def extract_contact_phone(event: dict) -> Optional[str]:
    """Try to extract a phone number from event description or attendees.

    Looks for patterns like 'tel:34694293833' or 'phone: +34694293833'
    in the event description. Returns the normalized phone or None.
    """
    desc = event.get("description", "") or ""
    # Pattern: tel:XXXXXXXXX or phone: XXXXXXXXX
    import re
    m = re.search(r"(?:tel|phone|telf|telefon)[:\s]*\+?(\d{7,15})", desc, re.IGNORECASE)
    if m:
        return m.group(1)
    return None
