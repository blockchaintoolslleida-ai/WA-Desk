"""
Conversations Router - List, detail, with case counts and derived status
Optimized: batch queries instead of N+1
"""
from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional
from pydantic import BaseModel
import logging
import uuid
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import asyncio
from database import get_supabase_admin
from routers.window import get_last_incoming_timestamp, compute_window_status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["Conversations"])


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


def compute_derived_status(cases_list):
    if not cases_list:
        return 'sense_casos'
    active_statuses = [c['status'] for c in cases_list if c.get('is_active', True)]
    if any(s in ['nou', 'per_atendre'] for s in active_statuses):
        return 'amb_pendents'
    if any(s == 'en_atencio' for s in active_statuses):
        return 'en_atencio'
    if any(s == 'esperant_client' for s in active_statuses):
        return 'esperant_client'
    return 'sense_pendents'


@router.get("")
async def list_conversations(
    authorization: Optional[str] = Header(None),
    filter_type: Optional[str] = Query(None, alias="filter"),
    search: Optional[str] = Query(None),
):
    """List conversations - optimized with batch queries (4 total instead of 3*N)"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()

    try:
        # BATCH QUERY 1: Conversations filtered by tenant
        tenant_id = user.get('tenant_id')
        try:
            conv_query = supabase.table('conversations').select(
                '*, contacts(id, name, phone, email)'
            )
            if tenant_id and user.get('role') != 'super_admin':
                conv_query = conv_query.eq('tenant_id', tenant_id)
            conv_res = conv_query.order('last_message_at', desc=True).execute()
            conversations = conv_res.data or []
        except Exception as e:
            # Fallback: if tenant_id column doesn't exist yet, fetch all
            if 'tenant_id' in str(e) and 'does not exist' in str(e):
                logger.warning("conversations.tenant_id column missing - run supabase_tenant_isolation_migration.sql")
                conv_res = supabase.table('conversations').select(
                    '*, contacts(id, name, phone, email)'
                ).order('last_message_at', desc=True).execute()
                conversations = conv_res.data or []
            else:
                raise

        if not conversations:
            return []

        conv_ids = [c['id'] for c in conversations]

        # Run 3 batch queries IN PARALLEL using threads
        def fetch_cases():
            return supabase.table('cases').select(
                'id, conversation_id, status, assigned_agent_id, is_active, title'
            ).in_('conversation_id', conv_ids).execute()

        def fetch_unclassified():
            return supabase.table('messages').select(
                'id, conversation_id'
            ).in_('conversation_id', conv_ids).eq('needs_classification', True).execute()

        def fetch_recent_msgs():
            return supabase.table('messages').select(
                'conversation_id, body, direction, sent_at'
            ).in_('conversation_id', conv_ids).order('sent_at', desc=True).limit(500).execute()

        def fetch_last_incoming():
            return supabase.table('messages').select(
                'conversation_id, sent_at'
            ).in_('conversation_id', conv_ids).eq('direction', 'incoming').order('sent_at', desc=True).limit(500).execute()

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=4) as pool:
            all_cases_res, unclass_res, recent_msgs_res, incoming_res = await asyncio.gather(
                loop.run_in_executor(pool, fetch_cases),
                loop.run_in_executor(pool, fetch_unclassified),
                loop.run_in_executor(pool, fetch_recent_msgs),
                loop.run_in_executor(pool, fetch_last_incoming),
            )

        all_cases = all_cases_res.data or []

        # Group cases by conversation_id
        cases_by_conv = {}
        for c in all_cases:
            cid = c['conversation_id']
            if cid not in cases_by_conv:
                cases_by_conv[cid] = []
            cases_by_conv[cid].append(c)

        unclass_msgs = unclass_res.data or []
        unclass_by_conv = {}
        for m in unclass_msgs:
            cid = m['conversation_id']
            unclass_by_conv[cid] = unclass_by_conv.get(cid, 0) + 1

        recent_msgs = recent_msgs_res.data or []

        # Pick last message per conversation
        last_msg_by_conv = {}
        for m in recent_msgs:
            cid = m['conversation_id']
            if cid not in last_msg_by_conv:
                last_msg_by_conv[cid] = m

        # Last incoming message per conversation (for 24h window)
        incoming_msgs = incoming_res.data or []
        last_incoming_by_conv = {}
        for m in incoming_msgs:
            cid = m['conversation_id']
            if cid not in last_incoming_by_conv:
                last_incoming_by_conv[cid] = m['sent_at']

        # Collect all agent IDs for a single profile lookup
        all_agent_ids = set()
        for cases_list in cases_by_conv.values():
            for c in cases_list:
                if c.get('assigned_agent_id'):
                    all_agent_ids.add(c['assigned_agent_id'])

        agents_map = {}
        if all_agent_ids:
            agents_res = supabase.table('profiles').select('id, full_name').in_('id', list(all_agent_ids)).execute()
            agents_map = {a['id']: a['full_name'] for a in (agents_res.data or [])}

        # Search filter (applied before enrichment to skip unnecessary work)
        if search and search.strip():
            s = search.strip().lower()
            conversations = [c for c in conversations if
                s in (c.get('contacts', {}) or {}).get('name', '').lower() or
                s in (c.get('contacts', {}) or {}).get('phone', '').lower()
            ]

        # Enrich all conversations in Python (no more HTTP calls!)
        enriched = []
        for conv in conversations:
            conv['contact'] = conv.pop('contacts', None)
            conv_id = conv['id']
            conv_cases = cases_by_conv.get(conv_id, [])

            active_cases = [c for c in conv_cases if c.get('is_active', True)]
            pending_cases = [c for c in active_cases if c['status'] in ['nou', 'per_atendre']]

            conv['cases_count'] = len(active_cases)
            conv['pending_cases'] = len(pending_cases)
            conv['derived_status'] = compute_derived_status(conv_cases)
            conv['unclassified_count'] = unclass_by_conv.get(conv_id, 0)

            agent_ids = list(set(c.get('assigned_agent_id') for c in active_cases if c.get('assigned_agent_id')))
            conv['agent_ids'] = agent_ids
            conv['agent_names'] = [agents_map.get(aid, '?') for aid in agent_ids]

            last_msg = last_msg_by_conv.get(conv_id)
            if last_msg:
                conv['last_message_body'] = (last_msg.get('body') or '')[:120]
                conv['last_message_direction'] = last_msg.get('direction')
            else:
                conv['last_message_body'] = None
                conv['last_message_direction'] = None

            # Window 24h status
            last_incoming_str = last_incoming_by_conv.get(conv_id)
            if last_incoming_str:
                last_incoming_dt = datetime.fromisoformat(last_incoming_str.replace('Z', '+00:00'))
                conv['window'] = compute_window_status(last_incoming_dt)
            else:
                conv['window'] = compute_window_status(None)

            enriched.append(conv)

        # Apply filters (all in Python, no extra queries)
        if filter_type == 'with_pending':
            enriched = [c for c in enriched if c['pending_cases'] > 0 or c['unclassified_count'] > 0]
        elif filter_type == 'in_progress':
            enriched = [c for c in enriched if c['derived_status'] == 'en_atencio']
        elif filter_type == 'unassigned':
            enriched = [c for c in enriched if
                any(not cs.get('assigned_agent_id') for cs in cases_by_conv.get(c['id'], []) if cs.get('is_active', True))
                or c['cases_count'] == 0]
        elif filter_type == 'mine':
            enriched = [c for c in enriched if user['id'] in c.get('agent_ids', [])]
        elif filter_type == 'unread':
            enriched = [c for c in enriched if c.get('unread_count', 0) > 0]
        elif filter_type == 'closed':
            enriched = [c for c in enriched if c['derived_status'] == 'sense_pendents' and c['cases_count'] > 0]

        return enriched

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List conversations error: {e}")
        raise HTTPException(status_code=500, detail="Error carregant converses")


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, authorization: Optional[str] = Header(None)):
    """Get single conversation with contact and cases"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()

    try:
        result = supabase.table('conversations').select(
            '*, contacts(id, name, phone, email, notes)'
        ).eq('id', conversation_id).single().execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Conversa no trobada")

        conv = result.data

        # Tenant isolation check (skip if column doesn't exist yet)
        tenant_id = user.get('tenant_id')
        if tenant_id and user.get('role') != 'super_admin':
            if conv.get('tenant_id') and conv['tenant_id'] != tenant_id:
                raise HTTPException(status_code=403, detail="Accés denegat")

        conv['contact'] = conv.pop('contacts', None)

        # Get cases
        cases_res = supabase.table('cases').select('*').eq(
            'conversation_id', conversation_id
        ).order('created_at', desc=False).execute()
        conv['cases'] = cases_res.data or []

        # Enrich cases with agent names
        agent_ids = list(set(c.get('assigned_agent_id') for c in conv['cases'] if c.get('assigned_agent_id')))
        agents_map = {}
        if agent_ids:
            agents_res = supabase.table('profiles').select('id, full_name').in_('id', agent_ids).execute()
            agents_map = {a['id']: a['full_name'] for a in (agents_res.data or [])}
        for c in conv['cases']:
            c['assigned_agent_name'] = agents_map.get(c.get('assigned_agent_id'))

        conv['derived_status'] = compute_derived_status(conv['cases'])

        # Unclassified count
        unclass_res = supabase.table('messages').select('id', count='exact').eq(
            'conversation_id', conversation_id
        ).eq('needs_classification', True).execute()
        conv['unclassified_count'] = unclass_res.count if unclass_res.count is not None else 0

        # Window 24h status
        last_incoming = get_last_incoming_timestamp(supabase, conversation_id)
        conv['window'] = compute_window_status(last_incoming)
        conv['window']['last_customer_message_at'] = last_incoming.isoformat() if last_incoming else None

        return conv

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get conversation error: {e}")
        raise HTTPException(status_code=500, detail="Error carregant conversa")


