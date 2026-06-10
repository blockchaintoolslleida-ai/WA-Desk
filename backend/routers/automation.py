"""
Automation Router — CRUD for rules, business hours, and assignment config.
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import logging
import uuid

from database import get_supabase_admin
from services.audit_logger import log_audit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/automation", tags=["Automation"])


# ─── Auth helper (reuse admin platform pattern) ──────────────

async def get_admin_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticat")
    token = authorization.replace("Bearer ", "")
    supabase = get_supabase_admin()
    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Token invalid")
        profile = supabase.table('profiles').select(
            'id, full_name, role, tenant_id'
        ).eq('id', user_response.user.id).single().execute()
        if not profile.data:
            raise HTTPException(status_code=401, detail="Perfil no trobat")
        if profile.data['role'] not in ('super_admin', 'admin'):
            raise HTTPException(status_code=403, detail="Accés denegat")
        return profile.data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Error d'autenticacio")


def _tenant_id(user: dict) -> str:
    tid = user.get('tenant_id')
    if not tid:
        raise HTTPException(status_code=400, detail="No tenant assignat")
    return tid


# ─── Pydantic models ─────────────────────────────────────────

class RuleCreate(BaseModel):
    category: str  # greeting | schedule | keywords | fallback
    name: str
    is_active: bool = True
    priority: int = 1
    trigger_config: dict = {}
    response_text: Optional[str] = None
    delay_seconds: int = 0
    daily_limit: Optional[int] = None


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    trigger_config: Optional[dict] = None
    response_text: Optional[str] = None
    delay_seconds: Optional[int] = None
    daily_limit: Optional[int] = None


class ReorderRequest(BaseModel):
    items: list  # [{id: str, priority: int}, ...]


class BusinessHoursUpdate(BaseModel):
    timezone: str = 'Europe/Madrid'
    schedule: dict = {}


class AssignmentConfigUpdate(BaseModel):
    is_enabled: bool = False
    timeout_minutes: int = 5
    strategy: str = 'round_robin'
    agent_pool: list = []


# ═══════════════════════════════════════════════════════════════
# RULES CRUD
# ═══════════════════════════════════════════════════════════════

@router.get("/rules")
async def list_rules(authorization: Optional[str] = Header(None)):
    user = await get_admin_user(authorization)
    tid = _tenant_id(user)
    supabase = get_supabase_admin()
    rules = supabase.table('automation_rules').select('*').eq(
        'tenant_id', tid
    ).order('priority').execute()
    return {"rules": rules.data or []}


@router.post("/rules")
async def create_rule(
    req: RuleCreate,
    authorization: Optional[str] = Header(None),
):
    user = await get_admin_user(authorization)
    tid = _tenant_id(user)
    supabase = get_supabase_admin()

    # Validate category
    if req.category not in ('greeting', 'schedule', 'keywords', 'fallback'):
        raise HTTPException(status_code=400, detail=f"Categoria invalida: {req.category}")

    # Fallback: only 1 rule allowed
    if req.category == 'fallback':
        existing = supabase.table('automation_rules').select('id').eq(
            'tenant_id', tid
        ).eq('category', 'fallback').limit(1).execute()
        if existing.data:
            raise HTTPException(
                status_code=400,
                detail="Nomes es permet 1 regla a la categoria fallback"
            )

    now = datetime.now(timezone.utc).isoformat()
    rule = {
        'id': str(uuid.uuid4()),
        'tenant_id': tid,
        'category': req.category,
        'name': req.name,
        'is_active': req.is_active,
        'priority': req.priority,
        'trigger_config': req.trigger_config,
        'response_text': req.response_text,
        'delay_seconds': req.delay_seconds,
        'daily_limit': req.daily_limit,
        'created_at': now,
        'updated_at': now,
    }
    supabase.table('automation_rules').insert(rule).execute()

    await log_audit(
        tid, user['id'], 'create', 'automation_rule', rule['id'],
        f"Rule: {req.name} ({req.category})"
    )
    return {"rule": rule}


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    req: RuleUpdate,
    authorization: Optional[str] = Header(None),
):
    user = await get_admin_user(authorization)
    tid = _tenant_id(user)
    supabase = get_supabase_admin()

    existing = supabase.table('automation_rules').select('id').eq(
        'id', rule_id
    ).eq('tenant_id', tid).single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Regla no trobada")

    updates = {k: v for k, v in req.dict().items() if v is not None}
    if updates:
        updates['updated_at'] = datetime.now(timezone.utc).isoformat()
        supabase.table('automation_rules').update(updates).eq('id', rule_id).execute()

        await log_audit(
            tid, user['id'], 'update', 'automation_rule', rule_id,
            f"Updated: {', '.join(updates.keys())}"
        )

    updated = supabase.table('automation_rules').select('*').eq(
        'id', rule_id
    ).single().execute()
    return {"rule": updated.data}


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    authorization: Optional[str] = Header(None),
):
    user = await get_admin_user(authorization)
    tid = _tenant_id(user)
    supabase = get_supabase_admin()

    existing = supabase.table('automation_rules').select('id,name').eq(
        'id', rule_id
    ).eq('tenant_id', tid).single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Regla no trobada")

    supabase.table('automation_rules').delete().eq('id', rule_id).execute()

    await log_audit(
        tid, user['id'], 'delete', 'automation_rule', rule_id,
        f"Deleted: {existing.data.get('name')}"
    )
    return {"ok": True}


@router.patch("/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: str,
    authorization: Optional[str] = Header(None),
):
    user = await get_admin_user(authorization)
    tid = _tenant_id(user)
    supabase = get_supabase_admin()

    existing = supabase.table('automation_rules').select(
        'id, is_active'
    ).eq('id', rule_id).eq('tenant_id', tid).single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Regla no trobada")

    new_state = not existing.data.get('is_active', True)
    supabase.table('automation_rules').update({
        'is_active': new_state,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }).eq('id', rule_id).execute()

    return {"ok": True, "is_active": new_state}


@router.put("/rules/reorder")
async def reorder_rules(
    req: ReorderRequest,
    authorization: Optional[str] = Header(None),
):
    user = await get_admin_user(authorization)
    tid = _tenant_id(user)
    supabase = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    for item in req.items:
        supabase.table('automation_rules').update({
            'priority': item['priority'],
            'updated_at': now,
        }).eq('id', item['id']).eq('tenant_id', tid).execute()

    return {"ok": True}


# ═══════════════════════════════════════════════════════════════
# BUSINESS HOURS
# ═══════════════════════════════════════════════════════════════

@router.get("/business-hours")
async def get_business_hours(authorization: Optional[str] = Header(None)):
    user = await get_admin_user(authorization)
    tid = _tenant_id(user)
    supabase = get_supabase_admin()

    existing = supabase.table('business_hours').select('*').eq(
        'tenant_id', tid
    ).limit(1).execute()

    if not existing.data:
        # Create default (Mon-Fri 9-13, 16-19; Fri 9-15; Sat-Sun closed)
        now = datetime.now(timezone.utc).isoformat()
        default = {
            'id': str(uuid.uuid4()),
            'tenant_id': tid,
            'timezone': 'Europe/Madrid',
            'schedule': {
                'mon': [['09:00', '13:00'], ['16:00', '19:00']],
                'tue': [['09:00', '13:00'], ['16:00', '19:00']],
                'wed': [['09:00', '13:00'], ['16:00', '19:00']],
                'thu': [['09:00', '13:00'], ['16:00', '19:00']],
                'fri': [['09:00', '15:00']],
                'sat': [],
                'sun': [],
            },
            'created_at': now,
            'updated_at': now,
        }
        supabase.table('business_hours').insert(default).execute()
        return {"business_hours": default}

    return {"business_hours": existing.data[0]}


@router.put("/business-hours")
async def update_business_hours(
    req: BusinessHoursUpdate,
    authorization: Optional[str] = Header(None),
):
    user = await get_admin_user(authorization)
    tid = _tenant_id(user)
    supabase = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    existing = supabase.table('business_hours').select('id').eq(
        'tenant_id', tid
    ).limit(1).execute()

    updates = {
        'timezone': req.timezone,
        'schedule': req.schedule,
        'updated_at': now,
    }

    if existing.data:
        supabase.table('business_hours').update(updates).eq(
            'id', existing.data[0]['id']
        ).execute()
    else:
        updates['id'] = str(uuid.uuid4())
        updates['tenant_id'] = tid
        updates['created_at'] = now
        supabase.table('business_hours').insert(updates).execute()

    await log_audit(
        tid, user['id'], 'update', 'business_hours', tid,
        "Business hours updated"
    )
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════
# ASSIGNMENT CONFIG
# ═══════════════════════════════════════════════════════════════

@router.get("/assignment")
async def get_assignment_config(authorization: Optional[str] = Header(None)):
    user = await get_admin_user(authorization)
    tid = _tenant_id(user)
    supabase = get_supabase_admin()

    existing = supabase.table('assignment_config').select('*').eq(
        'tenant_id', tid
    ).limit(1).execute()

    if not existing.data:
        now = datetime.now(timezone.utc).isoformat()
        default = {
            'id': str(uuid.uuid4()),
            'tenant_id': tid,
            'is_enabled': False,
            'timeout_minutes': 5,
            'strategy': 'round_robin',
            'agent_pool': [],
            'last_assigned_index': 0,
            'created_at': now,
            'updated_at': now,
        }
        supabase.table('assignment_config').insert(default).execute()
        return {"assignment": default}

    return {"assignment": existing.data[0]}


@router.put("/assignment")
async def update_assignment_config(
    req: AssignmentConfigUpdate,
    authorization: Optional[str] = Header(None),
):
    user = await get_admin_user(authorization)
    tid = _tenant_id(user)
    supabase = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    existing = supabase.table('assignment_config').select('id').eq(
        'tenant_id', tid
    ).limit(1).execute()

    updates = {
        'is_enabled': req.is_enabled,
        'timeout_minutes': req.timeout_minutes,
        'strategy': req.strategy,
        'agent_pool': req.agent_pool,
        'updated_at': now,
    }

    if existing.data:
        supabase.table('assignment_config').update(updates).eq(
            'id', existing.data[0]['id']
        ).execute()
    else:
        updates['id'] = str(uuid.uuid4())
        updates['tenant_id'] = tid
        updates['last_assigned_index'] = 0
        updates['created_at'] = now
        supabase.table('assignment_config').insert(updates).execute()

    await log_audit(
        tid, user['id'], 'update', 'assignment_config', tid,
        f"Assignment: enabled={req.is_enabled}, strategy={req.strategy}"
    )
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════
# LOGS (read-only)
# ═══════════════════════════════════════════════════════════════

@router.get("/logs")
async def get_automation_logs(
    limit: int = 50,
    authorization: Optional[str] = Header(None),
):
    user = await get_admin_user(authorization)
    tid = _tenant_id(user)
    supabase = get_supabase_admin()

    logs = supabase.table('automation_logs').select(
        'id, rule_id, conversation_id, category, triggered_at, response_preview'
    ).eq('tenant_id', tid).order('triggered_at', desc=True).limit(limit).execute()

    return {"logs": logs.data or []}
