"""
Calendar Watcher Service — polls Google Calendar for upcoming events
and schedules WhatsApp reminders via the message sender.
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta

from database import get_supabase_admin
from config import GOOGLE_POLLING_INTERVAL_MINUTES
from services.secrets_manager import decrypt_value
from services.calendar_templates import (
    render_template,
    format_event_datetime,
    extract_contact_phone,
)
from services.whatsapp import send_whatsapp_message, normalize_phone
from models import WhatsAppOutboundMessage

logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────

async def _build_credentials(tenant_id: str):
    """Build Google Credentials from the stored refresh token for a tenant.

    Returns google.oauth2.credentials.Credentials or None.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        logger.error("google-auth-oauthlib not installed")
        return None

    sb = get_supabase_admin()
    row = (
        sb.table("oauth_tokens")
        .select("encrypted_access_token, calendar_email")
        .eq("tenant_id", tenant_id)
        .eq("service", "google_calendar")
        .limit(1)
        .execute()
    )
    if not row.data:
        return None

    encrypted = row.data[0].get("encrypted_access_token", "")
    if not encrypted:
        return None

    refresh_token = decrypt_value(encrypted)
    if not refresh_token:
        return None

    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        logger.error("GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not configured")
        return None

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )

    # Refresh the access token
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, creds.refresh, Request())
        return creds
    except Exception as e:
        logger.error(f"Failed to refresh Google token for tenant {tenant_id}: {e}")
        return None


async def _fetch_upcoming_events(credentials, calendar_id: str, hours_ahead: int = 72) -> list:
    """Fetch upcoming events from Google Calendar within the next `hours_ahead` hours."""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        logger.error("google-api-python-client not installed")
        return []

    loop = asyncio.get_running_loop()

    def _do_fetch():
        service = build("calendar", "v3", credentials=credentials)
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(hours=hours_ahead)

        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=now.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=50,
            )
            .execute()
        )
        return events_result.get("items", [])

    try:
        return await loop.run_in_executor(None, _do_fetch)
    except Exception as e:
        logger.error(f"Google Calendar API error: {e}")
        return []


# ── Watcher Service ─────────────────────────────────────────────

