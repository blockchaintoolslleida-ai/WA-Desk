"""
Setup Router - DB check and seed demo data for multi-case model
"""
from fastapi import APIRouter, HTTPException
import logging
from database import get_supabase_admin
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/setup", tags=["Setup"])


@router.get("/check")
async def check_tables():
    supabase = get_supabase_admin()
    tables_status = {}
    for table in ['contacts', 'conversations', 'messages', 'cases', 'case_events', 'case_views', 'case_notes']:
        try:
            supabase.table(table).select('id').limit(1).execute()
            tables_status[table] = "ok"
        except Exception as e:
            tables_status[table] = f"missing: {str(e)[:80]}"
    all_ok = all(v == "ok" for v in tables_status.values())
    return {
        "all_tables_ready": all_ok,
        "tables": tables_status,
        "instruction": "Tot correcte" if all_ok else "Executa supabase_wa_migration_v2.sql"
    }


@router.post("/seed")
async def seed_demo_data():
    supabase = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    try:
        # Clear existing demo data
        supabase.table('case_events').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        supabase.table('case_notes').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        supabase.table('case_views').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        supabase.table('internal_notes').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        supabase.table('conversation_events').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        supabase.table('conversation_views').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        supabase.table('messages').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        supabase.table('cases').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        supabase.table('conversations').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        supabase.table('contacts').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()

        # Get tenant for seed data
        tenant_id = None
        tenants_res = supabase.table('tenants').select('id').limit(1).execute()
        if tenants_res.data:
            tenant_id = tenants_res.data[0]['id']

        # Get agent profiles
        profiles = supabase.table('profiles').select('id, full_name, role').in_(
            'role', ['admin', 'agent', 'tenant_admin', 'supervisor']
        ).execute()
        agent_ids = [p['id'] for p in (profiles.data or [])]
        agent1 = agent_ids[0] if len(agent_ids) > 0 else None
        agent2 = agent_ids[1] if len(agent_ids) > 1 else agent1

        # Create contacts
        contacts = [
            {'id': str(uuid.uuid4()), 'name': 'Joan Garcia', 'phone': '34612345678', 'email': 'joan@example.com', 'tenant_id': tenant_id, 'created_at': now, 'updated_at': now},
            {'id': str(uuid.uuid4()), 'name': 'Maria Lopez', 'phone': '34623456789', 'email': 'maria@example.com', 'tenant_id': tenant_id, 'created_at': now, 'updated_at': now},
            {'id': str(uuid.uuid4()), 'name': 'Pere Martinez', 'phone': '34634567890', 'tenant_id': tenant_id, 'created_at': now, 'updated_at': now},
            {'id': str(uuid.uuid4()), 'name': 'Anna Puig', 'phone': '34645678901', 'email': 'anna@example.com', 'tenant_id': tenant_id, 'created_at': now, 'updated_at': now},
        ]
        supabase.table('contacts').insert(contacts).execute()

        # Create conversations
        convs = [
            {'id': str(uuid.uuid4()), 'contact_id': contacts[0]['id'], 'status': None, 'unread_count': 2, 'is_active': True, 'last_message_at': now, 'tenant_id': tenant_id, 'created_at': now, 'updated_at': now},
            {'id': str(uuid.uuid4()), 'contact_id': contacts[1]['id'], 'status': None, 'unread_count': 0, 'is_active': True, 'last_message_at': now, 'tenant_id': tenant_id, 'created_at': now, 'updated_at': now},
            {'id': str(uuid.uuid4()), 'contact_id': contacts[2]['id'], 'status': None, 'unread_count': 1, 'is_active': True, 'last_message_at': now, 'tenant_id': tenant_id, 'created_at': now, 'updated_at': now},
            {'id': str(uuid.uuid4()), 'contact_id': contacts[3]['id'], 'status': None, 'unread_count': 0, 'is_active': True, 'last_message_at': now, 'tenant_id': tenant_id, 'created_at': now, 'updated_at': now},
        ]
        supabase.table('conversations').insert(convs).execute()

        # Create cases
        # Conv 0 (Joan): 1 case pending
        case1 = {'id': str(uuid.uuid4()), 'conversation_id': convs[0]['id'], 'title': 'Comanda #1234 - Peces frens', 'status': 'per_atendre', 'priority': 'high', 'created_by': agent1, 'is_active': True, 'created_at': now, 'updated_at': now, 'last_activity_at': now}
        # Conv 1 (Maria): 2 cases (multi-case!) - one in progress, one waiting
        case2 = {'id': str(uuid.uuid4()), 'conversation_id': convs[1]['id'], 'title': 'Pressupost suspensio', 'status': 'en_atencio', 'assigned_agent_id': agent1, 'priority': 'normal', 'created_by': agent1, 'is_active': True, 'created_at': now, 'updated_at': now, 'last_activity_at': now}
        case3 = {'id': str(uuid.uuid4()), 'conversation_id': convs[1]['id'], 'title': 'Incidencia entrega #789', 'status': 'esperant_client', 'assigned_agent_id': agent2, 'priority': 'high', 'created_by': agent1, 'is_active': True, 'created_at': now, 'updated_at': now, 'last_activity_at': now}
        # Conv 2 (Pere): no cases, just unclassified message
        # Conv 3 (Anna): 1 resolved case
        case4 = {'id': str(uuid.uuid4()), 'conversation_id': convs[3]['id'], 'title': 'Consulta disponibilitat oli', 'status': 'resolt', 'assigned_agent_id': agent1, 'priority': 'low', 'created_by': agent1, 'is_active': False, 'created_at': now, 'updated_at': now, 'last_activity_at': now}

        all_cases = [case1, case2, case3, case4]
        supabase.table('cases').insert(all_cases).execute()

        # Create messages
        msgs = [
            # Conv 0 (Joan) - messages linked to case1
            {'id': str(uuid.uuid4()), 'conversation_id': convs[0]['id'], 'case_id': case1['id'], 'direction': 'incoming', 'message_type': 'text', 'body': 'Bon dia, necessito peces de frens per a un Seat Leon 2019', 'needs_classification': False, 'sent_at': now, 'created_at': now},
            {'id': str(uuid.uuid4()), 'conversation_id': convs[0]['id'], 'case_id': case1['id'], 'direction': 'incoming', 'message_type': 'text', 'body': 'Em podeu fer un pressupost?', 'needs_classification': False, 'sent_at': now, 'created_at': now},
            # Conv 1 (Maria) - multi-case messages
            {'id': str(uuid.uuid4()), 'conversation_id': convs[1]['id'], 'case_id': case2['id'], 'direction': 'incoming', 'message_type': 'text', 'body': 'Hola, vull un pressupost per canviar la suspensio', 'needs_classification': False, 'sent_at': now, 'created_at': now},
            {'id': str(uuid.uuid4()), 'conversation_id': convs[1]['id'], 'case_id': case2['id'], 'direction': 'outgoing', 'message_type': 'text', 'body': 'Bon dia Maria! Estem preparant el pressupost.', 'sender_agent_id': agent1, 'needs_classification': False, 'sent_at': now, 'created_at': now},
            {'id': str(uuid.uuid4()), 'conversation_id': convs[1]['id'], 'case_id': case3['id'], 'direction': 'incoming', 'message_type': 'text', 'body': 'Per cert, tinc un problema amb l\'entrega #789, no ha arribat', 'needs_classification': False, 'sent_at': now, 'created_at': now},
            {'id': str(uuid.uuid4()), 'conversation_id': convs[1]['id'], 'case_id': case3['id'], 'direction': 'outgoing', 'message_type': 'text', 'body': 'Estem verificant amb el transportista. Et confirmo demà.', 'sender_agent_id': agent2, 'needs_classification': False, 'sent_at': now, 'created_at': now},
            # New unclassified message from Maria (which case?)
            {'id': str(uuid.uuid4()), 'conversation_id': convs[1]['id'], 'direction': 'incoming', 'message_type': 'text', 'body': 'Hola, alguna novetat?', 'needs_classification': True, 'sent_at': now, 'created_at': now},
            # Conv 2 (Pere) - no case, just unclassified
            {'id': str(uuid.uuid4()), 'conversation_id': convs[2]['id'], 'direction': 'incoming', 'message_type': 'text', 'body': 'Bon dia, necessito informacio sobre filtres d\'aire', 'needs_classification': True, 'sent_at': now, 'created_at': now},
            # Conv 3 (Anna) - resolved case
            {'id': str(uuid.uuid4()), 'conversation_id': convs[3]['id'], 'case_id': case4['id'], 'direction': 'incoming', 'message_type': 'text', 'body': 'Teniu oli 5W40 en stock?', 'needs_classification': False, 'sent_at': now, 'created_at': now},
            {'id': str(uuid.uuid4()), 'conversation_id': convs[3]['id'], 'case_id': case4['id'], 'direction': 'outgoing', 'message_type': 'text', 'body': 'Si, tenim 3 unitats disponibles. Vols que te\'l reservem?', 'sender_agent_id': agent1, 'needs_classification': False, 'sent_at': now, 'created_at': now},
            {'id': str(uuid.uuid4()), 'conversation_id': convs[3]['id'], 'case_id': case4['id'], 'direction': 'incoming', 'message_type': 'text', 'body': 'Si, perfect. Gracies!', 'needs_classification': False, 'sent_at': now, 'created_at': now},
        ]
        supabase.table('messages').insert(msgs).execute()

        # Create notes
        if agent1:
            supabase.table('case_notes').insert([
                {'id': str(uuid.uuid4()), 'case_id': case2['id'], 'author_id': agent1, 'note': 'Client habitual - prioritzar pressupost', 'created_at': now},
                {'id': str(uuid.uuid4()), 'case_id': case3['id'], 'author_id': agent2 or agent1, 'note': 'Transportista confirma entrega per demà', 'created_at': now},
            ]).execute()

        # Create events
        events = []
        for c in all_cases:
            events.append({'id': str(uuid.uuid4()), 'case_id': c['id'], 'actor_id': agent1, 'event_type': 'case_created', 'new_value': {'title': c['title']}, 'created_at': now})
            if c.get('assigned_agent_id'):
                events.append({'id': str(uuid.uuid4()), 'case_id': c['id'], 'actor_id': agent1, 'event_type': 'assignment', 'new_value': {'agent_id': c['assigned_agent_id']}, 'created_at': now})
        supabase.table('case_events').insert(events).execute()

        return {
            "message": "Dades demo creades (model multi-cas)",
            "seeded": True,
            "contacts": len(contacts),
            "conversations": len(convs),
            "cases": len(all_cases),
            "messages": len(msgs),
        }

    except Exception as e:
        logger.error(f"Seed error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
