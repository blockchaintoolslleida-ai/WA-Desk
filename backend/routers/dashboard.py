"""
Dashboard Router - Case-centric KPI Metrics
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
import logging
from datetime import datetime, timezone
from database import get_supabase_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


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


@router.get("/metrics")
async def get_metrics(authorization: Optional[str] = Header(None)):
    await get_user_from_token(authorization)
    supabase = get_supabase_admin()

    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        # Get all cases
        all_cases = supabase.table('cases').select('id, status, assigned_agent_id, is_active, conversation_id, created_at, updated_at').execute()
        cases = all_cases.data or []

        # Count by status
        status_counts = {}
        new_today = 0
        closed_today = 0
        for c in cases:
            s = c.get('status', 'nou')
            status_counts[s] = status_counts.get(s, 0) + 1
            if c.get('created_at', '') >= today_start:
                new_today += 1
            if s in ['tancat', 'resolt'] and c.get('updated_at', '') >= today_start:
                closed_today += 1

        # Unassigned cases
        unassigned = sum(1 for c in cases if not c.get('assigned_agent_id') and c.get('is_active'))

        # Cases by agent
        agent_counts = {}
        resolved_by_agent = {}
        for c in cases:
            agent_id = c.get('assigned_agent_id')
            if agent_id:
                agent_counts[agent_id] = agent_counts.get(agent_id, 0) + 1
                if c.get('status') in ['resolt', 'tancat']:
                    resolved_by_agent[agent_id] = resolved_by_agent.get(agent_id, 0) + 1

        agent_ids = list(set(list(agent_counts.keys()) + list(resolved_by_agent.keys())))
        agents_map = {}
        if agent_ids:
            agents_res = supabase.table('profiles').select('id, full_name').in_('id', agent_ids).execute()
            agents_map = {a['id']: a['full_name'] for a in (agents_res.data or [])}

        # Unclassified messages
        unclass_res = supabase.table('messages').select('id', count='exact').eq('needs_classification', True).execute()
        unclassified_msgs = unclass_res.count if unclass_res.count is not None else 0

        # Multi-case conversations
        conv_ids = list(set(c['conversation_id'] for c in cases if c.get('is_active')))
        conv_case_counts = {}
        for c in cases:
            if c.get('is_active'):
                cid = c['conversation_id']
                conv_case_counts[cid] = conv_case_counts.get(cid, 0) + 1
        multi_case_convs = sum(1 for v in conv_case_counts.values() if v > 1)

        return {
            "new_today": new_today,
            "per_atendre": status_counts.get('per_atendre', 0) + status_counts.get('nou', 0),
            "en_atencio": status_counts.get('en_atencio', 0),
            "esperant_client": status_counts.get('esperant_client', 0),
            "closed_today": closed_today,
            "unassigned": unassigned,
            "total_active": sum(1 for c in cases if c.get('is_active')),
            "total_cases": len(cases),
            "unclassified_msgs": unclassified_msgs,
            "multi_case_convs": multi_case_convs,
            "avg_first_response_minutes": None,
            "cases_by_agent": sorted([
                {"agent_id": aid, "agent_name": agents_map.get(aid, "?"), "count": cnt}
                for aid, cnt in agent_counts.items()
            ], key=lambda x: x['count'], reverse=True),
            "resolved_by_agent": sorted([
                {"agent_id": aid, "agent_name": agents_map.get(aid, "?"), "count": cnt}
                for aid, cnt in resolved_by_agent.items()
            ], key=lambda x: x['count'], reverse=True),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        raise HTTPException(status_code=500, detail="Error carregant metriques")
