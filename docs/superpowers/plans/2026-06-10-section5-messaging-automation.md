# Section 5 — Messaging Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a messaging automation engine with configurable auto-response rules, business hours, and agent auto-assignment — all managed from a new "Automatitzacions" admin section.

**Architecture:** Category-based pipeline (Greeting → Schedule → Keywords → Assignment → Fallback) that evaluates rules sequentially on incoming messages. First matching category executes and stops the pipeline. Backend: FastAPI router + services engine. Frontend: React admin section with 3 tabs.

**Tech Stack:** FastAPI + Python (backend), React + TailwindCSS (frontend), Supabase PostgreSQL (DB), existing WhatsApp service layer

---

## File Structure

| Action | File | Responsibility |
|---|---|---|
| Create | `backend/supabase_automation_migration.sql` | Create 4 new DB tables |
| Create | `backend/services/automation_engine.py` | Rule evaluation pipeline |
| Create | `backend/routers/automation.py` | REST API for CRUD + config |
| Modify | `backend/routers/webhook.py` | Hook engine after inbound insert |
| Modify | `backend/server.py` | Register automation router |
| Modify | `frontend/src/lib/api.js` | Add `automationApi` client |
| Modify | `frontend/src/lib/i18n.js` | Add CA/ES/EN translations |
| Create | `frontend/src/pages/admin/AutomationSection.js` | Main admin section component |
| Modify | `frontend/src/pages/AdminPage.js` | Add nav item + section render |

---

### Task 1: Database Migration

**Files:**
- Create: `backend/supabase_automation_migration.sql`

- [ ] **Step 1: Write the SQL migration file**

```sql
-- ============================================================
-- Section 5: Messaging Automation — Database Tables
-- ============================================================

-- 1. Automation Rules
CREATE TABLE IF NOT EXISTS automation_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  category TEXT NOT NULL CHECK (category IN ('greeting', 'schedule', 'keywords', 'fallback')),
  name TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  priority INTEGER NOT NULL DEFAULT 1,
  trigger_config JSONB NOT NULL DEFAULT '{}',
  response_text TEXT,
  delay_seconds INTEGER DEFAULT 0,
  daily_limit INTEGER,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_automation_rules_tenant
  ON automation_rules(tenant_id, category, priority);

-- 2. Business Hours
CREATE TABLE IF NOT EXISTS business_hours (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  timezone TEXT NOT NULL DEFAULT 'Europe/Madrid',
  schedule JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(tenant_id)
);

-- 3. Assignment Config
CREATE TABLE IF NOT EXISTS assignment_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  is_enabled BOOLEAN DEFAULT false,
  timeout_minutes INTEGER DEFAULT 5,
  strategy TEXT NOT NULL DEFAULT 'round_robin',
  agent_pool UUID[] DEFAULT '{}',
  last_assigned_index INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(tenant_id)
);

-- 4. Automation Logs
CREATE TABLE IF NOT EXISTS automation_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  rule_id UUID REFERENCES automation_rules(id) ON DELETE SET NULL,
  conversation_id UUID,
  message_id UUID,
  category TEXT,
  triggered_at TIMESTAMPTZ DEFAULT now(),
  response_preview TEXT
);

CREATE INDEX IF NOT EXISTS idx_automation_logs_tenant_date
  ON automation_logs(tenant_id, triggered_at);
CREATE INDEX IF NOT EXISTS idx_automation_logs_rule
  ON automation_logs(rule_id, triggered_at);
```

- [ ] **Step 2: Run migration on Supabase**

Run in Supabase SQL Editor or via local Supabase CLI against the project database. Verify all 4 tables exist:

```sql
SELECT table_name FROM information_schema.tables
WHERE table_name IN ('automation_rules', 'business_hours', 'assignment_config', 'automation_logs');
```

Expected: 4 rows returned.

- [ ] **Step 3: Commit**

```bash
git add backend/supabase_automation_migration.sql
git commit -m "feat: add automation tables — rules, business_hours, assignment_config, logs"
```

---

### Task 2: Automation Engine Service

**Files:**
- Create: `backend/services/automation_engine.py`

- [ ] **Step 1: Create the automation engine**

