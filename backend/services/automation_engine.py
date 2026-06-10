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
