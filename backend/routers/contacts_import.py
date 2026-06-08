"""
Contacts Import Router — Google OAuth + People API integration
Allows admins to import contacts from Gmail into WA-Desk.
"""
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import RedirectResponse
from typing import Optional
from pydantic import BaseModel
import logging
import uuid
import httpx
import os
import urllib.parse
from datetime import datetime, timezone
from database import get_supabase_admin
from services.secrets_manager import encrypt_value, decrypt_value
from services.whatsapp import normalize_phone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/contacts", tags=["Contacts Import"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_PEOPLE_API = "https://people.googleapis.com/v1/people/me/connections"
GOOGLE_SCOPES = "https://www.googleapis.com/auth/contacts.readonly"


def _get_google_config():
    return {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uri": os.environ.get("GOOGLE_REDIRECT_URI",
            os.environ.get("BASE_URL", "http://localhost:8000") + "/api/admin/contacts/callback/google"),
    }


# ── Auth helpers ──────────────────────────────────────────────

async def _get_admin_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticat")
    token = authorization.replace("Bearer ", "")
    supabase = get_supabase_admin()
    try:
        user_response = supabase.auth.get_user(token)
        profile = supabase.table('profiles').select(
            'id, full_name, role, tenant_id'
        ).eq('id', user_response.user.id).single().execute()
        if not profile.data or profile.data['role'] not in ('admin', 'super_admin'):
            raise HTTPException(status_code=403, detail="Accés denegat - cal rol admin")
        return profile.data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Error d'autenticacio")


def _save_tokens(tenant_id: str, service: str, access_token: str, refresh_token: str, expires_in: int):
    supabase = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()
    expires_at = datetime.now(timezone.utc).isoformat() if not expires_in else \
        (datetime.now(timezone.utc) + __import__('datetime').timedelta(seconds=expires_in)).isoformat()

    # Upsert
    existing = supabase.table('oauth_tokens').select('id').eq('tenant_id', tenant_id).eq('service', service).limit(1).execute()
    data = {
        'encrypted_access_token': encrypt_value(access_token),
        'encrypted_refresh_token': encrypt_value(refresh_token) if refresh_token else None,
        'token_expires_at': expires_at,
        'updated_at': now,
    }
    if existing.data:
        supabase.table('oauth_tokens').update(data).eq('id', existing.data[0]['id']).execute()
    else:
        data['id'] = str(uuid.uuid4())
        data['tenant_id'] = tenant_id
        data['service'] = service
        data['created_at'] = now
        supabase.table('oauth_tokens').insert(data).execute()


def _get_valid_token(tenant_id: str, service: str) -> Optional[str]:
    """Get a valid access token, refreshing if needed."""
    supabase = get_supabase_admin()
    row = supabase.table('oauth_tokens').select('*').eq('tenant_id', tenant_id).eq('service', service).limit(1).execute()
    if not row.data:
        return None

    data = row.data[0]
    access_token = decrypt_value(data['encrypted_access_token']) if data.get('encrypted_access_token') else None
    if not access_token:
        return None

    # Check expiry
    expires_at = data.get('token_expires_at')
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > exp_dt:
                # Refresh
                refresh_token = decrypt_value(data['encrypted_refresh_token']) if data.get('encrypted_refresh_token') else None
                if refresh_token:
                    cfg = _get_google_config()
                    try:
                        resp = httpx.post(GOOGLE_TOKEN_URL, data={
                            "client_id": cfg['client_id'],
                            "client_secret": cfg['client_secret'],
                            "refresh_token": refresh_token,
                            "grant_type": "refresh_token",
                        }, timeout=10)
                        if resp.status_code == 200:
                            d = resp.json()
                            _save_tokens(tenant_id, service, d['access_token'],
                                         d.get('refresh_token', refresh_token), d.get('expires_in', 3600))
                            return d['access_token']
                    except Exception as e:
                        logger.error(f"Token refresh failed: {e}")
                return None
        except (ValueError, TypeError):
            pass

    return access_token


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/auth-status")
async def auth_status(authorization: Optional[str] = Header(None)):
    """Check if Google OAuth is configured for this tenant"""
    user = await _get_admin_user(authorization)
    token = _get_valid_token(user['tenant_id'], 'google')
    return {"connected": bool(token), "service": "google"}