```python
"""
Automation Engine — evaluates auto-response rules on incoming WhatsApp messages.
Category pipeline: greeting → schedule → keywords → assignment → fallback
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import asyncio
import pytz

from database import get_supabase_admin

logger = logging.getLogger(__name__)

# Category evaluation order (fixed)
CATEGORY_ORDER = ['greeting', 'schedule', 'keywords', 'fallback']


async def evaluate_and_execute(
    tenant_id: str,
    conversation_id: str,
    message_data: dict,
    contact_id: str = None,
) -> Optional[Dict[str, Any]]:
    """
    Evaluate automation rules for an incoming message.
    Returns dict with execution result, or None if no rule fired.
    
    message_data expects keys: body, phone
    """
    if not tenant_id:
        return None
    
    try:
        supabase = get_supabase_admin()
        
        # Load rules for this tenant, active, ordered by category + priority
        rules_res = supabase.table('automation_rules').select('*').eq(
            'tenant_id', tenant_id
        ).eq('is_active', True).order('priority').execute()
        
        if not rules_res.data:
            return None
        
        # Group rules by category, preserving order within each category
        rules_by_category = {}
        for r in rules_res.data:
            cat = r['category']
            if cat not in rules_by_category:
                rules_by_category[cat] = []
            rules_by_category[cat].append(r)
        
        message_body = (message_data.get('body') or '').lower().strip()
        
        # Evaluate categories in fixed order
        for cat in CATEGORY_ORDER:
            category_rules = rules_by_category.get(cat, [])
            if not category_rules:
                continue
            
            result = await _evaluate_category(
                cat, category_rules, tenant_id, conversation_id,
                message_body, message_data, contact_id, supabase
            )
            if result:
                return result
        
        # Category 4: Assignment (handled separately, not in rules table)
        result = await _evaluate_assignment(tenant_id, conversation_id, supabase)
        if result:
            return result
        
        return None
        
    except Exception as e:
        logger.error(f"Automation engine error: {e}")
        return None


async def _evaluate_category(
    category: str,
    rules: list,
    tenant_id: str,
    conversation_id: str,
    message_body: str,
    message_data: dict,
    contact_id: str,
    supabase,
) -> Optional[Dict[str, Any]]:
    """Evaluate all rules in a category, return first match."""
    
    for rule in rules:
        if not rule.get('is_active'):
            continue
        
        # Check daily limit
        daily_limit = rule.get('daily_limit')
        if daily_limit:
            today_count = await _count_rule_logs_today(supabase, rule['id'], tenant_id)
            if today_count >= daily_limit:
                continue
        
        # Evaluate trigger
        triggered = False
        trigger_config = rule.get('trigger_config') or {}
        
        if category == 'greeting':
            triggered = await _is_first_contact(supabase, contact_id)
        elif category == 'schedule':
            triggered = await _evaluate_schedule_trigger(
                trigger_config, tenant_id, supabase
            )
        elif category == 'keywords':
            triggered = _evaluate_keywords_trigger(trigger_config, message_body)
        elif category == 'fallback':
            triggered = True  # catch-all
        
        if not triggered:
            continue
        
        # Execute action
        response_text = rule.get('response_text') or ''
        delay = rule.get('delay_seconds') or 0
        
        return await _execute_rule(
            rule, tenant_id, conversation_id, message_data,
            response_text, delay, supabase
        )
    
    return None


# ── Trigger Evaluators ────────────────────────────────────────

async def _is_first_contact(supabase, contact_id: str) -> bool:
    """Check if this contact has no previous conversations."""
    if not contact_id:
        return False
    try:
        convs = supabase.table('conversations').select('id').eq(
            'contact_id', contact_id
        ).limit(1).execute()
        return not bool(convs.data)
    except Exception:
        return False


async def _evaluate_schedule_trigger(
    trigger_config: dict, tenant_id: str, supabase
) -> bool:
    """
    Check if we're inside/outside business hours.
    trigger_config.type: 'outside_hours' or 'inside_hours'
    """
    rule_type = trigger_config.get('type', 'outside_hours')
    is_inside = await is_inside_business_hours(tenant_id, supabase)
    
    if rule_type == 'outside_hours':
        return not is_inside
    elif rule_type == 'inside_hours':
        return is_inside
    return False


def _evaluate_keywords_trigger(trigger_config: dict, message_body: str) -> bool:
    """Check if message contains any of the configured keywords."""
    keywords = trigger_config.get('keywords', [])
    if not keywords or not message_body:
        return False
    return any(kw.lower() in message_body for kw in keywords)
    # Note: for .lower() to work, keywords should already be lowercase;
    # case-insensitive matching is handled in message_body.lower()


# ── Schedule Helper ────────────────────────────────────────────

async def is_inside_business_hours(tenant_id: str, supabase) -> bool:
    """
    Returns True if the current time falls within any time slot
    for the current day of the week in the tenant's timezone.
    """
    try:
        bh_res = supabase.table('business_hours').select(
            'timezone, schedule'
        ).eq('tenant_id', tenant_id).limit(1).execute()
        
        if not bh_res.data:
            return False  # No hours configured = always outside
        
        bh = bh_res.data[0]
        tz_str = bh.get('timezone', 'Europe/Madrid')
        schedule = bh.get('schedule') or {}
        
        tz = pytz.timezone(tz_str)
        now_local = datetime.now(tz)
        day_key = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'][now_local.weekday()]
        
        slots = schedule.get(day_key, [])
        if not slots:
            return False
        
        now_time = now_local.strftime('%H:%M')
        
        for slot in slots:
            if len(slot) >= 2 and slot[0] <= now_time < slot[1]:
                return True
        
        return False
    except Exception as e:
        logger.warning(f"Error checking business hours: {e}")
        return False


# ── Daily Limit ────────────────────────────────────────────────

async def _count_rule_logs_today(supabase, rule_id: str, tenant_id: str) -> int:
    """Count how many times this rule fired today (in the tenant's timezone)."""
    try:
        # Get tenant timezone
        bh_res = supabase.table('business_hours').select('timezone').eq(
            'tenant_id', tenant_id
        ).limit(1).execute()
        tz_str = (bh_res.data[0].get('timezone') if bh_res.data else 'Europe/Madrid')
        tz = pytz.timezone(tz_str)
        now_local = datetime.now(tz)
        day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start_utc = day_start.astimezone(pytz.UTC).isoformat()
        
        logs = supabase.table('automation_logs').select('id', count='exact').eq(
            'rule_id', rule_id
        ).gte('triggered_at', day_start_utc).execute()
        
        return logs.count if logs.count else 0
    except Exception:
        return 0


# ── Rule Execution ─────────────────────────────────────────────

async def _execute_rule(
    rule: dict,
    tenant_id: str,
    conversation_id: str,
    message_data: dict,
    response_text: str,
    delay_seconds: int,
    supabase,
) -> Dict[str, Any]:
    """Execute a matched rule: substitute markers, apply delay, send message, log."""
    
    # Substitute markers
    response_text = await _substitute_markers(
        response_text, tenant_id, conversation_id, message_data, supabase
    )
    
    # Log the trigger
    log_entry = {
        'tenant_id': tenant_id,
        'rule_id': rule['id'],
        'conversation_id': conversation_id,
        'category': rule['category'],
        'triggered_at': datetime.now(timezone.utc).isoformat(),
        'response_preview': response_text[:100] if response_text else '',
    }
    supabase.table('automation_logs').insert(log_entry).execute()
    
    # Apply delay if configured
    if delay_seconds > 0:
        logger.info(
            f"Automation: rule '{rule['name']}' matched, delaying {delay_seconds}s"
        )
        asyncio.create_task(_delayed_send(
            response_text, message_data, tenant_id, delay_seconds
        ))
    else:
        await _send_automation_reply(response_text, message_data, tenant_id)
    
    logger.info(f"Automation fired: {rule['category']} → '{rule['name']}'")
    
    return {
        'category': rule['category'],
        'rule_name': rule['name'],
        'rule_id': rule['id'],
        'response_preview': response_text[:100],
    }


async def _delayed_send(
    response_text: str, message_data: dict, tenant_id: str, delay_seconds: int
):
    """Send after a delay (fire-and-forget background task)."""
    await asyncio.sleep(delay_seconds)
    await _send_automation_reply(response_text, message_data, tenant_id)


async def _send_automation_reply(
    response_text: str, message_data: dict, tenant_id: str
):
    """Send the auto-response via the existing WhatsApp service."""
    try:
        from services.whatsapp import send_whatsapp_message
        from models import WhatsAppOutboundMessage
        
        phone = message_data.get('phone', '')
        if not phone:
            logger.error("Automation: no phone to send reply to")
            return
        
        msg = WhatsAppOutboundMessage(phone=phone, body=response_text)
        result = await send_whatsapp_message(msg, tenant_id=tenant_id)
        if not result.get('ok'):
            logger.error(f"Automation send failed: {result.get('error')}")
    except Exception as e:
        logger.error(f"Automation send error: {e}")


async def _substitute_markers(
    text: str, tenant_id: str, conversation_id: str, message_data: dict, supabase
) -> str:
    """Replace {{markers}} in the response text with real values."""
    if not text:
        return text
    
    # {{agent_name}} — get assigned agent name
    if '{{agent_name}}' in text:
        try:
            conv = supabase.table('conversations').select(
                'assigned_agent_id'
            ).eq('id', conversation_id).single().execute()
            agent_id = (conv.data or {}).get('assigned_agent_id')
            if agent_id:
                agent = supabase.table('profiles').select('full_name').eq(
                    'id', agent_id
                ).single().execute()
                agent_name = (agent.data or {}).get('full_name', 'el nostre equip')
            else:
                agent_name = 'el nostre equip'
        except Exception:
            agent_name = 'el nostre equip'
        text = text.replace('{{agent_name}}', agent_name)
    
    # {{business_name}} — get tenant name
    if '{{business_name}}' in text:
        try:
            tenant = supabase.table('tenants').select('name').eq(
                'id', tenant_id
            ).single().execute()
            business_name = (tenant.data or {}).get('name', 'el nostre equip')
        except Exception:
            business_name = 'el nostre equip'
        text = text.replace('{{business_name}}', business_name)
    
    # {{contact_name}} — get contact name
    if '{{contact_name}}' in text:
        try:
            conv = supabase.table('conversations').select('contact_id').eq(
                'id', conversation_id
            ).single().execute()
            contact_id = (conv.data or {}).get('contact_id')
            if contact_id:
                contact = supabase.table('contacts').select('name').eq(
                    'id', contact_id
                ).single().execute()
                contact_name = (contact.data or {}).get('name', '')
            else:
                contact_name = ''
        except Exception:
            contact_name = ''
        if not contact_name:
            phone = message_data.get('phone', '')
            contact_name = phone or ''
        text = text.replace('{{contact_name}}', contact_name)
    
    return text


# ── Assignment Evaluation ──────────────────────────────────────

async def _evaluate_assignment(
    tenant_id: str, conversation_id: str, supabase
) -> Optional[Dict[str, Any]]:
    """Check if auto-assignment should fire for this conversation."""
    try:
        config_res = supabase.table('assignment_config').select('*').eq(
            'tenant_id', tenant_id
        ).limit(1).execute()
        
        if not config_res.data:
            return None
        
        config = config_res.data[0]
        if not config.get('is_enabled'):
            return None
        
        # Check if conversation already has an assigned agent
        conv = supabase.table('conversations').select(
            'assigned_agent_id, created_at'
        ).eq('id', conversation_id).single().execute()
        
        if not conv.data:
            return None
        
        conv_data = conv.data
        if conv_data.get('assigned_agent_id'):
            return None  # Already assigned
        
        # Check timeout
        created_at_str = conv_data.get('created_at', '')
        if created_at_str:
            created_at = datetime.fromisoformat(
                created_at_str.replace('Z', '+00:00')
            ).astimezone(timezone.utc)
            now = datetime.now(timezone.utc)
            timeout_minutes = config.get('timeout_minutes', 5)
            if (now - created_at).total_seconds() < timeout_minutes * 60:
                return None  # Timeout not yet reached
        
        # Select agent from pool
        agent_id = await _select_agent(config, supabase)
        if not agent_id:
            return None
        
        # Assign
        supabase.table('conversations').update({
            'assigned_agent_id': agent_id,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }).eq('id', conversation_id).execute()
        
        # Update round-robin index
        pool = config.get('agent_pool') or []
        if pool and agent_id in pool:
            new_index = (pool.index(agent_id) + 1) % len(pool)
            supabase.table('assignment_config').update({
                'last_assigned_index': new_index,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }).eq('id', config['id']).execute()
        
        logger.info(f"Auto-assigned agent {agent_id} to conversation {conversation_id}")
        return {
            'category': 'assignment',
            'rule_name': 'auto-assignment',
            'assigned_agent_id': agent_id,
        }
        
    except Exception as e:
        logger.error(f"Auto-assignment error: {e}")
        return None


async def _select_agent(config: dict, supabase) -> Optional[str]:
    """Select an agent based on the configured strategy."""
    pool = config.get('agent_pool') or []
    if not pool:
        return None
    
    strategy = config.get('strategy', 'round_robin')
    
    if strategy == 'least_conversations':
        # Find agent with fewest active conversations
        best_agent = None
        min_count = None
        for agent_id in pool:
            try:
                convs = supabase.table('conversations').select('id', count='exact').eq(
                    'assigned_agent_id', agent_id
                ).eq('is_active', True).execute()
                count = convs.count if convs.count else 0
            except Exception:
                count = 0
            if best_agent is None or count < min_count:
                best_agent = agent_id
                min_count = count
        return best_agent
    else:
        # Round-robin
        idx = config.get('last_assigned_index', 0) % len(pool)
        return pool[idx]


# ── Cleanup helper for tests ───────────────────────────────────

def reset_engine():
    """No-op reset for test isolation. Tests should mock Supabase responses."""
    pass
```

