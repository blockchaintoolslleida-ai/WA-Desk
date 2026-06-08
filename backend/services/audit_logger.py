"""
Audit Logger - Track all admin actions for compliance
"""
import logging
from datetime import datetime, timezone
import uuid
from database import get_supabase_admin

logger = logging.getLogger(__name__)

async def log_audit(tenant_id: str, user_id: str, action_type: str, entity_type: str,
                    entity_id: str = None, description: str = '', ip_address: str = None):
    try:
        supabase = get_supabase_admin()
        supabase.table('audit_logs').insert({
            'id': str(uuid.uuid4()),
            'tenant_id': tenant_id,
            'user_id': user_id,
            'action': action_type,
            'action_type': action_type,
            'entity_type': entity_type,
            'entity_id': entity_id or '',
            'description': description,
            'ip_address': ip_address,
            'created_at': datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.error(f"Audit log error: {e}")
