"""
Contacts Router — Full CRUD + search + start conversation
"""
from fastapi import APIRouter, HTTPException, Header, Query
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


# ── LIST ──────────────────────────────────────────────────────

@router.get("")
async def list_contacts(
    authorization: Optional[str] = Header(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """List contacts with optional search, paginated"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    try:
        query = supabase.table('contacts').select('*', count='exact')

        # Tenant filter
        if tenant_id and user.get('role') != 'super_admin':
            query = query.eq('tenant_id', tenant_id)

        # Search
        if search:
            q = search.strip()
            # SQLite doesn't support OR in Supabase client, so we filter in Python
            query = query.order('name')

        result = query.order('name').execute()
        contacts = result.data or []

        # Apply search filter in Python (name, phone, email)
        if search:
            q = search.strip().lower()
            contacts = [c for c in contacts if
                        q in (c.get('name') or '').lower() or
                        q in (c.get('phone') or '').lower() or
                        q in (c.get('email') or '').lower()]

        total = len(contacts)
        # Paginate manually
        start = (page - 1) * limit
        end = start + limit

        return {
            "contacts": contacts[start:end],
            "total": total,
            "page": page,
            "pages": max(1, (total + limit - 1) // limit),
        }

    except Exception as e:
        logger.error(f"List contacts error: {e}")
        raise HTTPException(status_code=500, detail="Error carregant contactes")


# ── SEARCH ────────────────────────────────────────────────────

@router.get("/search")
async def search_contacts(
    q: str = Query(..., min_length=1),
    authorization: Optional[str] = Header(None),
):
    """Quick search contacts — returns top 20 matches"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    tenant_id = user.get('tenant_id')

    try:
        query = supabase.table('contacts').select('id, name, phone, email, source')
        if tenant_id and user.get('role') != 'super_admin':
            query = query.eq('tenant_id', tenant_id)
        query = query.order('name').limit(100).execute()
        contacts = query.data or []

        ql = q.strip().lower()
        matches = [c for c in contacts if
                   ql in (c.get('name') or '').lower() or
                   ql in (c.get('phone') or '').lower() or
                   ql in (c.get('email') or '').lower()]
        return matches[:20]

    except Exception as e:
        logger.error(f"Search contacts error: {e}")
        raise HTTPException(status_code=500, detail="Error cercant contactes")


# ── GET SINGLE ────────────────────────────────────────────────

@router.get("/{contact_id}")
async def get_contact(contact_id: str, authorization: Optional[str] = Header(None)):
    """Get a single contact by ID"""
    await get_user_from_token(authorization)
    supabase = get_supabase_admin()

    result = supabase.table('contacts').select('*').eq('id', contact_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Contacte no trobat")
    return result.data


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


# ── DELETE ────────────────────────────────────────────────────

@router.delete("/{contact_id}")
async def delete_contact(contact_id: str, authorization: Optional[str] = Header(None)):
    """Hard delete a contact — admin and super_admin only"""
    user = await get_user_from_token(authorization)
    if user.get('role') == 'agent':
        raise HTTPException(status_code=403, detail="Els agents no poden eliminar contactes")
    supabase = get_supabase_admin()

    try:
        existing = supabase.table('contacts').select('id,name').eq('id', contact_id).single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Contacte no trobat")

        # Delete associated conversations first (FK constraint)
        convs = supabase.table('conversations').select('id').eq('contact_id', contact_id).execute()
        for c in (convs.data or []):
            # Delete messages and cases for each conversation
            cases_res = supabase.table('cases').select('id').eq('conversation_id', c['id']).execute()
            for cs in (cases_res.data or []):
                supabase.table('case_events').delete().eq('case_id', cs['id']).execute()
                supabase.table('case_notes').delete().eq('case_id', cs['id']).execute()
                supabase.table('case_views').delete().eq('case_id', cs['id']).execute()
            supabase.table('cases').delete().eq('conversation_id', c['id']).execute()
            supabase.table('messages').delete().eq('conversation_id', c['id']).execute()
        supabase.table('conversations').delete().eq('contact_id', contact_id).execute()
        supabase.table('contacts').delete().eq('id', contact_id).execute()

        return {"ok": True, "deleted": existing.data.get('name', contact_id)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete contact error: {e}")
        raise HTTPException(status_code=500, detail="Error eliminant contacte")


# ── START CONVERSATION ────────────────────────────────────────

@router.post("/{contact_id}/start-conversation")
async def start_conversation(contact_id: str, authorization: Optional[str] = Header(None)):
    """Create a new conversation for a contact and return the conversation ID"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    try:
        contact = supabase.table('contacts').select('id,name,phone').eq('id', contact_id).single().execute()
        if not contact.data:
            raise HTTPException(status_code=404, detail="Contacte no trobat")

        # Check if active conversation already exists
        existing = supabase.table('conversations').select('id').eq(
            'contact_id', contact_id
        ).eq('is_active', True).order('created_at', desc=True).limit(1).execute()

        if existing.data:
            return {"conversation_id": existing.data[0]['id'], "reused": True}

        # Create new conversation
        conv_id = str(uuid.uuid4())
        conv_data = {
            'id': conv_id,
            'contact_id': contact_id,
            'status': None,
            'last_message_at': now,
            'unread_count': 0,
            'is_active': True,
            'tenant_id': user.get('tenant_id'),
            'created_at': now,
            'updated_at': now,
        }
        supabase.table('conversations').insert(conv_data).execute()

        return {"conversation_id": conv_id, "reused": False}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Start conversation error: {e}")
        raise HTTPException(status_code=500, detail="Error iniciant conversa")