- [ ] **Step 2: Verify imports work**

```bash
cd backend && python -c "from services.automation_engine import evaluate_and_execute, is_inside_business_hours; print('OK')"
```

Expected: `OK` (may warn about missing pytz — install if needed)

- [ ] **Step 3: Install pytz if not present**

```bash
cd backend && pip install pytz
```

- [ ] **Step 4: Commit**

```bash
git add backend/services/automation_engine.py
git commit -m "feat: automation engine — category pipeline, triggers, markers, assignment"
```

---

### Task 3: Automation API Router

**Files:**
- Create: `backend/routers/automation.py`

- [ ] **Step 1: Create the automation router**

```python
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
        # Create default (empty schedule, Mon-Fri 9-18)
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
```

- [ ] **Step 2: Verify router loads**

```bash
cd backend && python -c "from routers.automation import router; print('Router OK, routes:', len(router.routes))"
```

Expected: Router OK, routes: ~10

- [ ] **Step 3: Commit**

```bash
git add backend/routers/automation.py
git commit -m "feat: automation API router — rules CRUD, business hours, assignment config"
```

---

### Task 4: Integrate Engine into Webhook

**Files:**
- Modify: `backend/routers/webhook.py`

- [ ] **Step 1: Add engine import**

At the top of `backend/routers/webhook.py`, add the import after the existing imports:

```python
# Add after line 17 (from services.secrets_manager import decrypt_value):
from services.automation_engine import evaluate_and_execute
```

- [ ] **Step 2: Add engine call after message insert**

In `process_inbound_message()` function, after the message insert block (after line 239: `supabase.table('messages').insert(msg_data).execute()`), add:

```python
        # ── Automation Engine: evaluate auto-response rules ─────
        # Only fire for incoming messages (not outbound_from_mobile)
        if direction == 'incoming':
            try:
                automation_result = await evaluate_and_execute(
                    resolved_tenant_id,
                    conversation_id,
                    {'body': message.body, 'phone': phone},
                    contact_id=contact_id,
                )
                if automation_result:
                    logger.info(
                        f"Automation fired: {automation_result.get('category')}"
                        f" → {automation_result.get('rule_name')}"
                    )
            except Exception as auto_err:
                logger.error(f"Automation engine error (non-fatal): {auto_err}")
```

Add this right before the logger line `logger.info(f"Inbound processed...")`.

- [ ] **Step 3: Verify integration**

```bash
cd backend && python -c "
from routers.webhook import process_inbound_message
print('webhook module loads OK with automation import')
"
```

Expected: `webhook module loads OK with automation import`

- [ ] **Step 4: Commit**

```bash
git add backend/routers/webhook.py
git commit -m "feat: integrate automation engine into webhook pipeline"
```

---

### Task 5: Register Router in Server

**Files:**
- Modify: `backend/server.py`

- [ ] **Step 1: Add automation router import and registration**

Add the import on line 16 (after the existing imports):

```python
from routers import auth, conversations, messages, webhook, dashboard, agents, setup, cases, media, contacts, window, admin_platform, templates, contacts_import, media_proxy, calendar, automation
```

Add the router registration after line 367 (register automation router after calendar.router):

```python
api_router.include_router(automation.router)
```

- [ ] **Step 2: Verify server starts**

```bash
cd backend && timeout 5 python server.py 2>&1 | head -5 || echo "Server started OK (timeout expected)"
```

Expected: Server starts without import errors.

- [ ] **Step 3: Commit**

```bash
git add backend/server.py
git commit -m "feat: register automation router in server"
```

---

### Task 6: Frontend API Client

**Files:**
- Modify: `frontend/src/lib/api.js`

- [ ] **Step 1: Add automationApi after the adminApi block (after line 131)**

```js
export const automationApi = {
  // Rules
  getRules: () => api.get('/admin/automation/rules'),
  createRule: (data) => api.post('/admin/automation/rules', data),
  updateRule: (id, data) => api.put(`/admin/automation/rules/${id}`, data),
  deleteRule: (id) => api.delete(`/admin/automation/rules/${id}`),
  toggleRule: (id) => api.patch(`/admin/automation/rules/${id}/toggle`),
  reorderRules: (data) => api.put('/admin/automation/rules/reorder', data),
  // Business Hours
  getBusinessHours: () => api.get('/admin/automation/business-hours'),
  updateBusinessHours: (data) => api.put('/admin/automation/business-hours', data),
  // Assignment
  getAssignment: () => api.get('/admin/automation/assignment'),
  updateAssignment: (data) => api.put('/admin/automation/assignment', data),
  // Logs
  getLogs: (limit = 50) => api.get(`/admin/automation/logs?limit=${limit}`),
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.js
git commit -m "feat: add automationApi client — rules, hours, assignment, logs"
```

---

### Task 7: i18n Translations

**Files:**
- Modify: `frontend/src/lib/i18n.js`

- [ ] **Step 1: Add Catalan translations**

Add in the `ca:` block, after existing `admin.*` entries. First, add the nav key near the other nav entries (find `'admin.nav.contacts_import'`):

```js
'admin.nav.automation': 'Automatitzacions',
```

Then add the full automation translations block (add at the end of the `ca:` block, before the closing `}`):

