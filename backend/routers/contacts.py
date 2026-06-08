"""
Contacts Router - CRUD contact info
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from pydantic import BaseModel
import logging
import uuid
from datetime import datetime, timezone
from database import get_supabase_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contacts", tags=["Contacts"])


class ContactCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    notes: Optional[str] = None


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


async def get_user_from_token(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticat")
    token = authorization.replace("Bearer ", "")
    admin_client = get_supabase_admin()
    try:
        user_response = admin_client.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Token invalid")
        profile = admin_client.table('profiles').select('id, full_name, role, tenant_id').eq('id', user_response.user.id).single().execute()
        if not profile.data:
            raise HTTPException(status_code=401, detail="Perfil no trobat")
        return profile.data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Error d'autenticacio")


@router.post("")
async def create_contact(req: ContactCreate, authorization: Optional[str] = Header(None)):
    """Create a new contact — admin and super_admin only"""
    user = await get_user_from_token(authorization)
    if user.get('role') == 'agent':
        raise HTTPException(status_code=403, detail="Els agents no poden crear contactes")
    supabase = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    try:
        contact = {
            'id': str(uuid.uuid4()),
            'name': req.name.strip(),
            'phone': req.phone.strip(),
            'email': req.email.strip() if req.email else None,
            'notes': req.notes.strip() if req.notes else None,
            'tenant_id': user.get('tenant_id'),
            'created_at': now,
            'updated_at': now,
        }
        supabase.table('contacts').insert(contact).execute()
        return contact
    except Exception as e:
        logger.error(f"Create contact error: {e}")
        raise HTTPException(status_code=500, detail="Error creant contacte")


@router.put("/{contact_id}")
async def update_contact(contact_id: str, req: ContactUpdate, authorization: Optional[str] = Header(None)):
    """Update contact information"""
    await get_user_from_token(authorization)
    supabase = get_supabase_admin()

    try:
        updates = {}
        if req.name is not None:
            updates['name'] = req.name.strip()
        if req.email is not None:
            updates['email'] = req.email.strip() if req.email.strip() else None
        if req.phone is not None:
            updates['phone'] = req.phone.strip()
        if req.notes is not None:
            updates['notes'] = req.notes.strip() if req.notes.strip() else None

        if not updates:
            raise HTTPException(status_code=400, detail="Cap camp per actualitzar")

        updates['updated_at'] = datetime.now(timezone.utc).isoformat()

        result = supabase.table('contacts').update(updates).eq('id', contact_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Contacte no trobat")

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update contact error: {e}")
        raise HTTPException(status_code=500, detail="Error actualitzant contacte")
