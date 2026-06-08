"""
Cases Router - CRUD, status, assignment for internal cases
"""
from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional, List
import logging
from datetime import datetime, timezone
import uuid
from database import get_supabase_admin
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases", tags=["Cases"])


class CaseCreate(BaseModel):
    conversation_id: str
    title: str
    description: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    priority: Optional[str] = "normal"
    case_type: Optional[str] = None
    initial_note: Optional[str] = None
    message_ids: Optional[List[str]] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    case_type: Optional[str] = None


class CaseStatusChange(BaseModel):
    status: str


class CaseAssign(BaseModel):
    agent_id: Optional[str] = None


class LinkMessages(BaseModel):
    message_ids: List[str]


async def get_user_from_token(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticat")
    token = authorization.replace("Bearer ", "")
    admin_client = get_supabase_admin()
    try:
        user_response = admin_client.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Token invalid")
        profile = admin_client.table('profiles').select('id, full_name, role').eq('id', user_response.user.id).single().execute()
        if not profile.data:
            raise HTTPException(status_code=401, detail="Perfil no trobat")
        return profile.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Error d'autenticacio")


@router.get("")
async def list_all_cases(
    authorization: Optional[str] = Header(None),
    status: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    unassigned: Optional[bool] = Query(None),
    conversation_id: Optional[str] = Query(None),
):
    """List cases with filters"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        query = supabase.table('cases').select('*').order('last_activity_at', desc=True)
        if status:
            query = query.eq('status', status)
        if assigned_to == "me":
            query = query.eq('assigned_agent_id', user['id'])
        elif assigned_to:
            query = query.eq('assigned_agent_id', assigned_to)
        if unassigned:
            query = query.is_('assigned_agent_id', 'null')
        if conversation_id:
            query = query.eq('conversation_id', conversation_id)
        result = query.execute()
        cases = result.data or []
        # Enrich with agent names
        agent_ids = list(set(c.get('assigned_agent_id') for c in cases if c.get('assigned_agent_id')))
        agents_map = {}
        if agent_ids:
            agents_res = supabase.table('profiles').select('id, full_name').in_('id', agent_ids).execute()
            agents_map = {a['id']: a['full_name'] for a in (agents_res.data or [])}
        for c in cases:
            c['assigned_agent_name'] = agents_map.get(c.get('assigned_agent_id'))
        return cases
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List cases error: {e}")
        raise HTTPException(status_code=500, detail="Error carregant casos")


@router.post("")
async def create_case(req: CaseCreate, authorization: Optional[str] = Header(None)):
    """Create a new case, optionally linking messages"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        now = datetime.now(timezone.utc).isoformat()
        case_id = str(uuid.uuid4())
        case_data = {
            'id': case_id,
            'conversation_id': req.conversation_id,
            'title': req.title,
            'description': req.description,
            'status': 'per_atendre',
            'assigned_agent_id': req.assigned_agent_id,
            'priority': req.priority or 'normal',
            'case_type': req.case_type,
            'created_by': user['id'],
            'created_at': now,
            'updated_at': now,
            'last_activity_at': now,
            'is_active': True,
        }
        supabase.table('cases').insert(case_data).execute()

        # Link messages if provided
        if req.message_ids:
            for mid in req.message_ids:
                supabase.table('messages').update({
                    'case_id': case_id,
                    'needs_classification': False
                }).eq('id', mid).execute()

        # Create initial note if provided
        if req.initial_note:
            supabase.table('case_notes').insert({
                'id': str(uuid.uuid4()),
                'case_id': case_id,
                'author_id': user['id'],
                'note': req.initial_note,
                'created_at': now,
            }).execute()

        # Log creation event
        supabase.table('case_events').insert({
            'id': str(uuid.uuid4()),
            'case_id': case_id,
            'actor_id': user['id'],
            'event_type': 'case_created',
            'new_value': {'title': req.title, 'messages_linked': len(req.message_ids or [])},
            'created_at': now,
        }).execute()

        # If assigned, log assignment event
        if req.assigned_agent_id:
            supabase.table('case_events').insert({
                'id': str(uuid.uuid4()),
                'case_id': case_id,
                'actor_id': user['id'],
                'event_type': 'assignment',
                'new_value': {'agent_id': req.assigned_agent_id},
                'created_at': now,
            }).execute()

        return {**case_data, 'assigned_agent_name': None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create case error: {e}")
        raise HTTPException(status_code=500, detail=f"Error creant cas: {str(e)}")


@router.get("/{case_id}")
async def get_case(case_id: str, authorization: Optional[str] = Header(None)):
    """Get case detail"""
    await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        result = supabase.table('cases').select('*').eq('id', case_id).single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Cas no trobat")
        case = result.data
        if case.get('assigned_agent_id'):
            agent_res = supabase.table('profiles').select('id, full_name').eq('id', case['assigned_agent_id']).single().execute()
            case['assigned_agent'] = agent_res.data if agent_res.data else None
        else:
            case['assigned_agent'] = None
        # Count linked messages
        msg_count = supabase.table('messages').select('id', count='exact').eq('case_id', case_id).execute()
        case['message_count'] = msg_count.count if msg_count.count is not None else 0
        return case
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get case error: {e}")
        raise HTTPException(status_code=500, detail="Error carregant cas")


@router.patch("/{case_id}")
async def update_case(case_id: str, req: CaseUpdate, authorization: Optional[str] = Header(None)):
    """Update case title, description, priority, type"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        now = datetime.now(timezone.utc).isoformat()
        update_data = {'updated_at': now}
        if req.title is not None:
            update_data['title'] = req.title
        if req.description is not None:
            update_data['description'] = req.description
        if req.priority is not None:
            update_data['priority'] = req.priority
        if req.case_type is not None:
            update_data['case_type'] = req.case_type
        supabase.table('cases').update(update_data).eq('id', case_id).execute()
        return {"ok": True}
    except Exception as e:
        logger.error(f"Update case error: {e}")
        raise HTTPException(status_code=500, detail="Error actualitzant cas")


@router.patch("/{case_id}/status")
async def change_case_status(case_id: str, req: CaseStatusChange, authorization: Optional[str] = Header(None)):
    """Change case status"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        current = supabase.table('cases').select('status').eq('id', case_id).single().execute()
        if not current.data:
            raise HTTPException(status_code=404, detail="Cas no trobat")
        old_status = current.data['status']
        now = datetime.now(timezone.utc).isoformat()
        update = {'status': req.status, 'updated_at': now, 'last_activity_at': now}
        if req.status in ['resolt', 'tancat']:
            update['is_active'] = False
        else:
            update['is_active'] = True
        supabase.table('cases').update(update).eq('id', case_id).execute()
        supabase.table('case_events').insert({
            'id': str(uuid.uuid4()),
            'case_id': case_id,
            'actor_id': user['id'],
            'event_type': 'status_change',
            'old_value': {'status': old_status},
            'new_value': {'status': req.status},
            'created_at': now,
        }).execute()
        return {"status": req.status, "previous": old_status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status change error: {e}")
        raise HTTPException(status_code=500, detail="Error canviant estat")


@router.post("/{case_id}/assign")
async def assign_case(case_id: str, req: CaseAssign, authorization: Optional[str] = Header(None)):
    """Assign/reassign case"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        current = supabase.table('cases').select('assigned_agent_id').eq('id', case_id).single().execute()
        if not current.data:
            raise HTTPException(status_code=404, detail="Cas no trobat")
        old_agent_id = current.data.get('assigned_agent_id')
        new_agent_id = req.agent_id if req.agent_id else user['id']
        now = datetime.now(timezone.utc).isoformat()

        supabase.table('cases').update({
            'assigned_agent_id': new_agent_id, 'updated_at': now, 'last_activity_at': now
        }).eq('id', case_id).execute()

        # Resolve agent names for the event
        old_agent_name = None
        if old_agent_id:
            old_res = supabase.table('profiles').select('full_name').eq('id', old_agent_id).single().execute()
            old_agent_name = old_res.data['full_name'] if old_res.data else None

        new_res = supabase.table('profiles').select('full_name').eq('id', new_agent_id).single().execute()
        new_agent_name = new_res.data['full_name'] if new_res.data else None

        event_type = 'assignment' if not old_agent_id else 'reassignment'
        supabase.table('case_events').insert({
            'id': str(uuid.uuid4()),
            'case_id': case_id,
            'actor_id': user['id'],
            'event_type': event_type,
            'old_value': {'agent_id': old_agent_id, 'agent_name': old_agent_name} if old_agent_id else None,
            'new_value': {'agent_id': new_agent_id, 'agent_name': new_agent_name},
            'created_at': now,
        }).execute()

        return {"assigned_agent_id": new_agent_id, "agent_name": new_agent_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assign case error: {e}")
        raise HTTPException(status_code=500, detail="Error assignant cas")


@router.post("/{case_id}/link-messages")
async def link_messages(case_id: str, req: LinkMessages, authorization: Optional[str] = Header(None)):
    """Link messages to an existing case"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        now = datetime.now(timezone.utc).isoformat()
        for mid in req.message_ids:
            supabase.table('messages').update({
                'case_id': case_id,
                'needs_classification': False
            }).eq('id', mid).execute()
        supabase.table('cases').update({'last_activity_at': now, 'updated_at': now}).eq('id', case_id).execute()
        supabase.table('case_events').insert({
            'id': str(uuid.uuid4()),
            'case_id': case_id,
            'actor_id': user['id'],
            'event_type': 'messages_linked',
            'new_value': {'message_ids': req.message_ids, 'count': len(req.message_ids)},
            'created_at': now,
        }).execute()
        return {"ok": True, "linked": len(req.message_ids)}
    except Exception as e:
        logger.error(f"Link messages error: {e}")
        raise HTTPException(status_code=500, detail="Error vinculant missatges")


@router.post("/{case_id}/unlink-messages")
async def unlink_messages(case_id: str, req: LinkMessages, authorization: Optional[str] = Header(None)):
    """Unlink messages from a case"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        now = datetime.now(timezone.utc).isoformat()
        for mid in req.message_ids:
            supabase.table('messages').update({
                'case_id': None,
                'needs_classification': True
            }).eq('id', mid).eq('case_id', case_id).execute()
        supabase.table('case_events').insert({
            'id': str(uuid.uuid4()),
            'case_id': case_id,
            'actor_id': user['id'],
            'event_type': 'messages_unlinked',
            'new_value': {'message_ids': req.message_ids, 'count': len(req.message_ids)},
            'created_at': now,
        }).execute()
        return {"ok": True, "unlinked": len(req.message_ids)}
    except Exception as e:
        logger.error(f"Unlink messages error: {e}")
        raise HTTPException(status_code=500, detail="Error desvinculant missatges")


@router.get("/{case_id}/notes")
async def list_case_notes(case_id: str, authorization: Optional[str] = Header(None)):
    """List notes for a case"""
    await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        result = supabase.table('case_notes').select('*').eq('case_id', case_id).order('created_at', desc=False).execute()
        notes = result.data or []
        author_ids = list(set(n.get('author_id') for n in notes if n.get('author_id')))
        authors_map = {}
        if author_ids:
            a_res = supabase.table('profiles').select('id, full_name').in_('id', author_ids).execute()
            authors_map = {a['id']: a['full_name'] for a in (a_res.data or [])}
        for n in notes:
            n['author_name'] = authors_map.get(n.get('author_id'), '?')
        return notes
    except Exception as e:
        logger.error(f"List notes error: {e}")
        raise HTTPException(status_code=500, detail="Error carregant notes")


class NoteBody(BaseModel):
    note: str


@router.post("/{case_id}/notes")
async def create_case_note(case_id: str, req: NoteBody, authorization: Optional[str] = Header(None)):
    """Create a note on a case"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        now = datetime.now(timezone.utc).isoformat()
        note_data = {
            'id': str(uuid.uuid4()),
            'case_id': case_id,
            'author_id': user['id'],
            'note': req.note,
            'created_at': now,
        }
        supabase.table('case_notes').insert(note_data).execute()
        supabase.table('case_events').insert({
            'id': str(uuid.uuid4()),
            'case_id': case_id,
            'actor_id': user['id'],
            'event_type': 'note_created',
            'new_value': {'note_preview': req.note[:80]},
            'created_at': now,
        }).execute()
        note_data['author_name'] = user['full_name']
        return note_data
    except Exception as e:
        logger.error(f"Create note error: {e}")
        raise HTTPException(status_code=500, detail="Error creant nota")


@router.put("/{case_id}/notes/{note_id}")
async def update_case_note(case_id: str, note_id: str, req: NoteBody, authorization: Optional[str] = Header(None)):
    """Update a note (only author can edit)"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        existing = supabase.table('case_notes').select('id, author_id').eq('id', note_id).eq('case_id', case_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Nota no trobada")
        if existing.data[0]['author_id'] != user['id']:
            raise HTTPException(status_code=403, detail="Només l'autor pot editar la nota")

        now = datetime.now(timezone.utc).isoformat()
        update_data = {'note': req.note}
        try:
            supabase.table('case_notes').update({**update_data, 'updated_at': now}).eq('id', note_id).execute()
        except Exception:
            supabase.table('case_notes').update(update_data).eq('id', note_id).execute()
        return {"ok": True, "id": note_id, "note": req.note, "updated_at": now}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update note error: {e}")
        raise HTTPException(status_code=500, detail="Error actualitzant nota")


@router.delete("/{case_id}/notes/{note_id}")
async def delete_case_note(case_id: str, note_id: str, authorization: Optional[str] = Header(None)):
    """Delete a note (only author can delete)"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        existing = supabase.table('case_notes').select('id, author_id').eq('id', note_id).eq('case_id', case_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Nota no trobada")
        if existing.data[0]['author_id'] != user['id']:
            raise HTTPException(status_code=403, detail="Només l'autor pot eliminar la nota")

        supabase.table('case_notes').delete().eq('id', note_id).execute()
        return {"ok": True, "deleted": note_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete note error: {e}")
        raise HTTPException(status_code=500, detail="Error eliminant nota")


@router.get("/{case_id}/events")
async def list_case_events(case_id: str, authorization: Optional[str] = Header(None)):
    """List events for a case (audit trail)"""
    await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        result = supabase.table('case_events').select('*').eq('case_id', case_id).order('created_at', desc=False).execute()
        events = result.data or []
        actor_ids = list(set(e.get('actor_id') for e in events if e.get('actor_id')))
        actors_map = {}
        if actor_ids:
            a_res = supabase.table('profiles').select('id, full_name').in_('id', actor_ids).execute()
            actors_map = {a['id']: a['full_name'] for a in (a_res.data or [])}
        for e in events:
            e['actor_name'] = actors_map.get(e.get('actor_id'), 'Sistema')
        return events
    except Exception as e:
        logger.error(f"List events error: {e}")
        raise HTTPException(status_code=500, detail="Error carregant historial")


@router.post("/{case_id}/view")
async def register_view(case_id: str, authorization: Optional[str] = Header(None)):
    """Register that an agent is viewing a case"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        now = datetime.now(timezone.utc).isoformat()
        supabase.table('case_views').insert({
            'id': str(uuid.uuid4()),
            'case_id': case_id,
            'agent_id': user['id'],
            'viewed_at': now,
        }).execute()
        return {"ok": True}
    except Exception as e:
        return {"ok": False}


@router.get("/{case_id}/viewers")
async def get_case_viewers(case_id: str, authorization: Optional[str] = Header(None)):
    """Get agents currently viewing this case"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        from datetime import timedelta
        threshold = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        result = supabase.table('case_views').select('agent_id, viewed_at').eq('case_id', case_id).gte('viewed_at', threshold).execute()
        viewers = []
        if result.data:
            agent_ids = list(set(v['agent_id'] for v in result.data if v['agent_id'] != user['id']))
            if agent_ids:
                a_res = supabase.table('profiles').select('id, full_name').in_('id', agent_ids).execute()
                viewers = [{'id': a['id'], 'name': a['full_name']} for a in (a_res.data or [])]
        return viewers
    except Exception as e:
        return []