```js
// ── Admin: Automatitzacions (Section 5) ──
'admin.automation.tab_rules': 'Regles d\'auto-resposta',
'admin.automation.tab_hours': 'Horari laboral',
'admin.automation.tab_assignment': 'Assignació automàtica',
'admin.automation.cat_greeting': 'Salutació',
'admin.automation.cat_greeting_desc': 'Primer contacte',
'admin.automation.cat_schedule': 'Horaris',
'admin.automation.cat_schedule_desc': 'Fora d\'horari / En horari',
'admin.automation.cat_keywords': 'Paraules clau',
'admin.automation.cat_keywords_desc': 'Respostes per keyword',
'admin.automation.cat_assignment': 'Assignació',
'admin.automation.cat_assignment_desc': 'Auto-assignació d\'agents',
'admin.automation.cat_fallback': 'Fallback',
'admin.automation.cat_fallback_desc': 'Resposta per defecte',
'admin.automation.rule_name': 'Nom de la regla',
'admin.automation.rule_active': 'Activa',
'admin.automation.rule_priority': 'Prioritat',
'admin.automation.rule_trigger': 'Disparador',
'admin.automation.rule_response': 'Missatge de resposta',
'admin.automation.rule_delay': 'Delay (segons)',
'admin.automation.rule_daily_limit': 'Límit diari',
'admin.automation.rule_unlimited': 'Il·limitat',
'admin.automation.add_rule': 'Afegir regla',
'admin.automation.edit_rule': 'Editar regla',
'admin.automation.save_rule': 'Guardar regla',
'admin.automation.cancel': 'Cancel·lar',
'admin.automation.add_keyword': 'Afegir',
'admin.automation.keyword_placeholder': 'Nova paraula clau...',
'admin.automation.markers_hint': 'Marcadors disponibles:',
'admin.automation.timezone': 'Zona horària',
'admin.automation.day_mon': 'Dilluns',
'admin.automation.day_tue': 'Dimarts',
'admin.automation.day_wed': 'Dimecres',
'admin.automation.day_thu': 'Dijous',
'admin.automation.day_fri': 'Divendres',
'admin.automation.day_sat': 'Dissabte',
'admin.automation.day_sun': 'Diumenge',
'admin.automation.closed': 'Tancat',
'admin.automation.add_slot': 'Afegir franja',
'admin.automation.save_hours': 'Guardar horari',
'admin.automation.assignment_enabled': 'Assignació automàtica',
'admin.automation.assignment_desc': 'Quan s\'activa, els nous missatges s\'assignen automàticament',
'admin.automation.assignment_timeout': 'Timeout d\'assignació (minuts)',
'admin.automation.assignment_timeout_hint': 'Si cap agent assigna la conversa en aquest temps, s\'assigna automàticament',
'admin.automation.assignment_strategy': 'Estratègia',
'admin.automation.strategy_round_robin': 'Round-robin (per torns)',
'admin.automation.strategy_least': 'Menys converses obertes',
'admin.automation.assignment_agents': 'Agents participants',
'admin.automation.assignment_disabled_warn': 'L\'assignació automàtica està desactivada. Totes les converses requereixen assignació manual.',
'admin.automation.save_assignment': 'Guardar configuració',
'admin.automation.trigger_outside_hours': 'Fora d\'horari',
'admin.automation.trigger_inside_hours': 'En horari laboral',
'admin.automation.no_rules': 'Encara no hi ha regles en aquesta categoria',
'admin.automation.fallback_only_one': 'Només es permet 1 regla fallback',
```

- [ ] **Step 2: Add Spanish translations**

Same keys in `es:` block:

```js
'admin.nav.automation': 'Automatizaciones',
'admin.automation.tab_rules': 'Reglas de auto-respuesta',
'admin.automation.tab_hours': 'Horario laboral',
'admin.automation.tab_assignment': 'Asignación automática',
'admin.automation.cat_greeting': 'Saludo',
'admin.automation.cat_greeting_desc': 'Primer contacto',
'admin.automation.cat_schedule': 'Horarios',
'admin.automation.cat_schedule_desc': 'Fuera de horario / En horario',
'admin.automation.cat_keywords': 'Palabras clave',
'admin.automation.cat_keywords_desc': 'Respuestas por keyword',
'admin.automation.cat_assignment': 'Asignación',
'admin.automation.cat_assignment_desc': 'Auto-asignación de agentes',
'admin.automation.cat_fallback': 'Fallback',
'admin.automation.cat_fallback_desc': 'Respuesta por defecto',
'admin.automation.rule_name': 'Nombre de la regla',
'admin.automation.rule_active': 'Activa',
'admin.automation.rule_priority': 'Prioridad',
'admin.automation.rule_trigger': 'Disparador',
'admin.automation.rule_response': 'Mensaje de respuesta',
'admin.automation.rule_delay': 'Delay (segundos)',
'admin.automation.rule_daily_limit': 'Límite diario',
'admin.automation.rule_unlimited': 'Ilimitado',
'admin.automation.add_rule': 'Añadir regla',
'admin.automation.edit_rule': 'Editar regla',
'admin.automation.save_rule': 'Guardar regla',
'admin.automation.cancel': 'Cancelar',
'admin.automation.add_keyword': 'Añadir',
'admin.automation.keyword_placeholder': 'Nueva palabra clave...',
'admin.automation.markers_hint': 'Marcadores disponibles:',
'admin.automation.timezone': 'Zona horaria',
'admin.automation.day_mon': 'Lunes',
'admin.automation.day_tue': 'Martes',
'admin.automation.day_wed': 'Miércoles',
'admin.automation.day_thu': 'Jueves',
'admin.automation.day_fri': 'Viernes',
'admin.automation.day_sat': 'Sábado',
'admin.automation.day_sun': 'Domingo',
'admin.automation.closed': 'Cerrado',
'admin.automation.add_slot': 'Añadir franja',
'admin.automation.save_hours': 'Guardar horario',
'admin.automation.assignment_enabled': 'Asignación automática',
'admin.automation.assignment_desc': 'Cuando se activa, los nuevos mensajes se asignan automáticamente',
'admin.automation.assignment_timeout': 'Timeout de asignación (minutos)',
'admin.automation.assignment_timeout_hint': 'Si ningún agente asigna la conversación en este tiempo, se asigna automáticamente',
'admin.automation.assignment_strategy': 'Estrategia',
'admin.automation.strategy_round_robin': 'Round-robin (por turnos)',
'admin.automation.strategy_least': 'Menos conversaciones abiertas',
'admin.automation.assignment_agents': 'Agentes participantes',
'admin.automation.assignment_disabled_warn': 'La asignación automática está desactivada. Todas las conversaciones requieren asignación manual.',
'admin.automation.save_assignment': 'Guardar configuración',
'admin.automation.trigger_outside_hours': 'Fuera de horario',
'admin.automation.trigger_inside_hours': 'En horario laboral',
'admin.automation.no_rules': 'Aún no hay reglas en esta categoría',
'admin.automation.fallback_only_one': 'Solo se permite 1 regla fallback',
```

- [ ] **Step 3: Add English translations**

Same keys in `en:` block:

```js
'admin.nav.automation': 'Automations',
'admin.automation.tab_rules': 'Auto-reply Rules',
'admin.automation.tab_hours': 'Business Hours',
'admin.automation.tab_assignment': 'Auto-Assignment',
'admin.automation.cat_greeting': 'Greeting',
'admin.automation.cat_greeting_desc': 'First contact',
'admin.automation.cat_schedule': 'Schedule',
'admin.automation.cat_schedule_desc': 'Outside / Inside hours',
'admin.automation.cat_keywords': 'Keywords',
'admin.automation.cat_keywords_desc': 'Keyword-based replies',
'admin.automation.cat_assignment': 'Assignment',
'admin.automation.cat_assignment_desc': 'Agent auto-assignment',
'admin.automation.cat_fallback': 'Fallback',
'admin.automation.cat_fallback_desc': 'Default reply',
'admin.automation.rule_name': 'Rule name',
'admin.automation.rule_active': 'Active',
'admin.automation.rule_priority': 'Priority',
'admin.automation.rule_trigger': 'Trigger',
'admin.automation.rule_response': 'Response message',
'admin.automation.rule_delay': 'Delay (seconds)',
'admin.automation.rule_daily_limit': 'Daily limit',
'admin.automation.rule_unlimited': 'Unlimited',
'admin.automation.add_rule': 'Add rule',
'admin.automation.edit_rule': 'Edit rule',
'admin.automation.save_rule': 'Save rule',
'admin.automation.cancel': 'Cancel',
'admin.automation.add_keyword': 'Add',
'admin.automation.keyword_placeholder': 'New keyword...',
'admin.automation.markers_hint': 'Available markers:',
'admin.automation.timezone': 'Timezone',
'admin.automation.day_mon': 'Monday',
'admin.automation.day_tue': 'Tuesday',
'admin.automation.day_wed': 'Wednesday',
'admin.automation.day_thu': 'Thursday',
'admin.automation.day_fri': 'Friday',
'admin.automation.day_sat': 'Saturday',
'admin.automation.day_sun': 'Sunday',
'admin.automation.closed': 'Closed',
'admin.automation.add_slot': 'Add slot',
'admin.automation.save_hours': 'Save hours',
'admin.automation.assignment_enabled': 'Auto-assignment',
'admin.automation.assignment_desc': 'When enabled, new messages are automatically assigned',
'admin.automation.assignment_timeout': 'Assignment timeout (minutes)',
'admin.automation.assignment_timeout_hint': 'If no agent assigns the conversation within this time, it is automatically assigned',
'admin.automation.assignment_strategy': 'Strategy',
'admin.automation.strategy_round_robin': 'Round-robin (by turns)',
'admin.automation.strategy_least': 'Fewest open conversations',
'admin.automation.assignment_agents': 'Participating agents',
'admin.automation.assignment_disabled_warn': 'Auto-assignment is disabled. All conversations require manual assignment.',
'admin.automation.save_assignment': 'Save configuration',
'admin.automation.trigger_outside_hours': 'Outside business hours',
'admin.automation.trigger_inside_hours': 'Inside business hours',
'admin.automation.no_rules': 'No rules in this category yet',
'admin.automation.fallback_only_one': 'Only 1 fallback rule allowed',
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/i18n.js
git commit -m "feat: i18n keys for automation section (CA/ES/EN)"
```