@router.get("/auth/google")
async def auth_google(authorization: Optional[str] = Header(None)):
    """Start Google OAuth flow — redirect to Google consent screen"""
    await _get_admin_user(authorization)
    cfg = _get_google_config()
    if not cfg['client_id']:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID no configurat")

    params = {
        "client_id": cfg['client_id'],
        "redirect_uri": cfg['redirect_uri'],
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/callback/google")
async def callback_google(code: str, state: str = None, authorization: Optional[str] = Header(None)):
    """Google OAuth callback — exchange code for tokens and store"""
    # Get admin user from auth header (if present) or just handle the callback
    tenant_id = None
    if authorization and authorization.startswith("Bearer "):
        try:
            user = await _get_admin_user(authorization)
            tenant_id = user['tenant_id']
        except Exception:
            pass

    if not tenant_id:
        return {"error": "No autenticat — torna al panel d'administració i torna a intentar"}

    cfg = _get_google_config()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data={
                "client_id": cfg['client_id'],
                "client_secret": cfg['client_secret'],
                "redirect_uri": cfg['redirect_uri'],
                "code": code,
                "grant_type": "authorization_code",
            })

        if resp.status_code != 200:
            logger.error(f"Google token exchange failed: {resp.status_code} - {resp.text}")
            raise HTTPException(status_code=400, detail=f"Error d'autenticació amb Google: {resp.text[:200]}")

        data = resp.json()
        _save_tokens(tenant_id, 'google',
                     data['access_token'],
                     data.get('refresh_token', ''),
                     data.get('expires_in', 3600))

        # Redirect back to admin panel
        base_url = os.environ.get("BASE_URL", "http://localhost:3000")
        return RedirectResponse(url=f"{base_url}/admin?section=contacts-import&oauth=success")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google callback error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)[:200]}")


@router.get("/list/google")
async def list_google_contacts(authorization: Optional[str] = Header(None)):
    """Fetch contacts from Google People API"""
    user = await _get_admin_user(authorization)
    token = _get_valid_token(user['tenant_id'], 'google')
    if not token:
        raise HTTPException(status_code=401, detail="No connectat a Google. Autentica primer a /api/admin/contacts/auth/google")

    contacts = []
    page_token = None

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for _ in range(5):  # Max 5 pages (~2500 contacts)
                params = {
                    "personFields": "names,emailAddresses,phoneNumbers",
                    "pageSize": 500,
                }
                if page_token:
                    params["pageToken"] = page_token

                resp = await client.get(GOOGLE_PEOPLE_API, params=params,
                                        headers={"Authorization": f"Bearer {token}"})

                if resp.status_code != 200:
                    logger.error(f"Google People API error: {resp.status_code} - {resp.text[:200]}")
                    raise HTTPException(status_code=502, detail=f"Error de Google API: {resp.text[:200]}")

                data = resp.json()
                for person in data.get('connections', []):
                    names = person.get('names', [])
                    emails = person.get('emailAddresses', [])
                    phones = person.get('phoneNumbers', [])

                    name = names[0].get('displayName', '') if names else ''
                    email = emails[0].get('value', '') if emails else ''
                    phone_raw = phones[0].get('value', '') if phones else ''
                    phone = normalize_phone(phone_raw) if phone_raw else ''

                    if name or email or phone:
                        contacts.append({
                            "name": name,
                            "email": email,
                            "phone": phone,
                            "google_id": person.get('resourceName', ''),
                        })

                page_token = data.get('nextPageToken')
                if not page_token:
                    break

        return {"contacts": contacts, "total": len(contacts)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google contacts fetch error: {e}")
        raise HTTPException(status_code=500, detail=f"Error obtenint contactes: {str(e)[:200]}")


class ImportContactsRequest(BaseModel):
    contacts: list  # [{"name": "...", "email": "...", "phone": "..."}, ...]


@router.post("/import")
async def import_contacts(req: ImportContactsRequest, authorization: Optional[str] = Header(None)):
    """Import selected contacts into WA-Desk contacts table"""
    user = await _get_admin_user(authorization)
    supabase = get_supabase_admin()
    tenant_id = user['tenant_id']
    now = datetime.now(timezone.utc).isoformat()

    imported = 0
    skipped = 0
    errors = []

    for c in req.contacts:
        try:
            name = (c.get('name') or '').strip()
            email = (c.get('email') or '').strip()
            phone = (c.get('phone') or '').strip()

            if not name and not phone:
                skipped += 1
                continue

            # Check duplicates by email and phone
            existing = None
            if email:
                existing = supabase.table('contacts').select('id').eq('email', email).eq('tenant_id', tenant_id).limit(1).execute()
            if not existing or not existing.data:
                if phone:
                    existing = supabase.table('contacts').select('id').eq('phone', phone).eq('tenant_id', tenant_id).limit(1).execute()

            if existing and existing.data:
                skipped += 1
                continue

            contact = {
                'id': str(uuid.uuid4()),
                'name': name or f"Contacte {phone[-4:]}" if phone else email,
                'phone': phone or None,
                'email': email or None,
                'source': 'google',
                'tenant_id': tenant_id,
                'created_at': now,
                'updated_at': now,
            }
            supabase.table('contacts').insert(contact).execute()
            imported += 1

        except Exception as e:
            errors.append(f"{c.get('name', '?')}: {str(e)[:50]}")

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
    }