class CalendarWatcherService:
    """Background service that polls Google Calendar and sends WhatsApp reminders."""

    def __init__(self):
        self._running = False

    async def start(self):
        """Start the background polling loop."""
        self._running = True
        interval_seconds = GOOGLE_POLLING_INTERVAL_MINUTES * 60
        logger.info(
            f"CalendarWatcher started — polling every {GOOGLE_POLLING_INTERVAL_MINUTES} min"
        )

        while self._running:
            try:
                await self._poll_all_tenants()
            except Exception as e:
                logger.error(f"CalendarWatcher error: {e}")
            await asyncio.sleep(interval_seconds)

    async def _poll_all_tenants(self):
        """Poll all tenants with active calendar connections."""
        sb = get_supabase_admin()

        # Find tenants with Google Calendar tokens and active reminder settings
        tokens = (
            sb.table("oauth_tokens")
            .select("tenant_id, calendar_email, calendar_id")
            .eq("service", "google_calendar")
            .execute()
        )

        if not tokens.data:
            return

        for token_row in tokens.data:
            tenant_id = token_row["tenant_id"]
            try:
                await self._poll_tenant(
                    tenant_id=tenant_id,
                    calendar_id=token_row.get("calendar_id", "primary"),
                )
            except Exception as e:
                logger.error(
                    f"Error polling tenant {tenant_id}: {e}", exc_info=True
                )

    async def _poll_tenant(self, tenant_id: str, calendar_id: str):
        """Poll a single tenant's calendar and process events."""
        sb = get_supabase_admin()

        # Check if reminders are active for this tenant
        settings = (
            sb.table("reminder_settings")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("is_active", 1)
            .limit(1)
            .execute()
        )
        if not settings.data:
            return

        settings = settings.data[0]
        lead_time_hours = settings.get("lead_time_hours", 24)
        template_text = settings.get("template_text", "")

        # Build credentials
        creds = await _build_credentials(tenant_id)
        if not creds:
            return

        # Fetch events (look ahead = lead_time + 72h safety window)
        lookup_window = max(lead_time_hours + 72, 96)
        events = await _fetch_upcoming_events(creds, calendar_id, lookup_window)

        now = datetime.now(timezone.utc)

        for event in events:
            await self._process_event(
                tenant_id=tenant_id,
                event=event,
                lead_time_hours=lead_time_hours,
                template_text=template_text,
                now=now,
            )

    async def _process_event(
        self,
        tenant_id: str,
        event: dict,
        lead_time_hours: int,
        template_text: str,
        now: datetime,
    ):
        """Process a single calendar event: schedule or send reminder."""
        sb = get_supabase_admin()
        event_id = event.get("id", "")

        if not event_id:
            return

        # Check if already processed
        existing = (
            sb.table("reminder_log")
            .select("id, status")
            .eq("tenant_id", tenant_id)
            .eq("google_event_id", event_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return  # Already handled

        # Get event start time
        start_info = event.get("start", {})
        start_iso = start_info.get("dateTime") or start_info.get("date")
        if not start_iso:
            return

        try:
            # Handle all-day events
            if "T" not in start_iso:
                start_dt = datetime.fromisoformat(f"{start_iso}T00:00:00+00:00")
            else:
                start_dt = datetime.fromisoformat(
                    start_iso.replace("Z", "+00:00")
                )
        except ValueError:
            return

        # Calculate when to send the reminder
        scheduled_for = start_dt - timedelta(hours=lead_time_hours)

        # If reminder time has already passed and it's still before the event,
        # send immediately (or schedule for 1 minute from now)
        if scheduled_for <= now:
            if now < start_dt:
                scheduled_for = now + timedelta(minutes=1)
            else:
                return  # Event already started, skip

        # Extract contact info
        event_title = event.get("summary", "Sense titol")
        client_name = event.get("summary", "")[:50]
        contact_phone = extract_contact_phone(event)

        # Try to get contact name from attendees or description
        attendees = event.get("attendees", [])
        if attendees:
            for att in attendees:
                display = att.get("displayName", "")
                email_addr = att.get("email", "")
                if display and "organizer" not in att.get("responseStatus", ""):
                    client_name = display
                    break
                elif email_addr and "@" in email_addr:
                    # Use email local part as fallback name
                    client_name = email_addr.split("@")[0]

        event_date_str, event_time_str = format_event_datetime(start_iso)

        # Insert reminder into log
        log_id = str(uuid.uuid4())
        now_iso = now.isoformat()
        log_entry = {
            "id": log_id,
            "tenant_id": tenant_id,
            "contact_phone": contact_phone or "",
            "google_event_id": event_id,
            "event_title": event_title,
            "event_start": start_iso,
            "scheduled_for": scheduled_for.isoformat(),
            "status": "pending",
            "retry_count": 0,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        sb.table("reminder_log").insert(log_entry).execute()

        # If scheduled_for is very soon (within 2 minutes), send it now
        if (scheduled_for - now).total_seconds() < 120:
            await self._send_reminder(log_id, tenant_id, contact_phone,
                                      event_title, event_date_str, event_time_str,
                                      client_name, template_text)

        logger.info(
            f"Reminder scheduled: event='{event_title}' at {event_date_str} {event_time_str} "
            f"send at {scheduled_for.isoformat()} for tenant {tenant_id}"
        )

    async def _send_due_reminders(self):
        """Send all pending reminders whose scheduled_for has passed."""
        sb = get_supabase_admin()
        now = datetime.now(timezone.utc)

        # Get all pending reminders ready to send
        pending = (
            sb.table("reminder_log")
            .select("*")
            .eq("status", "pending")
            .lte("scheduled_for", now.isoformat())
            .execute()
        )

        for entry in (pending.data or []):
            # Get tenant settings for template
            settings = (
                sb.table("reminder_settings")
                .select("template_text")
                .eq("tenant_id", entry["tenant_id"])
                .limit(1)
                .execute()
            )
            template = (
                settings.data[0].get("template_text", "")
                if settings.data
                else ""
            )

            event_date_str, event_time_str = format_event_datetime(
                entry.get("event_start")
            )

            await self._send_reminder(
                log_id=entry["id"],
                tenant_id=entry["tenant_id"],
                contact_phone=entry.get("contact_phone", ""),
                event_title=entry.get("event_title", ""),
                event_date_str=event_date_str,
                event_time_str=event_time_str,
                client_name=entry.get("event_title", "")[:50],
                template_text=template,
            )

    async def _send_reminder(
        self,
        log_id: str,
        tenant_id: str,
        contact_phone: str,
        event_title: str,
        event_date_str: str,
        event_time_str: str,
        client_name: str,
        template_text: str,
    ):
        """Send a single reminder via WhatsApp and update the log."""
        sb = get_supabase_admin()

        if not contact_phone:
            self._update_log(log_id, "failed", "No contact phone found")
            return

        body = render_template(
            template=template_text,
            client_name=client_name,
            event_title=event_title,
            event_date=event_date_str,
            event_time=event_time_str,
        )

        if not body.strip():
            body = (
                f"Hola {client_name}, le recordamos su cita: {event_title} "
                f"el dia {event_date_str} a las {event_time_str}."
            )

        try:
            wa_result = await send_whatsapp_message(
                WhatsAppOutboundMessage(
                    phone=normalize_phone(contact_phone),
                    body=body,
                ),
                tenant_id=tenant_id,
            )

            if wa_result.get("ok"):
                self._update_log(log_id, "sent", None)
                logger.info(
                    f"Reminder sent: '{event_title}' to {contact_phone} "
                    f"(tenant={tenant_id})"
                )
            else:
                error = wa_result.get("error", "Unknown error")
                self._handle_retry(log_id, error)
        except Exception as e:
            self._handle_retry(log_id, str(e))

    def _handle_retry(self, log_id: str, error: str):
        """Increment retry count; mark as failed after 3 attempts."""
        sb = get_supabase_admin()
        now = datetime.now(timezone.utc).isoformat()

        entry = (
            sb.table("reminder_log")
            .select("retry_count")
            .eq("id", log_id)
            .single()
            .execute()
        )
        retries = (entry.data.get("retry_count", 0) if entry.data else 0) + 1

        if retries >= 3:
            self._update_log(log_id, "failed", error)
        else:
            # Exponential backoff: 5min, 25min, 125min
            delay = 5 ** retries * 60
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            sb.table("reminder_log").update({
                "retry_count": retries,
                "error_message": error,
                "scheduled_for": retry_at.isoformat(),
                "updated_at": now,
            }).eq("id", log_id).execute()
            logger.warning(
                f"Reminder {log_id} retry {retries}/3: {error} (next at {retry_at.isoformat()})"
            )

    def _update_log(self, log_id: str, status: str, error: str = None):
        """Update reminder log status."""
        sb = get_supabase_admin()
        now = datetime.now(timezone.utc).isoformat()
        updates = {"status": status, "updated_at": now}
        if status == "sent":
            updates["sent_at"] = now
        if error:
            updates["error_message"] = error
        sb.table("reminder_log").update(updates).eq("id", log_id).execute()


# Singleton
watcher = CalendarWatcherService()