---

### Task 8: Frontend AutomationSection Component

**Files:**
- Create: `frontend/src/pages/admin/AutomationSection.js`

- [ ] **Step 1: Create the main AutomationSection component**

```jsx
import { useState, useEffect } from 'react';
import { automationApi, agentsApi } from '../../lib/api';
import { toast } from 'sonner';
import {
  Lightning, Chat, Clock, MagnifyingGlass, UserPlus,
  Warning, Plus, Pencil, Trash, X,
} from '@phosphor-icons/react';

const CATEGORIES = [
  { id: 'greeting', color: '#22C55E', bg: '#F0FDF4', border: '#BBF7D0',
    icon: Chat, key: 'cat_greeting', descKey: 'cat_greeting_desc', num: 1 },
  { id: 'schedule', color: '#F97316', bg: '#FFF7ED', border: '#FED7AA',
    icon: Clock, key: 'cat_schedule', descKey: 'cat_schedule_desc', num: 2 },
  { id: 'keywords', color: '#3B82F6', bg: '#EFF6FF', border: '#BFDBFE',
    icon: MagnifyingGlass, key: 'cat_keywords', descKey: 'cat_keywords_desc', num: 3 },
  { id: 'assignment', color: '#8B5CF6', bg: '#F5F3FF', border: '#DDD6FE',
    icon: UserPlus, key: 'cat_assignment', descKey: 'cat_assignment_desc', num: 4 },
  { id: 'fallback', color: '#EF4444', bg: '#FEF2F2', border: '#FECACA',
    icon: Warning, key: 'cat_fallback', descKey: 'cat_fallback_desc', num: 5 },
];

const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAY_KEY_MAP = { mon: 'day_mon', tue: 'day_tue', wed: 'day_wed', thu: 'day_thu', fri: 'day_fri', sat: 'day_sat', sun: 'day_sun' };

export default function AutomationSection({ t, locale }) {
  const [tab, setTab] = useState('rules');

  return (
    <div className="space-y-6" style={{ fontFamily: 'IBM Plex Sans, sans-serif' }}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>
            <Lightning size={18} weight="fill" className="inline mr-2 text-amber-500" />
            {t('admin.nav.automation') || 'Automatitzacions'}
          </h2>
        </div>
      </div>

      {/* Internal Tabs */}
      <div className="flex gap-0 border-b-2 border-[#E2E8F0]">
        {['rules', 'hours', 'assignment'].map(tabId => (
          <button key={tabId} onClick={() => setTab(tabId)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${
              tab === tabId
                ? 'text-[#0F172A] border-b-2 border-[#0F172A] -mb-0.5'
                : 'text-[#94A3B8] hover:text-[#475569]'
            }`}>
            {t(`admin.automation.tab_${tabId}`)}
          </button>
        ))}
      </div>

      {tab === 'rules' && <RulesTab t={t} />}
      {tab === 'hours' && <BusinessHoursTab t={t} />}
      {tab === 'assignment' && <AssignmentTab t={t} />}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// RULES TAB
// ═══════════════════════════════════════════════════════════════

function RulesTab({ t }) {
  const [rules, setRules] = useState([]);
  const [editingRule, setEditingRule] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const res = await automationApi.getRules();
      setRules(res.data.rules || []);
    } catch { /* tables may not exist yet */ }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const handleToggle = async (ruleId) => {
    try {
      const res = await automationApi.toggleRule(ruleId);
      setRules(prev => prev.map(r => r.id === ruleId ? { ...r, is_active: res.data.is_active } : r));
    } catch (e) { toast.error('Error toggling rule'); }
  };

  const handleDelete = async (ruleId) => {
    try {
      await automationApi.deleteRule(ruleId);
      setRules(prev => prev.filter(r => r.id !== ruleId));
      toast.success('Rule deleted');
    } catch (e) { toast.error('Error deleting rule'); }
  };

  const handleSave = async (data) => {
    try {
      if (data.id) {
        const res = await automationApi.updateRule(data.id, data);
        setRules(prev => prev.map(r => r.id === data.id ? res.data.rule : r));
      } else {
        const res = await automationApi.createRule(data);
        setRules(prev => [...prev, res.data.rule]);
      }
      setEditingRule(null);
      toast.success(data.id ? 'Rule updated' : 'Rule created');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error saving rule');
    }
  };

  if (loading) return <p className="text-sm text-[#94A3B8] py-4">{t('general.loading')}</p>;

  return (
    <div className="space-y-3">
      {CATEGORIES.map(cat => {
        const catRules = (rules || []).filter(r => r.category === cat.id).sort((a, b) => a.priority - b.priority);
        const isAssignment = cat.id === 'assignment';
        return (
          <div key={cat.id} className="border border-[#E2E8F0] rounded-lg overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5" style={{ background: cat.bg, borderBottom: `1px solid ${cat.border}` }}>
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 flex items-center justify-center rounded-full text-white text-[10px] font-bold" style={{ background: cat.color }}>{cat.num}</span>
                <span className="text-xs font-bold" style={{ color: cat.color }}>{t(`admin.automation.${cat.key}`)}</span>
                <span className="text-[10px] text-[#64748B]">{t(`admin.automation.${cat.descKey}`)}</span>
              </div>
              {!isAssignment && !(cat.id === 'fallback' && catRules.length > 0) && (
                <button onClick={() => setEditingRule({ category: cat.id, is_active: true, priority: catRules.length + 1, trigger_config: {}, response_text: '', delay_seconds: 0, daily_limit: null })}
                  className="text-[11px] px-2.5 py-1 bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] flex items-center gap-1">
                  <Plus size={11} /> {t('admin.automation.add_rule')}
                </button>
              )}
              {isAssignment && (
                <span className="text-[10px] text-[#64748B]">⏻ Configurable a la pestanya Assignació</span>
              )}
            </div>
            <div className="divide-y divide-[#F1F5F9]">
              {catRules.length === 0 && !isAssignment ? (
                <p className="px-4 py-3 text-[11px] text-[#94A3B8] italic">{t('admin.automation.no_rules')}</p>
              ) : (
                catRules.map(rule => (
                  <div key={rule.id} className="flex items-center gap-3 px-4 py-2.5 text-xs">
                    <span className="w-5 text-center font-bold text-[#94A3B8]">{rule.priority}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-[#0F172A] truncate">{rule.name}</div>
                      <div className="text-[10px] text-[#64748B]">
                        {_describeTrigger(rule.category, rule.trigger_config, t)}
                        {rule.delay_seconds > 0 ? ` · Delay: ${rule.delay_seconds}s` : ''}
                        {rule.daily_limit ? ` · Límit: ${rule.daily_limit}/dia` : ''}
                      </div>
                    </div>
                    {/* Toggle */}
                    <button onClick={() => handleToggle(rule.id)}
                      className={`relative w-7 h-4 rounded-full flex-shrink-0 transition-colors ${rule.is_active ? 'bg-green-500' : 'bg-[#CBD5E1]'}`}>
                      <div className={`absolute top-0.5 w-3 h-3 bg-white rounded-full shadow transition-all ${rule.is_active ? 'right-0.5' : 'left-0.5'}`} />
                    </button>
                    <button onClick={() => setEditingRule({ ...rule })} className="text-[#94A3B8] hover:text-[#0F172A]"><Pencil size={12} /></button>
                    <button onClick={() => handleDelete(rule.id)} className="text-[#94A3B8] hover:text-red-500"><Trash size={12} /></button>
                  </div>
                ))
              )}
            </div>
          </div>
        );
      })}

      {editingRule && (
        <RuleEditorModal rule={editingRule} t={t}
          onClose={() => setEditingRule(null)}
          onSave={handleSave} />
      )}
    </div>
  );
}


