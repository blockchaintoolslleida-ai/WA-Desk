"""
Google Calendar Integration Router

Endpoints:
  GET  /api/calendar/auth-url          — Generate Google OAuth URL (loopback / OOB)
  POST /api/calendar/exchange-code     — Exchange authorization code for tokens
  GET  /api/calendar/status            — Connection status
  DELETE /api/calendar/disconnect      — Disconnect Google Calendar
  GET  /api/calendar/reminder-settings — Get reminder config
  PUT  /api/calendar/reminder-settings — Update reminder config
  POST /api/calendar/test-reminder     — Send a test reminder
  GET  /api/calendar/reminder-logs     — List reminder logs

OAuth flow: auth-url → user opens URL → Google shows auth code → user pastes code
→ exchange-code endpoint swaps code for tokens.
"""
from fastapi import APIRouter, HTTPException, Header, Query
from fastapi.responses import RedirectResponse
from typing import Optional
from pydantic import BaseModel
import logging
import uuid
import os
import secrets as _secrets
from datetime import datetime, timezone

from database import get_supabase_admin
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
from services.secrets_manager import encrypt_value, decrypt_value
from services.calendar_templates import render_template
from services.whatsapp import send_whatsapp_message, normalize_phone
from services.audit_logger import log_audit
from models import WhatsAppOutboundMessage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/calendar", tags=["Google Calendar"])

# ── CSRF state store (in-memory) ──────────────────────────────
_oauth_states: dict = {}


# ═══════════════════════════════════════════════════════════════════
# Auth Helper
# ═══════════════════════════════════════════════════════════════════

async def get_user_from_token(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticat")
    token = authorization.replace("Bearer ", "")
    admin_client = get_supabase_admin()
    try:
        user_response = admin_client.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Token invalid")
        profile = (
            admin_client.table("profiles")
            .select("id, full_name, role, tenant_id")
            .eq("id", user_response.user.id)
            .single()
            .execute()
        )
        if not profile.data:
            raise HTTPException(status_code=401, detail="Perfil no trobat")
        return profile.data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Error d'autenticacio")


# ═══════════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════════

class ExchangeCodeRequest(BaseModel):
    code: str
    state: str


class ReminderSettingsUpdate(BaseModel):
    is_active: Optional[bool] = None
    lead_time_hours: Optional[int] = None
    template_text: Optional[str] = None
    notification_window_minutes: Optional[int] = None


class TestReminderRequest(BaseModel):
    phone: str
    event_title: str = "Cita de prova"
    event_date: str = "15/01/2026"
    event_time: str = "10:00"


# ═══════════════════════════════════════════════════════════════════
# 1. OAuth URL (loopback / copy-paste flow)
# ═══════════════════════════════════════════════════════════════════

@router.get("/auth-url")
async def get_auth_url(authorization: Optional[str] = Header(None)):
    """Generate the Google OAuth 2.0 authorization URL for copy-paste flow.

    Uses redirect_uri=urn:ietf:wg:oauth:2.0:oob (out-of-band) so Google
    displays an authorization code the user can copy and paste.
    Falls back to the configured redirect URI if available.
    """
    user = await get_user_from_token(authorization)

    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLIENT_ID no configurat. Cal configurar les credencials de Google Cloud.",
        )

    # Generate CSRF state token
    state = _secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "tenant_id": user["tenant_id"],
        "user_id": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Clean up old states (>10 min)
    now = datetime.now(timezone.utc)
    expired = [s for s, v in _oauth_states.items()
               if (now - datetime.fromisoformat(v["created_at"])).total_seconds() > 600]
    for s in expired:
        del _oauth_states[s]

    scope = "https://www.googleapis.com/auth/calendar.readonly"

    # Use the configured redirect URI (should be accepted if properly set in Google Console)
    # For local development, this must be added under "Authorized redirect URIs"
    redirect_to_use = GOOGLE_REDIRECT_URI

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_to_use}"
        "&response_type=code"
        f"&scope={scope}"
        "&access_type=offline"
        "&prompt=consent"
        f"&state={state}"
    )

    return {
        "url": auth_url,
        "state": state,
        "redirect_uri": redirect_to_use,
        "note": "Open the URL in your browser. After authorizing, Google will redirect to: "
                + redirect_to_use + ". Copy the 'code' parameter from the URL.",
    }


# ═══════════════════════════════════════════════════════════════════
# 2. Exchange Code (POST — accepts code from frontend or manual paste)
# ═══════════════════════════════════════════════════════════════════

