"""
Admin Platform Router - Multi-tenant WhatsApp account management
Sections: Account, Credentials, Webhook, Audit Logs
"""
from fastapi import APIRouter, HTTPException, Header, Request
from typing import Optional
from pydantic import BaseModel
import logging
import uuid
import httpx
from datetime import datetime, timezone
from database import get_supabase_admin
from services.secrets_manager import encrypt_value, decrypt_value, mask_value
from services.audit_logger import log_audit
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin Platform"])

WHATSAPP_API_URL = "https://graph.facebook.com/v21.0"


# ──────────────── Auth helpers ────────────────

async def get_admin_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticat")
    token = authorization.replace("Bearer ", "")
    supabase = get_supabase_admin()
    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Token invalid")
        profile = supabase.table('profiles').select('id, full_name, role, tenant_id').eq(
            'id', user_response.user.id).single().execute()
        if not profile.data:
            raise HTTPException(status_code=401, detail="Perfil no trobat")
        if profile.data['role'] not in ('super_admin', 'admin'):
            raise HTTPException(status_code=403, detail="Accés denegat - cal rol admin")
        return profile.data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Error d'autenticacio")


# ──────────────── Setup Check ────────────────

@router.get("/setup/check")
async def check_admin_tables(authorization: Optional[str] = Header(None)):
    """Check if admin platform tables exist"""
    await get_admin_user(authorization)
    supabase = get_supabase_admin()

    tables = ['tenants', 'whatsapp_accounts', 'whatsapp_secrets', 'whatsapp_webhook_logs', 'audit_logs']
    status = {}
    for table in tables:
        try:
            supabase.table(table).select('id').limit(1).execute()
            status[table] = 'ok'
        except Exception:
            status[table] = 'missing'

    all_ready = all(v == 'ok' for v in status.values())
    return {"all_ready": all_ready, "tables": status}


# ──────────────── Tenant Management ────────────────

class TenantCreate(BaseModel):
    name: str
    slug: str