@router.get("/{conversation_id}/messages")
async def list_conversation_messages(
    conversation_id: str,
    authorization: Optional[str] = Header(None),
    case_id: Optional[str] = Query(None),
    unclassified_only: Optional[bool] = Query(None),
):
    """List messages for a conversation, optionally filtered by case"""
    await get_user_from_token(authorization)
    supabase = get_supabase_admin()

    try:
        query = supabase.table('messages').select('*').eq(
            'conversation_id', conversation_id
        ).order('sent_at', desc=False)

        if case_id:
            query = query.eq('case_id', case_id)
        if unclassified_only:
            query = query.eq('needs_classification', True)

        result = query.execute()
        messages = result.data or []

        # Enrich with agent names
        agent_ids = list(set(m.get('sender_agent_id') for m in messages if m.get('sender_agent_id')))
        agents_map = {}
        if agent_ids:
            agents_res = supabase.table('profiles').select('id, full_name').in_('id', agent_ids).execute()
            agents_map = {a['id']: a['full_name'] for a in (agents_res.data or [])}

        for m in messages:
            m['sender_agent_name'] = agents_map.get(m.get('sender_agent_id'))

        return messages

    except Exception as e:
        logger.error(f"List messages error: {e}")
        raise HTTPException(status_code=500, detail="Error carregant missatges")