@router.post("/exchange-code")
async def exchange_code(req: ExchangeCodeRequest):
    """Exchange an OAuth authorization code for tokens. Stores the refresh token."""
    # Validate state
    state_data = _oauth_states.pop(req.state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state token")

    tenant_id = state_data["tenant_id"]
    user_id = state_data["user_id"]

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth credentials not configured",
        )

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import google_auth_oauthlib.flow

        # Build config for web application
        client_config = {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uris": [GOOGLE_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            client_config,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            redirect_uri=GOOGLE_REDIRECT_URI,
        )
        flow.fetch_token(code=req.code)

        credentials = flow.credentials
        refresh_token = credentials.refresh_token

        if not refresh_token:
            raise HTTPException(
                status_code=400,
                detail="No s'ha pogut obtenir el refresh token. Torna a autoritzar desconnectant primer si cal.",
            )

        # Refresh access token before using
        credentials.refresh(Request())

        # Get user email from Google Calendar (no extra API needed)
        cal_service = build("calendar", "v3", credentials=credentials)
        cal_list = cal_service.calendarList().list().execute()
        email = cal_list.get("items", [{}])[0].get("id", "")
        if not email:
            # Fallback: try primary calendar
            primary = cal_service.calendars().get(calendarId="primary").execute()
            email = primary.get("id", "unknown")

        # Store encrypted refresh token
        sb = get_supabase_admin()
        now = datetime.now(timezone.utc).isoformat()
        encrypted = encrypt_value(refresh_token)

        # Upsert into oauth_tokens
        existing = (
            sb.table("oauth_tokens")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("service", "google_calendar")
            .limit(1)
            .execute()
        )

        if existing.data:
            sb.table("oauth_tokens").update({
                "encrypted_access_token": encrypted,
                "calendar_email": email,
                "calendar_id": "primary",
                "updated_at": now,
            }).eq("id", existing.data[0]["id"]).execute()
        else:
            sb.table("oauth_tokens").insert({
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "service": "google_calendar",
                "encrypted_access_token": encrypted,
                "calendar_email": email,
                "calendar_id": "primary",
                "created_at": now,
                "updated_at": now,
            }).execute()

        # Ensure reminder_settings exist with defaults
        rem_existing = (
            sb.table("reminder_settings")
            .select("tenant_id")
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not rem_existing.data:
            sb.table("reminder_settings").insert({
                "tenant_id": tenant_id,
                "is_active": 1,
                "lead_time_hours": 24,
                "template_text": (
                    "Hola {{client_name}}, le recordamos su cita: "
                    "{{event_title}} el dia {{event_date}} a las {{event_time}}. "
                    "Por favor confirme su asistencia."
                ),
                "notification_window_minutes": 30,
                "created_at": now,
                "updated_at": now,
            }).execute()

        await log_audit(
            tenant_id, user_id, "connect_calendar", "oauth_tokens",
            tenant_id,
            f"Google Calendar connected: {email}",
        )

        logger.info(f"Google Calendar connected for tenant {tenant_id}: {email}")

        return {
            "success": True,
            "email": email,
            "message": "Google Calendar connectat correctament",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth code exchange error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error intercanviant el codi d'autoritzacio: {str(e)[:200]}",
        )


# ═══════════════════════════════════════════════════════════════════
# 2b. OAuth Callback (GET — for when redirect URI IS configured correctly)
# ═══════════════════════════════════════════════════════════════════

@router.get("/oauth2callback")
async def oauth2_callback(code: str = Query(None), state: str = Query(None), error: str = Query(None)):
    """Handle Google OAuth redirect. Forwards to frontend with code or error."""
    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    frontend_url = base_url.replace(":8000", ":3000")

    if error:
        return RedirectResponse(url=f"{frontend_url}/calendar?error={error}")

    if code and state:
        # Redirect to frontend with code embedded — frontend will POST to /exchange-code
        return RedirectResponse(
            url=f"{frontend_url}/calendar?code={code}&state={state}"
        )

    return {"status": "waiting_for_redirect"}


# ═══════════════════════════════════════════════════════════════════
# 3. Connection Status
# ═══════════════════════════════════════════════════════════════════

@router.get("/status")
async def get_calendar_status(authorization: Optional[str] = Header(None)):
    """Check if the current tenant has Google Calendar connected."""
    user = await get_user_from_token(authorization)
    sb = get_supabase_admin()
    tenant_id = user["tenant_id"]

    row = (
        sb.table("oauth_tokens")
        .select("calendar_email, calendar_id, updated_at")
        .eq("tenant_id", tenant_id)
        .eq("service", "google_calendar")
        .limit(1)
        .execute()
    )

    if not row.data:
        return {"connected": False, "email": None, "calendar_id": None}

    return {
        "connected": True,
        "email": row.data[0].get("calendar_email", ""),
        "calendar_id": row.data[0].get("calendar_id", "primary"),
        "connected_at": row.data[0].get("updated_at"),
    }


# ═══════════════════════════════════════════════════════════════════
# 4. Disconnect
# ═══════════════════════════════════════════════════════════════════

@router.delete("/disconnect")
async def disconnect_calendar(authorization: Optional[str] = Header(None)):
    """Remove the Google Calendar connection for this tenant."""
    user = await get_user_from_token(authorization)
    sb = get_supabase_admin()
    tenant_id = user["tenant_id"]

    result = (
        sb.table("oauth_tokens")
        .delete()
        .eq("tenant_id", tenant_id)
        .eq("service", "google_calendar")
        .execute()
    )

    await log_audit(
        tenant_id, user["id"], "disconnect_calendar", "oauth_tokens",
        tenant_id,
        "Google Calendar disconnected",
    )

    return {"success": True, "message": "Google Calendar desconnectat"}


# ═══════════════════════════════════════════════════════════════════
# 5. Get Reminder Settings
# ═══════════════════════════════════════════════════════════════════

@router.get("/reminder-settings")
async def get_reminder_settings(authorization: Optional[str] = Header(None)):
    """Get reminder configuration for the current tenant."""
    user = await get_user_from_token(authorization)
    sb = get_supabase_admin()
    tenant_id = user["tenant_id"]

    row = (
        sb.table("reminder_settings")
        .select("*")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )

    if not row.data:
        return {
            "tenant_id": tenant_id,
            "is_active": True,
            "lead_time_hours": 24,
            "template_text": (
                "Hola {{client_name}}, le recordamos su cita: "
                "{{event_title}} el dia {{event_date}} a las {{event_time}}. "
                "Por favor confirme su asistencia."
            ),
            "notification_window_minutes": 30,
        }

    return row.data[0]


# ═══════════════════════════════════════════════════════════════════
# 6. Update Reminder Settings
# ═══════════════════════════════════════════════════════════════════

@router.put("/reminder-settings")
async def update_reminder_settings(
    req: ReminderSettingsUpdate,
    authorization: Optional[str] = Header(None),
):
    """Update reminder configuration."""
    user = await get_user_from_token(authorization)
    sb = get_supabase_admin()
    tenant_id = user["tenant_id"]
    now = datetime.now(timezone.utc).isoformat()

    if req.lead_time_hours is not None:
        if req.lead_time_hours < 1 or req.lead_time_hours > 168:
            raise HTTPException(
                status_code=400,
                detail="lead_time_hours ha de ser entre 1 i 168 (1 hora a 7 dies)",
            )

    if req.template_text is not None and len(req.template_text) > 2000:
        raise HTTPException(
            status_code=400,
            detail="La plantilla no pot superar els 2000 caracters",
        )

    updates = {}
    if req.is_active is not None:
        updates["is_active"] = 1 if req.is_active else 0
    if req.lead_time_hours is not None:
        updates["lead_time_hours"] = req.lead_time_hours
    if req.template_text is not None:
        updates["template_text"] = req.template_text
    if req.notification_window_minutes is not None:
        updates["notification_window_minutes"] = req.notification_window_minutes

    if not updates:
        raise HTTPException(status_code=400, detail="No s'ha especificat cap canvi")

    updates["updated_at"] = now

    existing = (
        sb.table("reminder_settings")
        .select("tenant_id")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )

    if existing.data:
        sb.table("reminder_settings").update(updates).eq("tenant_id", tenant_id).execute()
    else:
        updates["tenant_id"] = tenant_id
        updates["created_at"] = now
        sb.table("reminder_settings").insert(updates).execute()

    await log_audit(
        tenant_id, user["id"], "update_settings", "reminder_settings",
        tenant_id,
        f"Updated reminder config: {', '.join(updates.keys())}",
    )

    row = (
        sb.table("reminder_settings")
        .select("*")
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )
    return row.data


# ═══════════════════════════════════════════════════════════════════
# 7. Test Reminder
# ═══════════════════════════════════════════════════════════════════

@router.post("/test-reminder")
async def test_reminder(
    req: TestReminderRequest,
    authorization: Optional[str] = Header(None),
):
    """Send a test reminder using the current template."""
    user = await get_user_from_token(authorization)
    sb = get_supabase_admin()
    tenant_id = user["tenant_id"]

    settings = (
        sb.table("reminder_settings")
        .select("template_text")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    template = (
        settings.data[0].get("template_text", "")
        if settings.data
        else "Hola {{client_name}}, recordatori: {{event_title}} el {{event_date}} a les {{event_time}}"
    )

    body = render_template(
        template=template,
        client_name="Client de prova",
        event_title=req.event_title,
        event_date=req.event_date,
        event_time=req.event_time,
    )

    wa_result = await send_whatsapp_message(
        WhatsAppOutboundMessage(
            phone=normalize_phone(req.phone),
            body=body,
        ),
        tenant_id=tenant_id,
    )

    return {
        "sent": wa_result.get("ok", False),
        "error": wa_result.get("error"),
        "body": body,
        "phone": normalize_phone(req.phone),
    }


# ═══════════════════════════════════════════════════════════════════
# 8. Reminder Logs
# ═══════════════════════════════════════════════════════════════════

@router.get("/reminder-logs")
async def get_reminder_logs(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Get reminder log entries for the current tenant."""
    user = await get_user_from_token(authorization)
    sb = get_supabase_admin()
    tenant_id = user["tenant_id"]

    query = (
        sb.table("reminder_log")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .limit(limit)
    )

    if status:
        query = query.eq("status", status)

    result = query.execute()
    return result.data or []
