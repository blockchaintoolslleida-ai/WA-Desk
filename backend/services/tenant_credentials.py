"""
Tenant credentials resolver for WhatsApp.
Resolves (access_token, phone_number_id, whatsapp_business_account_id) for a tenant,
falling back to .env values when tenant has no per-tenant config (DEV mode).
"""
import logging
from typing import Optional, Tuple
from database import get_supabase_admin
from services.secrets_manager import decrypt_value
from config import (
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_BUSINESS_ACCOUNT_ID,
)

logger = logging.getLogger(__name__)


def get_env_credentials() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return env-level credentials (DEV fallback). May return None values."""
    return WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_BUSINESS_ACCOUNT_ID


def get_tenant_credentials(tenant_id: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (access_token, phone_number_id, whatsapp_business_account_id) for tenant.

    Resolution order:
      1. If tenant_id provided AND tenant has full config → use tenant credentials
      2. Otherwise fallback to .env (DEV / unconfigured tenant)

    Token is decrypted from whatsapp_secrets.encrypted_access_token.
    """
    env_tok, env_phone, env_waba = get_env_credentials()

    if not tenant_id:
        return env_tok, env_phone, env_waba

    try:
        sb = get_supabase_admin()
        acc_res = sb.table('whatsapp_accounts').select(
            'id, phone_number_id, whatsapp_business_account_id'
        ).eq('tenant_id', tenant_id).limit(1).execute()
        if not acc_res.data:
            return env_tok, env_phone, env_waba
        acc = acc_res.data[0]
        phone_id = acc.get('phone_number_id') or env_phone
        waba_id = acc.get('whatsapp_business_account_id') or env_waba

        sec_res = sb.table('whatsapp_secrets').select(
            'encrypted_access_token'
        ).eq('whatsapp_account_id', acc['id']).limit(1).execute()
        token = env_tok
        if sec_res.data and sec_res.data[0].get('encrypted_access_token'):
            decrypted = decrypt_value(sec_res.data[0]['encrypted_access_token'])
            if decrypted:
                token = decrypted

        return token, phone_id, waba_id
    except Exception as e:
        logger.warning(f"Could not resolve tenant credentials for {tenant_id}: {e}; falling back to env")
        return env_tok, env_phone, env_waba


def resolve_tenant_id_from_conversation(conversation_id: str) -> Optional[str]:
    """Look up tenant_id for a conversation (handles missing column gracefully)."""
    try:
        sb = get_supabase_admin()
        res = sb.table('conversations').select('tenant_id').eq('id', conversation_id).limit(1).execute()
        if res.data and res.data[0].get('tenant_id'):
            return res.data[0]['tenant_id']
    except Exception:
        pass
    return None