function _describeTrigger(category, triggerConfig, t) {
  if (category === 'greeting') return t('admin.automation.cat_greeting_desc');
  if (category === 'schedule') {
    const type = (triggerConfig && triggerConfig.type) || 'outside_hours';
    return type === 'outside_hours' ? t('admin.automation.trigger_outside_hours') : t('admin.automation.trigger_inside_hours');
  }
  if (category === 'keywords') {
    const kws = (triggerConfig && triggerConfig.keywords) || [];
    return kws.length ? kws.slice(0, 3).join(', ') + (kws.length > 3 ? '...' : '') : 'Sense paraules';
  }
  if (category === 'fallback') return t('admin.automation.cat_fallback_desc');
  return '';
}


// ═══════════════════════════════════════════════════════════════
// RULE EDITOR MODAL
// ═══════════════════════════════════════════════════════════════

function RuleEditorModal({ rule, t, onClose, onSave }) {
  const [form, setForm] = useState({
    id: rule.id || null,
    name: rule.name || '',
    is_active: rule.is_active !== undefined ? rule.is_active : true,
    priority: rule.priority || 1,
    category: rule.category,
    trigger_config: rule.trigger_config || {},
    response_text: rule.response_text || '',
    delay_seconds: rule.delay_seconds || 0,
    daily_limit: rule.daily_limit || null,
  });

  const handleKeywordAdd = () => {
    const input = document.getElementById('kw-input');
    const word = (input?.value || '').trim().toLowerCase();
    if (!word) return;
    const current = form.trigger_config?.keywords || [];
    if (current.includes(word)) return;
    setForm(f => ({ ...f, trigger_config: { ...f.trigger_config, keywords: [...current, word], match_mode: 'any' } }));
    if (input) input.value = '';
  };

  const handleKeywordRemove = (kw) => {
    const current = form.trigger_config?.keywords || [];
    setForm(f => ({ ...f, trigger_config: { ...f.trigger_config, keywords: current.filter(k => k !== kw), match_mode: 'any' } }));
  };

  const handleSave = () => {
    if (!form.name.trim()) return;
    onSave({
      id: form.id,
      category: form.category,
      name: form.name.trim(),
      is_active: form.is_active,
      priority: form.priority,
      trigger_config: form.trigger_config,
      response_text: form.response_text,
      delay_seconds: form.delay_seconds,
      daily_limit: form.daily_limit || null,
    });
  };

  const isSchedule = form.category === 'schedule';
  const isKeywords = form.category === 'keywords';
  const isSimple = form.category === 'greeting' || form.category === 'fallback';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} style={{ fontFamily: 'IBM Plex Sans, sans-serif' }}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#E2E8F0]">
          <h3 className="text-sm font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>
            {form.id ? t('admin.automation.edit_rule') : t('admin.automation.add_rule')}
          </h3>
          <button onClick={onClose} className="text-[#94A3B8] hover:text-[#0F172A]"><X size={16} /></button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* Name */}
          <div>
            <label className="text-[11px] font-semibold text-[#475569] block mb-1">{t('admin.automation.rule_name')}</label>
            <input type="text" value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full px-3 py-2 text-xs border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]"
              placeholder="Ex: Fora d'horari" />
          </div>

          {/* Active toggle */}
          <div className="flex items-center justify-between px-3 py-2 bg-[#F8FAFC] rounded-md">
            <span className="text-xs font-semibold text-[#475569]">{t('admin.automation.rule_active')}</span>
            <button onClick={() => setForm(f => ({ ...f, is_active: !f.is_active }))}
              className={`relative w-8 h-4.5 rounded-full transition-colors ${form.is_active ? 'bg-green-500' : 'bg-[#CBD5E1]'}`}>
              <div className={`absolute top-0.5 w-3.5 h-3.5 bg-white rounded-full shadow transition-all ${form.is_active ? 'right-0.5' : 'left-0.5'}`} />
            </button>
          </div>

          {/* Priority */}
          <div>
            <label className="text-[11px] font-semibold text-[#475569] block mb-1">{t('admin.automation.rule_priority')}</label>
            <input type="number" value={form.priority} min={1}
              onChange={e => setForm(f => ({ ...f, priority: parseInt(e.target.value) || 1 }))}
              className="w-24 px-3 py-2 text-xs border border-[#E2E8F0] rounded-md" />
          </div>

          {/* Trigger (varies by category) */}
          {!isSimple && (
            <>
              <div className="border-t border-[#E2E8F0] pt-3">
                <div className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wide mb-2">🎯 {t('admin.automation.rule_trigger')}</div>

                {isSchedule && (
                  <select value={form.trigger_config?.type || 'outside_hours'}
                    onChange={e => setForm(f => ({ ...f, trigger_config: { type: e.target.value } }))}
                    className="w-full px-3 py-2 text-xs border border-[#E2E8F0] rounded-md bg-white">
                    <option value="outside_hours">{t('admin.automation.trigger_outside_hours')}</option>
                    <option value="inside_hours">{t('admin.automation.trigger_inside_hours')}</option>
                  </select>
                )}

                {isKeywords && (
                  <div>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {(form.trigger_config?.keywords || []).map(kw => (
                        <span key={kw} className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#EFF6FF] border border-[#BFDBFE] rounded-full text-[11px] text-[#1E40AF]">
                          {kw}
                          <button onClick={() => handleKeywordRemove(kw)} className="font-bold hover:text-red-500">×</button>
                        </span>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <input id="kw-input" type="text"
                        className="flex-1 px-3 py-1.5 text-xs border border-[#E2E8F0] rounded-md"
                        placeholder={t('admin.automation.keyword_placeholder')}
                        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleKeywordAdd(); } }} />
                      <button onClick={handleKeywordAdd}
                        className="px-3 py-1.5 text-xs bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B]">
                        {t('admin.automation.add_keyword')}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}

          {/* Response text */}
          <div className="border-t border-[#E2E8F0] pt-3">
            <div className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wide mb-2">⚡ {t('admin.automation.rule_response')}</div>
            <textarea rows={3} value={form.response_text}
              onChange={e => setForm(f => ({ ...f, response_text: e.target.value }))}
              className="w-full px-3 py-2 text-xs border border-[#E2E8F0] rounded-md resize-none font-mono"
              placeholder="Escriu el missatge de resposta..." />
            <p className="text-[10px] text-[#94A3B8] mt-1">
              {t('admin.automation.markers_hint')} <code className="bg-[#F1F5F9] px-1 rounded">{'{{agent_name}}'} {'{{business_name}}'} {'{{contact_name}}'}</code>
            </p>
          </div>

          {/* Delay + Daily limit */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold text-[#475569] block mb-1">⏱️ {t('admin.automation.rule_delay')}</label>
              <input type="number" value={form.delay_seconds} min={0}
                onChange={e => setForm(f => ({ ...f, delay_seconds: parseInt(e.target.value) || 0 }))}
                className="w-full px-3 py-2 text-xs border border-[#E2E8F0] rounded-md" />
            </div>
            <div>
              <label className="text-[11px] font-semibold text-[#475569] block mb-1">📊 {t('admin.automation.rule_daily_limit')}</label>
              <input type="number" value={form.daily_limit || ''} min={1}
                placeholder={t('admin.automation.rule_unlimited')}
                onChange={e => setForm(f => ({ ...f, daily_limit: e.target.value ? parseInt(e.target.value) : null }))}
                className="w-full px-3 py-2 text-xs border border-[#E2E8F0] rounded-md" />
            </div>
          </div>
        </div>

        {/* Buttons */}
        <div className="flex justify-end gap-2 px-5 py-3 border-t border-[#E2E8F0] bg-[#F8FAFC]">
          <button onClick={onClose}
            className="px-3 py-1.5 text-xs border border-[#E2E8F0] rounded-md text-[#475569] hover:bg-white">
            {t('admin.automation.cancel')}
          </button>
          <button onClick={handleSave}
            className="px-4 py-1.5 text-xs bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B]">
            {t('admin.automation.save_rule')}
          </button>
        </div>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// BUSINESS HOURS TAB
// ═══════════════════════════════════════════════════════════════

function BusinessHoursTab({ t }) {
  const [timezone, setTimezone] = useState('Europe/Madrid');
  const [schedule, setSchedule] = useState({});
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const res = await automationApi.getBusinessHours();
      const bh = res.data.business_hours;
      if (bh) {
        setTimezone(bh.timezone || 'Europe/Madrid');
        setSchedule(bh.schedule || {});
      }
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const handleDayToggle = (dayKey) => {
    setSchedule(prev => {
      const current = prev[dayKey] || [];
      if (current.length > 0) return { ...prev, [dayKey]: [] }; // disable day
      return { ...prev, [dayKey]: [['09:00', '13:00']] }; // enable with default slot
    });
  };

  const handleSlotChange = (dayKey, slotIdx, field, value) => {
    setSchedule(prev => {
      const slots = [...(prev[dayKey] || [])];
      if (!slots[slotIdx]) return prev;
      slots[slotIdx] = [...slots[slotIdx]];
      slots[slotIdx][field] = value;
      return { ...prev, [dayKey]: slots };
    });
  };

  const handleAddSlot = (dayKey) => {
    setSchedule(prev => ({
      ...prev,
      [dayKey]: [...(prev[dayKey] || []), ['09:00', '13:00']],
    }));
  };

  const handleRemoveSlot = (dayKey, slotIdx) => {
    setSchedule(prev => {
      const slots = (prev[dayKey] || []).filter((_, i) => i !== slotIdx);
      return { ...prev, [dayKey]: slots };
    });
  };

  const handleSave = async () => {
    try {
      await automationApi.updateBusinessHours({ timezone, schedule });
      toast.success(t('admin.automation.save_hours'));
    } catch (e) { toast.error('Error saving'); }
  };

  if (loading) return <p className="text-sm text-[#94A3B8] py-4">{t('general.loading')}</p>;

  return (
    <div className="space-y-4">
      {/* Timezone */}
      <div>
        <label className="text-[11px] font-semibold text-[#475569] block mb-1">{t('admin.automation.timezone')}</label>
        <select value={timezone} onChange={e => setTimezone(e.target.value)}
          className="w-72 px-3 py-2 text-xs border border-[#E2E8F0] rounded-md bg-white">
          <option>Europe/Madrid</option>
          <option>Europe/London</option>
          <option>Europe/Paris</option>
          <option>Europe/Berlin</option>
          <option>America/New_York</option>
          <option>America/Chicago</option>
          <option>America/Los_Angeles</option>
          <option>Asia/Tokyo</option>
        </select>
      </div>

      {/* Days grid */}
      <div className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wide mb-2">Dies i franges</div>
      <div className="space-y-2">
        {DAY_KEYS.map(dayKey => {
          const slots = schedule[dayKey] || [];
          const isOpen = slots.length > 0;
          return (
            <div key={dayKey} className={`flex items-start gap-3 p-3 rounded-lg border ${isOpen ? 'bg-[#F8FAFC] border-[#E2E8F0]' : 'bg-[#F1F5F9] border-[#E2E8F0]'}`}>
              <div className="flex items-center gap-2 min-w-[110px] pt-1">
                <button onClick={() => handleDayToggle(dayKey)}
                  className={`relative w-8 h-4.5 rounded-full transition-colors ${isOpen ? 'bg-green-500' : 'bg-[#CBD5E1]'}`}>
                  <div className={`absolute top-0.5 w-3.5 h-3.5 bg-white rounded-full shadow transition-all ${isOpen ? 'right-0.5' : 'left-0.5'}`} />
                </button>
                <span className={`text-xs font-semibold ${isOpen ? 'text-[#0F172A]' : 'text-[#94A3B8]'}`}>
                  {t(`admin.automation.${DAY_KEY_MAP[dayKey]}`)}
                </span>
              </div>
              <div className="flex-1 space-y-1.5">
                {isOpen ? (
                  <>
                    {slots.map((slot, i) => (
                      <div key={i} className="flex items-center gap-1.5">
                        <input type="time" value={slot[0] || ''}
                          onChange={e => handleSlotChange(dayKey, i, 0, e.target.value)}
                          className="w-24 px-2 py-1 text-[11px] border border-[#E2E8F0] rounded-md" />
                        <span className="text-[11px] text-[#94A3B8]">a</span>
                        <input type="time" value={slot[1] || ''}
                          onChange={e => handleSlotChange(dayKey, i, 1, e.target.value)}
                          className="w-24 px-2 py-1 text-[11px] border border-[#E2E8F0] rounded-md" />
                        <button onClick={() => handleRemoveSlot(dayKey, i)}
                          className="text-[#94A3B8] hover:text-red-500 ml-1">
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                    <button onClick={() => handleAddSlot(dayKey)}
                      className="text-[10px] px-2 py-0.5 border border-dashed border-[#CBD5E1] rounded text-[#64748B] hover:bg-white">
                      + {t('admin.automation.add_slot')}
                    </button>
                  </>
                ) : (
                  <span className="text-[11px] text-[#94A3B8]">{t('admin.automation.closed')}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex justify-end">
        <button onClick={handleSave}
          className="px-4 py-2 text-sm bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B]">
          {t('admin.automation.save_hours')}
        </button>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// ASSIGNMENT TAB
// ═══════════════════════════════════════════════════════════════

function AssignmentTab({ t }) {
  const [config, setConfig] = useState(null);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const [aRes, agRes] = await Promise.all([
        automationApi.getAssignment(),
        agentsApi.list(),
      ]);
      setConfig(aRes.data.assignment || {});
      setAgents(agRes.data.agents || []);
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    try {
      await automationApi.updateAssignment({
        is_enabled: config.is_enabled,
        timeout_minutes: config.timeout_minutes,
        strategy: config.strategy,
        agent_pool: config.agent_pool,
      });
      toast.success(t('admin.automation.save_assignment'));
    } catch (e) { toast.error('Error saving'); }
  };

  const toggleAgent = (agentId) => {
    setConfig(prev => {
      const pool = prev.agent_pool || [];
      if (pool.includes(agentId)) {
        return { ...prev, agent_pool: pool.filter(id => id !== agentId) };
      }
      return { ...prev, agent_pool: [...pool, agentId] };
    });
  };

  if (loading || !config) return <p className="text-sm text-[#94A3B8] py-4">{t('general.loading')}</p>;

  const enabled = config.is_enabled;

  return (
    <div className="space-y-5">
      {/* Master toggle */}
      <div className="flex items-center justify-between p-4 bg-[#F5F3FF] border border-[#DDD6FE] rounded-lg">
        <div>
          <div className="text-sm font-bold text-[#4C1D95]">{t('admin.automation.assignment_enabled')}</div>
          <div className="text-[11px] text-[#7C3AED] mt-0.5">{t('admin.automation.assignment_desc')}</div>
        </div>
        <button onClick={() => setConfig(p => ({ ...p, is_enabled: !p.is_enabled }))}
          className={`relative w-10 h-5.5 rounded-full transition-colors ${enabled ? 'bg-[#8B5CF6]' : 'bg-[#CBD5E1]'}`}>
          <div className={`absolute top-0.5 w-4.5 h-4.5 bg-white rounded-full shadow transition-all ${enabled ? 'right-0.5' : 'left-0.5'}`} />
        </button>
      </div>

      {/* Timeout */}
      <div className={`p-4 border rounded-lg ${!enabled ? 'opacity-40 pointer-events-none' : 'border-[#E2E8F0] bg-[#F8FAFC]'}`}>
        <label className="text-[11px] font-semibold text-[#475569] block mb-1">{t('admin.automation.assignment_timeout')}</label>
        <input type="number" value={config.timeout_minutes || 5} min={1}
          onChange={e => setConfig(p => ({ ...p, timeout_minutes: parseInt(e.target.value) || 5 }))}
          disabled={!enabled}
          className="w-32 px-3 py-2 text-xs border border-[#E2E8F0] rounded-md" />
        <p className="text-[10px] text-[#94A3B8] mt-1.5">{t('admin.automation.assignment_timeout_hint')}</p>
      </div>

      {/* Strategy */}
      <div className={`p-4 border rounded-lg ${!enabled ? 'opacity-40 pointer-events-none' : 'border-[#E2E8F0] bg-[#F8FAFC]'}`}>
        <label className="text-[11px] font-semibold text-[#475569] block mb-1">{t('admin.automation.assignment_strategy')}</label>
        <select value={config.strategy || 'round_robin'}
          onChange={e => setConfig(p => ({ ...p, strategy: e.target.value }))}
          disabled={!enabled}
          className="w-64 px-3 py-2 text-xs border border-[#E2E8F0] rounded-md bg-white">
          <option value="round_robin">{t('admin.automation.strategy_round_robin')}</option>
          <option value="least_conversations">{t('admin.automation.strategy_least')}</option>
        </select>
      </div>

      {/* Agent pool */}
      <div className={`p-4 border rounded-lg ${!enabled ? 'opacity-40 pointer-events-none' : 'border-[#E2E8F0] bg-[#F8FAFC]'}`}>
        <label className="text-[11px] font-semibold text-[#475569] block mb-2">{t('admin.automation.assignment_agents')}</label>
        <div className="space-y-1.5">
          {agents.map(agent => (
            <label key={agent.id} className="flex items-center gap-2 text-xs cursor-pointer">
              <input type="checkbox" checked={(config.agent_pool || []).includes(agent.id)}
                onChange={() => toggleAgent(agent.id)}
                disabled={!enabled}
                className="accent-[#8B5CF6]" />
              {agent.full_name || agent.email || agent.id}
            </label>
          ))}
          {agents.length === 0 && (
            <p className="text-[11px] text-[#94A3B8] italic">{t('admin.automation.no_rules')}</p>
          )}
        </div>
      </div>

      {/* Warning when disabled */}
      {!enabled && (
        <div className="p-3 bg-[#FEF2F2] border border-[#FECACA] rounded-md text-[11px] text-[#991B1B]">
          ⚠️ {t('admin.automation.assignment_disabled_warn')}
        </div>
      )}

      <div className="flex justify-end">
        <button onClick={handleSave}
          className="px-4 py-2 text-sm bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B]">
          {t('admin.automation.save_assignment')}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify component compiles**

```bash
cd frontend && npx react-scripts build 2>&1 | tail -5
# Just check no import/compile errors — build may fail on missing AdminPage changes (that's Task 9)
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/AutomationSection.js
git commit -m "feat: AutomationSection component — rules, business hours, assignment tabs"
```

---

### Task 9: Integrate into AdminPage

**Files:**
- Modify: `frontend/src/pages/AdminPage.js`

- [ ] **Step 1: Add import and nav item**

In `AdminPage.js`, add the import after line 15 (`ContactsImportSection`):

```js
import AutomationSection from './admin/AutomationSection';
```

Add `Lightning` to the phosphor icons import on line 7:

```js
import { Gear, LinkSimple, ClockCounterClockwise, CheckCircle, XCircle, CaretRight, ArrowLeft, ChatText, Buildings, DownloadSimple, Lightning } from '@phosphor-icons/react';
```

Add to `NAV_ITEMS` array (after templates or before logs — placed after templates to keep related messaging items together):

```js
{ id: 'automation', icon: Lightning, key: 'admin.nav.automation' },
```

- [ ] **Step 2: Add section render**

In the main render, add the automation case after line 156 (`{section === 'contacts-import' ...}`):

```jsx
{section === 'automation' && <AutomationSection t={t} locale={locale} />}
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npx react-scripts build 2>&1 | tail -10
```

Expected: successful build with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AdminPage.js
git commit -m "feat: add Automations nav item and section to AdminPage"
```

---

### Task 10: Integration Tests

**Files:**
- Create: `backend/tests/test_automation.py`

- [ ] **Step 1: Write backend tests**

```python
"""
Tests for automation engine and API endpoints.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.automation_engine import _evaluate_keywords_trigger, _substitute_markers


class TestKeywordsTrigger:
    def test_single_match(self):
        config = {"keywords": ["preu", "pressupost"]}
        assert _evaluate_keywords_trigger(config, "quin preu te?") is True

    def test_no_match(self):
        config = {"keywords": ["preu", "pressupost"]}
        assert _evaluate_keywords_trigger(config, "hola que tal") is False

    def test_empty_body(self):
        config = {"keywords": ["preu"]}
        assert _evaluate_keywords_trigger(config, "") is False

    def test_empty_keywords(self):
        config = {"keywords": []}
        assert _evaluate_keywords_trigger(config, "preu") is False

    def test_case_insensitive(self):
        config = {"keywords": ["preu"]}
        assert _evaluate_keywords_trigger(config, "PREU si us plau") is True

    def test_partial_match(self):
        config = {"keywords": ["preu"]}
        assert _evaluate_keywords_trigger(config, "quin pressupost teniu?") is False


class TestMarkerSubstitution:
    @pytest.mark.asyncio
    async def test_agent_name_default(self):
        """When no supabase, defaults to 'el nostre equip'"""
        result = await _substitute_markers(
            "Hola {{agent_name}}", None, None, {}, None
        )
        assert "el nostre equip" in result

    @pytest.mark.asyncio
    async def test_no_markers(self):
        result = await _substitute_markers(
            "Hola, com et podem ajudar?", None, None, {}, None
        )
        assert result == "Hola, com et podem ajudar?"

    @pytest.mark.asyncio
    async def test_business_name_default(self):
        result = await _substitute_markers(
            "Benvingut a {{business_name}}", None, None, {}, None
        )
        assert "el nostre equip" in result

    @pytest.mark.asyncio
    async def test_contact_name_from_phone(self):
        result = await _substitute_markers(
            "Hola {{contact_name}}", None, None, {"phone": "34606919022"}, None
        )
        assert "34606919022" in result
```

- [ ] **Step 2: Run tests**

```bash
cd backend && python -m pytest tests/test_automation.py -v
```

Expected: 8 passed

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_automation.py
git commit -m "test: automation engine — keywords trigger and marker substitution"
```

---

### Task 11: Final Verification

- [ ] **Step 1: Full backend test suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All existing tests still pass. New automation tests pass.

- [ ] **Step 2: Verify backend server starts clean**

```bash
cd backend && python -c "from server import app; print('Server OK, routes:', len(app.routes))"
```

Expected: `Server OK, routes: XX` (no import errors)

- [ ] **Step 3: Verify admin API endpoints return 401 (auth required)**

```bash
curl -s http://localhost:8000/api/admin/automation/rules | head -1
```

Expected: `{"detail":"No autenticat"}`

- [ ] **Step 4: Commit any remaining files**

```bash
git add --all
git commit -m "chore: final integration verification for Section 5 automation"
```

---

## Summary

| Task | Files | Key Deliverable |
|---|---|---|
| 1 | `supabase_automation_migration.sql` | 4 DB tables |
| 2 | `services/automation_engine.py` | Category pipeline engine |
| 3 | `routers/automation.py` | REST API (rules, hours, assignment) |
| 4 | `routers/webhook.py` | Engine integration |
| 5 | `server.py` | Router registration |
| 6 | `lib/api.js` | Frontend API client |
| 7 | `lib/i18n.js` | CA/ES/EN translations |
| 8 | `admin/AutomationSection.js` | Full UI (3 tabs + modal) |
| 9 | `AdminPage.js` | Nav + section render |
| 10 | `tests/test_automation.py` | Backend unit tests |
| 11 | Verification | Full test suite + manual checks |

**Total:** 11 tasks, ~40 steps, estimated 2-3 hours to complete.