@router.post("/{conversation_id}/read")
async def mark_read(conversation_id: str, authorization: Optional[str] = Header(None)):
    """Mark conversation as read"""
    await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        supabase.table('conversations').update({'unread_count': 0}).eq('id', conversation_id).execute()
        return {"ok": True}
    except Exception:
        return {"ok": False}


class CreateConversationRequest(BaseModel):
    contact_id: str


@router.post("")
async def create_conversation(req: CreateConversationRequest, authorization: Optional[str] = Header(None)):
    """Create a new conversation for a contact"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    try:
        # Verify contact exists
        contact = supabase.table('contacts').select('id,name,phone').eq('id', req.contact_id).single().execute()
        if not contact.data:
            raise HTTPException(status_code=404, detail="Contacte no trobat")

        conv_id = str(uuid.uuid4())
        conv_data = {
            'id': conv_id,
            'contact_id': req.contact_id,
            'status': None,
            'last_message_at': now,
            'unread_count': 0,
            'is_active': True,
            'tenant_id': user.get('tenant_id'),
            'created_at': now,
            'updated_at': now,
        }
        supabase.table('conversations').insert(conv_data).execute()

        # Return conversation with contact info
        result = supabase.table('conversations').select('*, contacts(id, name, phone)').eq('id', conv_id).single().execute()
        return result.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create conversation error: {e}")
        raise HTTPException(status_code=500, detail="Error creant conversa")


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str, authorization: Optional[str] = Header(None)):
    """Hard-delete a conversation and all associated data (messages, cases, events, notes)"""
    await get_user_from_token(authorization)
    supabase = get_supabase_admin()
    try:
        # Delete all associated data in order (respecting FK constraints)
        # Find cases linked to this conversation
        cases = supabase.table('cases').select('id').eq('conversation_id', conversation_id).execute()
        case_ids = [c['id'] for c in (cases.data or [])]

        for cid in case_ids:
            supabase.table('case_events').delete().eq('case_id', cid).execute()
            supabase.table('case_notes').delete().eq('case_id', cid).execute()
            supabase.table('case_views').delete().eq('case_id', cid).execute()
        supabase.table('cases').delete().eq('conversation_id', conversation_id).execute()
        supabase.table('messages').delete().eq('conversation_id', conversation_id).execute()
        supabase.table('conversations').delete().eq('id', conversation_id).execute()

        return {"ok": True, "deleted": True, "hard": True}
    except Exception as e:
        logger.error(f"Delete conversation error: {e}")
        raise HTTPException(status_code=500, detail="Error eliminant conversa")