@router.get("/my-tenant")
async def get_my_tenant(authorization: Optional[str] = Header(None)):
    """Get the current user's tenant info"""
    user = await get_admin_user(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    if not tenant_id:
        return {"tenant": None}

    result = supabase.table('tenants').select('*').eq('id', tenant_id).limit(1).execute()
    return {"tenant": result.data[0] if result.data else None}


@router.post("/my-tenant")
async def create_my_tenant(req: TenantCreate, authorization: Optional[str] = Header(None)):
    """Create a new tenant and assign the current user to it"""
    user = await get_admin_user(authorization)
    supabase = get_supabase_admin()

    if user.get('tenant_id'):
        raise HTTPException(status_code=400, detail="Ja tens un tenant assignat")

    slug = req.slug.strip().lower().replace(' ', '-')

    # Check slug uniqueness
    existing = supabase.table('tenants').select('id').eq('slug', slug).limit(1).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Aquest slug ja existeix")

    now = datetime.now(timezone.utc).isoformat()
    tenant = {
        'id': str(uuid.uuid4()),
        'name': req.name.strip(),
        'slug': slug,
        'status': 'active',
        'created_at': now,
    }
    supabase.table('tenants').insert(tenant).execute()

    # Assign user to tenant
    supabase.table('profiles').update({'tenant_id': tenant['id']}).eq('id', user['id']).execute()

    await log_audit(tenant['id'], user['id'], 'create_tenant', 'tenant', tenant['id'],
                    f"Tenant created: {tenant['name']}")

    return {"tenant": tenant}


# ──────────────── Section 1: WhatsApp Account ────────────────

class WAAccountUpdate(BaseModel):
    account_name: Optional[str] = None
    phone_number_id: Optional[str] = None
    whatsapp_business_account_id: Optional[str] = None
    connection_type: Optional[str] = None       # 'meta' or 'openwa'
    openwa_server_url: Optional[str] = None
    openwa_session_id: Optional[str] = None


@router.get("/whatsapp-account")
async def get_whatsapp_account(authorization: Optional[str] = Header(None)):
    """Get current tenant's WhatsApp account configuration"""
    user = await get_admin_user(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    if not tenant_id:
        return {"account": None, "needs_tenant": True}

    result = supabase.table('whatsapp_accounts').select('*').eq('tenant_id', tenant_id).limit(1).execute()

    if not result.data:
        # Create empty account for this tenant (no auto-import from .env!)
        now = datetime.now(timezone.utc).isoformat()
        new_account = {
            'id': str(uuid.uuid4()),
            'tenant_id': tenant_id,
            'account_name': '',
            'business_name': '',
            'phone_number_id': '',
            'connection_status': 'disconnected',
            'webhook_status': 'not_configured',
            'token_status': 'not_set',
            'created_at': now,
            'updated_at': now,
        }
        supabase.table('whatsapp_accounts').insert(new_account).execute()
        return {"account": new_account}

    return {"account": result.data[0]}


@router.put("/whatsapp-account")
async def update_whatsapp_account(req: WAAccountUpdate, authorization: Optional[str] = Header(None), request: Request = None):
    """Update WhatsApp account configuration"""
    user = await get_admin_user(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant assignat")

    # Get existing account
    existing = supabase.table('whatsapp_accounts').select('id').eq('tenant_id', tenant_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Compte WhatsApp no trobat")

    account_id = existing.data[0]['id']
    updates = {k: v for k, v in req.dict().items() if v is not None}
    updates['updated_at'] = datetime.now(timezone.utc).isoformat()

    supabase.table('whatsapp_accounts').update(updates).eq('id', account_id).execute()

    await log_audit(tenant_id, user['id'], 'update', 'whatsapp_account', account_id,
                    f"Updated fields: {', '.join(updates.keys())}")

    updated = supabase.table('whatsapp_accounts').select('*').eq('id', account_id).single().execute()
    return {"account": updated.data}


@router.post("/whatsapp-account/validate")
async def validate_connection(authorization: Optional[str] = Header(None)):
    """Validate the WhatsApp connection (Meta API or OpenWA Gateway)"""
    user = await get_admin_user(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    account = supabase.table('whatsapp_accounts').select(
        'id, connection_type, phone_number_id, openwa_server_url, openwa_session_id'
    ).eq('tenant_id', tenant_id).limit(1).execute()
    if not account.data:
        raise HTTPException(status_code=404, detail="Compte no trobat")

    acc = account.data[0]
    connection_type = acc.get('connection_type') or 'meta'

    # ── OpenWA validation ───────────────────────────────────
    if connection_type == 'openwa':
        server_url = acc.get('openwa_server_url', '')
        session_id = acc.get('openwa_session_id', '')
        secrets = supabase.table('whatsapp_secrets').select('encrypted_openwa_api_key').eq(
            'whatsapp_account_id', acc['id']).limit(1).execute()
        api_key = None
        if secrets.data and secrets.data[0].get('encrypted_openwa_api_key'):
            api_key = decrypt_value(secrets.data[0]['encrypted_openwa_api_key'])

        now = datetime.now(timezone.utc).isoformat()

        if not server_url or not api_key or not session_id:
            supabase.table('whatsapp_accounts').update({
                'connection_status': 'error',
                'token_status': 'not_set',
                'last_validation_at': now,
                'updated_at': now,
            }).eq('id', acc['id']).execute()
            return {"valid": False, "error": "OpenWA: URL, API Key o Session ID no configurat"}

        from services.whatsapp import validate_openwa_connection
        result = await validate_openwa_connection(server_url, api_key, session_id)

        status_update = {
            'connection_status': 'connected' if result['ok'] else 'error',
            'token_status': 'valid' if result['ok'] else 'error',
            'last_validation_at': now,
            'updated_at': now,
        }
        supabase.table('whatsapp_accounts').update(status_update).eq('id', acc['id']).execute()

        # Auto-register webhook on OpenWA after successful validation
        webhook_registered = False
        if result['ok']:
            try:
                base_url = os.environ.get('BASE_URL', 'http://localhost:8000')
                # Use the frontend-accessible URL if available via Referer or known IP
                webhook_url = f"{base_url}/api/whatsapp/webhook/openwa"
                webhook_payload = {
                    "url": webhook_url,
                    "events": ["message.received"],
                }
                async with httpx.AsyncClient(timeout=10) as openwa_client:
                    wh_resp = await openwa_client.post(
                        f"{server_url.rstrip('/')}/api/sessions/{session_id}/webhooks",
                        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                        json=webhook_payload,
                    )
                if wh_resp.status_code in (200, 201):
                    webhook_registered = True
                    logger.info(f"OpenWA webhook auto-registered: {webhook_url}")
                    supabase.table('whatsapp_accounts').update({
                        'webhook_status': 'verified',
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                    }).eq('id', acc['id']).execute()
                else:
                    logger.warning(f"OpenWA webhook registration returned {wh_resp.status_code}: {wh_resp.text[:200]}")
            except Exception as wh_err:
                logger.warning(f"OpenWA webhook registration failed (non-fatal): {wh_err}")

        await log_audit(tenant_id, user['id'], 'validate', 'whatsapp_account', acc['id'],
                        f"OpenWA validation: {'OK' if result['ok'] else result.get('error', 'Failed')}"
                        + (f" + webhook registered ({webhook_url})" if webhook_registered else ""))
        return {
            "valid": result['ok'],
            "data": result,
            "connection_type": "openwa",
            "webhook_registered": webhook_registered,
        }

    # ── Meta validation (original) ──────────────────────────
    phone_id = acc.get('phone_number_id')
    secrets = supabase.table('whatsapp_secrets').select('encrypted_access_token').eq(
        'whatsapp_account_id', acc['id']).limit(1).execute()
    access_token = None
    if secrets.data and secrets.data[0].get('encrypted_access_token'):
        access_token = decrypt_value(secrets.data[0]['encrypted_access_token'])
    if not access_token:
        access_token = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')

    if not access_token or not phone_id:
        status_update = {
            'connection_status': 'error',
            'token_status': 'not_set',
            'last_validation_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        supabase.table('whatsapp_accounts').update(status_update).eq('id', acc['id']).execute()
        return {"valid": False, "error": "Token o Phone Number ID no configurat"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{WHATSAPP_API_URL}/{phone_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"fields": "verified_name,display_phone_number,quality_rating"}
            )

        now = datetime.now(timezone.utc).isoformat()

        if resp.status_code == 200:
            data = resp.json()
            supabase.table('whatsapp_accounts').update({
                'connection_status': 'connected',
                'token_status': 'valid',
                'display_phone_number': data.get('display_phone_number', ''),
                'sender_display_name': data.get('verified_name', ''),
                'last_validation_at': now,
                'updated_at': now,
            }).eq('id', acc['id']).execute()

            await log_audit(tenant_id, user['id'], 'validate', 'whatsapp_account', acc['id'], 'Connection validated OK')
            return {"valid": True, "data": data, "connection_type": "meta"}
        else:
            supabase.table('whatsapp_accounts').update({
                'connection_status': 'error',
                'token_status': 'error' if resp.status_code == 401 else 'valid',
                'last_validation_at': now,
                'updated_at': now,
            }).eq('id', acc['id']).execute()
            return {"valid": False, "error": f"Meta API: {resp.status_code} - {resp.text[:200]}"}

    except Exception as e:
        return {"valid": False, "error": str(e)}


@router.post("/whatsapp-account/disconnect")
async def disconnect_account(authorization: Optional[str] = Header(None)):
    """Mark account as disconnected"""
    user = await get_admin_user(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    account = supabase.table('whatsapp_accounts').select('id').eq('tenant_id', tenant_id).limit(1).execute()
    if not account.data:
        raise HTTPException(status_code=404, detail="Compte no trobat")

    now = datetime.now(timezone.utc).isoformat()
    supabase.table('whatsapp_accounts').update({
        'connection_status': 'disconnected',
        'updated_at': now,
    }).eq('id', account.data[0]['id']).execute()

    await log_audit(tenant_id, user['id'], 'disconnect', 'whatsapp_account', account.data[0]['id'], 'Account disconnected')
    return {"ok": True}


# ──────────────── Section 2: Credentials ────────────────

class SecretsUpdate(BaseModel):
    access_token: Optional[str] = None
    app_secret: Optional[str] = None
    verify_token: Optional[str] = None
    openwa_api_key: Optional[str] = None
    token_expires_at: Optional[str] = None


@router.get("/whatsapp-secrets")
async def get_secrets(authorization: Optional[str] = Header(None)):
    """Get masked secrets for the WhatsApp account"""
    user = await get_admin_user(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    account = supabase.table('whatsapp_accounts').select('id').eq('tenant_id', tenant_id).limit(1).execute()
    if not account.data:
        return {"secrets": None}

    result = supabase.table('whatsapp_secrets').select('*').eq(
        'whatsapp_account_id', account.data[0]['id']).limit(1).execute()

    if not result.data:
        return {"secrets": {
            "has_access_token": False, "has_app_secret": False, "has_verify_token": False,
            "has_openwa_api_key": False,
            "token_expires_at": None, "last_rotated_at": None,
        }}

    s = result.data[0]
    return {"secrets": {
        "has_access_token": bool(s.get('encrypted_access_token')),
        "masked_access_token": mask_value(decrypt_value(s['encrypted_access_token'])) if s.get('encrypted_access_token') else '',
        "has_app_secret": bool(s.get('encrypted_app_secret')),
        "masked_app_secret": mask_value(decrypt_value(s['encrypted_app_secret']), 4) if s.get('encrypted_app_secret') else '',
        "has_verify_token": bool(s.get('encrypted_verify_token')),
        "masked_verify_token": mask_value(decrypt_value(s['encrypted_verify_token'])) if s.get('encrypted_verify_token') else '',
        "has_openwa_api_key": bool(s.get('encrypted_openwa_api_key')),
        "masked_openwa_api_key": mask_value(decrypt_value(s['encrypted_openwa_api_key'])) if s.get('encrypted_openwa_api_key') else '',
        "token_expires_at": s.get('token_expires_at'),
        "last_rotated_at": s.get('last_rotated_at'),
    }}


@router.put("/whatsapp-secrets")
async def update_secrets(req: SecretsUpdate, authorization: Optional[str] = Header(None)):
    """Update encrypted credentials"""
    user = await get_admin_user(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    account = supabase.table('whatsapp_accounts').select('id').eq('tenant_id', tenant_id).limit(1).execute()
    if not account.data:
        raise HTTPException(status_code=404, detail="Compte no trobat")

    account_id = account.data[0]['id']
    now = datetime.now(timezone.utc).isoformat()

    updates = {'updated_at': now}
    changed = []

    if req.access_token is not None:
        updates['encrypted_access_token'] = encrypt_value(req.access_token)
        changed.append('access_token')
    if req.app_secret is not None:
        updates['encrypted_app_secret'] = encrypt_value(req.app_secret)
        changed.append('app_secret')
    if req.verify_token is not None:
        updates['encrypted_verify_token'] = encrypt_value(req.verify_token)
        changed.append('verify_token')
    if req.openwa_api_key is not None:
        updates['encrypted_openwa_api_key'] = encrypt_value(req.openwa_api_key)
        changed.append('openwa_api_key')
    if req.token_expires_at is not None:
        updates['token_expires_at'] = req.token_expires_at

    if changed:
        updates['last_rotated_at'] = now

    # Upsert
    existing = supabase.table('whatsapp_secrets').select('id').eq('whatsapp_account_id', account_id).limit(1).execute()
    if existing.data:
        supabase.table('whatsapp_secrets').update(updates).eq('whatsapp_account_id', account_id).execute()
    else:
        updates['id'] = str(uuid.uuid4())
        updates['whatsapp_account_id'] = account_id
        updates['created_at'] = now
        supabase.table('whatsapp_secrets').insert(updates).execute()

    await log_audit(tenant_id, user['id'], 'update_secrets', 'whatsapp_secrets', account_id,
                    f"Updated: {', '.join(changed)}")

    return {"ok": True, "updated": changed}


@router.post("/whatsapp-secrets/test-connection")
async def test_connection(authorization: Optional[str] = Header(None)):
    """Test the stored credentials by calling Meta API"""
    user = await get_admin_user(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    account = supabase.table('whatsapp_accounts').select('id, phone_number_id').eq(
        'tenant_id', tenant_id).limit(1).execute()
    if not account.data:
        return {"ok": False, "error": "Compte no trobat"}

    acc = account.data[0]
    secrets = supabase.table('whatsapp_secrets').select('encrypted_access_token').eq(
        'whatsapp_account_id', acc['id']).limit(1).execute()

    token = None
    if secrets.data and secrets.data[0].get('encrypted_access_token'):
        token = decrypt_value(secrets.data[0]['encrypted_access_token'])

    if not token:
        token = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')

    if not token:
        return {"ok": False, "error": "Access Token no configurat"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{WHATSAPP_API_URL}/{acc['phone_number_id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code == 200:
            return {"ok": True, "message": "Connexio correcta"}
        return {"ok": False, "error": f"Error {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ──────────────── Section 3: Webhook ────────────────

@router.get("/webhook-info")
async def get_webhook_info(authorization: Optional[str] = Header(None)):
    """Get webhook configuration and status"""
    user = await get_admin_user(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    account = supabase.table('whatsapp_accounts').select(
        'id, webhook_status'
    ).eq('tenant_id', tenant_id).limit(1).execute()

    base_url = os.environ.get('REACT_APP_BACKEND_URL', os.environ.get('BASE_URL', ''))
    verify_token = os.environ.get('WHATSAPP_VERIFY_TOKEN', '')

    # Get last webhook events
    last_events = []
    if account.data:
        acc_id = account.data[0]['id']
        try:
            events = supabase.table('whatsapp_webhook_logs').select(
                'id, event_type, delivery_status, error_message, received_at'
            ).eq('whatsapp_account_id', acc_id).order('received_at', desc=True).limit(10).execute()
            last_events = events.data or []
        except Exception:
            pass

    # Try to get verify_token from secrets
    if account.data:
        try:
            sec = supabase.table('whatsapp_secrets').select('encrypted_verify_token').eq(
                'whatsapp_account_id', account.data[0]['id']).limit(1).execute()
            if sec.data and sec.data[0].get('encrypted_verify_token'):
                verify_token = decrypt_value(sec.data[0]['encrypted_verify_token'])
        except Exception:
            pass

    return {
        "webhook_url": f"{base_url}/api/whatsapp/webhook",
        "verify_token": verify_token,
        "webhook_status": account.data[0]['webhook_status'] if account.data else 'not_configured',
        "last_events": last_events,
    }


@router.post("/webhook-info/verify")
async def verify_webhook(authorization: Optional[str] = Header(None)):
    """Mark webhook as verified after user configures Meta"""
    user = await get_admin_user(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    account = supabase.table('whatsapp_accounts').select('id').eq('tenant_id', tenant_id).limit(1).execute()
    if not account.data:
        raise HTTPException(status_code=404, detail="Compte no trobat")

    now = datetime.now(timezone.utc).isoformat()
    supabase.table('whatsapp_accounts').update({
        'webhook_status': 'verified',
        'updated_at': now,
    }).eq('id', account.data[0]['id']).execute()

    await log_audit(tenant_id, user['id'], 'verify_webhook', 'whatsapp_account', account.data[0]['id'], 'Webhook marked as verified')
    return {"ok": True}


# ──────────────── Audit Logs ────────────────

@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 50,
    authorization: Optional[str] = Header(None),
):
    """Get audit logs for the current tenant"""
    user = await get_admin_user(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    if not tenant_id:
        return []

    result = supabase.table('audit_logs').select(
        'id, action_type, entity_type, entity_id, description, created_at, user_id, action'
    ).eq('tenant_id', tenant_id).order('created_at', desc=True).limit(limit).execute()

    logs = []
    for r in (result.data or []):
        r['action_type'] = r.get('action_type') or r.get('action') or ''
        logs.append(r)
    return logs


# ──────────────── Super Admin: Company Management ────────────────

def require_super_admin(user: dict):
    if user.get('role') != 'super_admin':
        raise HTTPException(status_code=403, detail="Només el superadministrador pot fer aquesta acció")


@router.get("/tenants")
async def list_tenants(authorization: Optional[str] = Header(None)):
    """List all companies/tenants — super_admin only"""
    user = await get_admin_user(authorization)
    require_super_admin(user)
    supabase = get_supabase_admin()

    tenants = supabase.table('tenants').select('*').order('created_at', desc=True).execute()
    result = []
    for t in (tenants.data or []):
        # Count users per tenant
        users = supabase.table('profiles').select('id', count='exact').eq('tenant_id', t['id']).execute()
        accounts = supabase.table('whatsapp_accounts').select('id').eq('tenant_id', t['id']).limit(1).execute()
        t['user_count'] = users.count if users.count else 0
        t['has_whatsapp'] = bool(accounts.data)
        result.append(t)
    return result


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str, authorization: Optional[str] = Header(None)):
    """Delete a company and all associated data — super_admin only"""
    user = await get_admin_user(authorization)
    require_super_admin(user)
    supabase = get_supabase_admin()

    # Verify tenant exists
    tenant = supabase.table('tenants').select('id,name').eq('id', tenant_id).single().execute()
    if not tenant.data:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    tenant_name = tenant.data.get('name', tenant_id)

    # Cascade delete: whatsapp_secrets → whatsapp_accounts → conversations → messages → contacts → profiles → tenant
    account = supabase.table('whatsapp_accounts').select('id').eq('tenant_id', tenant_id).limit(1).execute()
    if account.data:
        acc_id = account.data[0]['id']
        supabase.table('whatsapp_secrets').delete().eq('whatsapp_account_id', acc_id).execute()
        supabase.table('whatsapp_webhook_logs').delete().eq('whatsapp_account_id', acc_id).execute()
        supabase.table('whatsapp_api_logs').delete().eq('whatsapp_account_id', acc_id).execute()
        supabase.table('whatsapp_accounts').delete().eq('id', acc_id).execute()

    # Delete conversations and messages for this tenant
    convs = supabase.table('conversations').select('id').eq('tenant_id', tenant_id).execute()
    for c in (convs.data or []):
        supabase.table('case_events').delete().eq('case_id', supabase.table('cases').select('id').eq('conversation_id', c['id']).execute().data[0]['id'] if supabase.table('cases').select('id').eq('conversation_id', c['id']).execute().data else None).execute() if False else None
        # Quick cascade
        cases_res = supabase.table('cases').select('id').eq('conversation_id', c['id']).execute()
        for cs in (cases_res.data or []):
            supabase.table('case_events').delete().eq('case_id', cs['id']).execute()
            supabase.table('case_notes').delete().eq('case_id', cs['id']).execute()
            supabase.table('case_views').delete().eq('case_id', cs['id']).execute()
        supabase.table('cases').delete().eq('conversation_id', c['id']).execute()
        supabase.table('messages').delete().eq('conversation_id', c['id']).execute()
    supabase.table('conversations').delete().eq('tenant_id', tenant_id).execute()
    supabase.table('contacts').delete().eq('tenant_id', tenant_id).execute()

    # Clear tenant_id from profiles (don't delete users, just unlink)
    supabase.table('profiles').update({'tenant_id': None}).eq('tenant_id', tenant_id).execute()
    supabase.table('audit_logs').delete().eq('tenant_id', tenant_id).execute()
    supabase.table('tenants').delete().eq('id', tenant_id).execute()

    await log_audit(tenant_id, user['id'], 'delete_tenant', 'tenant', tenant_id, f"Empresa '{tenant_name}' eliminada pel superadmin")
    return {"ok": True, "deleted": tenant_name}


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None


@router.put("/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, req: TenantUpdate, authorization: Optional[str] = Header(None)):
    """Edit company name/slug — super_admin only"""
    user = await get_admin_user(authorization)
    require_super_admin(user)
    supabase = get_supabase_admin()

    tenant = supabase.table('tenants').select('id').eq('id', tenant_id).single().execute()
    if not tenant.data:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    updates = {}
    if req.name is not None:
        updates['name'] = req.name.strip()
    if req.slug is not None:
        slug = req.slug.strip().lower().replace(' ', '-')
        existing = supabase.table('tenants').select('id').eq('slug', slug).neq('id', tenant_id).limit(1).execute()
        if existing.data:
            raise HTTPException(status_code=409, detail="Aquest slug ja existeix")
        updates['slug'] = slug

    if updates:
        supabase.table('tenants').update(updates).eq('id', tenant_id).execute()
        await log_audit(tenant_id, user['id'], 'update_tenant', 'tenant', tenant_id,
                        f"Updated: {', '.join(updates.keys())}")
    updated = supabase.table('tenants').select('*').eq('id', tenant_id).single().execute()
    return updated.data


@router.get("/tenants/{tenant_id}/users")
async def list_tenant_users(tenant_id: str, authorization: Optional[str] = Header(None)):
    """List users in a company — super_admin only"""
    user = await get_admin_user(authorization)
    require_super_admin(user)
    supabase = get_supabase_admin()

    users = supabase.table('profiles').select(
        'id, full_name, email, role, phone, is_active, created_at'
    ).eq('tenant_id', tenant_id).order('created_at').execute()
    return users.data or []


class AssignUserRequest(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = 'agent'  # 'admin' or 'agent'


@router.post("/tenants/{tenant_id}/users")
async def assign_user_to_tenant(tenant_id: str, req: AssignUserRequest, authorization: Optional[str] = Header(None)):
    """Create and assign a new admin/agent to a company — super_admin only"""
    user = await get_admin_user(authorization)
    require_super_admin(user)
    supabase = get_supabase_admin()

    # Verify tenant
    tenant = supabase.table('tenants').select('id').eq('id', tenant_id).single().execute()
    if not tenant.data:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    if req.role not in ('admin', 'agent'):
        raise HTTPException(status_code=400, detail="Rol ha de ser 'admin' o 'agent'")

    now = datetime.now(timezone.utc).isoformat()
    try:
        # Create auth user
        auth_response = supabase.auth.admin.create_user({
            "email": req.email.strip(),
            "password": req.password,
            "email_confirm": True,
        })
        uid = auth_response.user.id
    except Exception as e:
        if 'already been registered' in str(e) or 'duplicate' in str(e).lower():
            raise HTTPException(status_code=400, detail="Ja existeix un usuari amb aquest email")
        raise HTTPException(status_code=500, detail=f"Error creant usuari: {str(e)[:100]}")

    from local_db import hash_password
    profile = {
        'id': uid,
        'full_name': req.full_name.strip(),
        'email': req.email.strip(),
        'password_hash': hash_password(req.password),
        'role': req.role,
        'is_active': True,
        'tenant_id': tenant_id,
        'created_at': now,
    }
    supabase.table('profiles').insert(profile).execute()

    await log_audit(tenant_id, user['id'], 'assign_user', 'profiles', uid,
                    f"User '{req.full_name}' ({req.role}) assigned to tenant")
    return profile


@router.delete("/tenants/{tenant_id}/users/{target_user_id}")
async def remove_user_from_tenant(tenant_id: str, target_user_id: str, authorization: Optional[str] = Header(None)):
    """Remove user from company (unlink or delete agent) — super_admin only"""
    user = await get_admin_user(authorization)
    require_super_admin(user)
    supabase = get_supabase_admin()

    target = supabase.table('profiles').select('id,full_name,role,email,tenant_id').eq('id', target_user_id).single().execute()
    if not target.data:
        raise HTTPException(status_code=404, detail="Usuari no trobat")
    if target.data.get('tenant_id') != tenant_id:
        raise HTTPException(status_code=400, detail="Aquest usuari no pertany a aquesta empresa")

    target_name = target.data.get('full_name', target.data.get('email', ''))

    if target.data['role'] == 'agent':
        # Delete agent completely
        supabase.table('profiles').delete().eq('id', target_user_id).execute()
        await log_audit(tenant_id, user['id'], 'remove_user', 'profiles', target_user_id,
                        f"Agent '{target_name}' deleted")
        return {"ok": True, "deleted": True, "name": target_name}
    else:
        # Unlink admin (set tenant_id to None, don't delete)
        supabase.table('profiles').update({'tenant_id': None}).eq('id', target_user_id).execute()
        await log_audit(tenant_id, user['id'], 'unlink_user', 'profiles', target_user_id,
                        f"Admin '{target_name}' unlinked from tenant")
        return {"ok": True, "unlinked": True, "name": target_name}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, authorization: Optional[str] = Header(None)):
    """Delete any user — super_admin only"""
    user = await get_admin_user(authorization)
    require_super_admin(user)
    supabase = get_supabase_admin()

    target = supabase.table('profiles').select('id,full_name,role,email').eq('id', user_id).single().execute()
    if not target.data:
        raise HTTPException(status_code=404, detail="Usuari no trobat")

    if target.data['id'] == user['id']:
        raise HTTPException(status_code=400, detail="No et pots eliminar a tu mateix")

    target_name = target.data.get('full_name', target.data.get('email', user_id))
    supabase.table('profiles').delete().eq('id', user_id).execute()

    await log_audit(user.get('tenant_id'), user['id'], 'delete_user', 'profiles', user_id,
                    f"Usuari '{target_name}' eliminat pel superadmin")
    return {"ok": True, "deleted": target_name}
