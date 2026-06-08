"""
Contacts Router - Update contact info
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from pydantic import BaseModel
import logging
from datetime import datetime, timezone
from database import get_supabase_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contacts", tags=["Contacts"])


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
