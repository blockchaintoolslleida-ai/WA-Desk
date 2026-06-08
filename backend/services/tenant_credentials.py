"""
Tenant credentials resolver for WhatsApp.
Resolves connection config for a tenant — supports Meta API and OpenWA gateway.
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


def get_tenant_connection_config(tenant_id: Optional[str]) -> dict:
    """Return the full connection configuration for a tenant.

    Returns a dict with at minimum:
      - connection_type: 'meta' or 'openwa'
      - display_phone_number: str or None

    For 'meta' type:
      - access_token: str or None
      - phone_number_id: str or None
      - whatsapp_business_account_id: str or None

    For 'openwa' type:
      - openwa_server_url: str or None
      - openwa_api_key: str or None
      - openwa_session_id: str or None

    Falls back to .env values for Meta when tenant has no config.
    """
    env_tok, env_phone, env_waba = get_env_credentials()

    if not tenant_id:
        return {
            "connection_type": "meta",
            "access_token": env_tok,
            "phone_number_id": env_phone,
            "whatsapp_business_account_id": env_waba,
            "display_phone_number": None,
        }

    try:
        sb = get_supabase_admin()
        acc_res = sb.table('whatsapp_accounts').select(
            'id, connection_type, phone_number_id, whatsapp_business_account_id, '
            'openwa_server_url, openwa_session_id, display_phone_number'
        ).eq('tenant_id', tenant_id).limit(1).execute()

        if not acc_res.data:
            return {
                "connection_type": "meta",
                "access_token": env_tok,
                "phone_number_id": env_phone,
                "whatsapp_business_account_id": env_waba,
                "display_phone_number": None,
            }

        acc = acc_res.data[0]
        connection_type = acc.get('connection_type') or 'meta'

        if connection_type == 'openwa':
            sec_res = sb.table('whatsapp_secrets').select(
                'encrypted_openwa_api_key'
            ).eq('whatsapp_account_id', acc['id']).limit(1).execute()
            api_key = None
            if sec_res.data and sec_res.data[0].get('encrypted_openwa_api_key'):
                decrypted = decrypt_value(sec_res.data[0]['encrypted_openwa_api_key'])
                if decrypted:
                    api_key = decrypted

            return {
                "connection_type": "openwa",
                "openwa_server_url": acc.get('openwa_server_url') or '',
                "openwa_api_key": api_key,
                "openwa_session_id": acc.get('openwa_session_id') or '',
                "display_phone_number": acc.get('display_phone_number') or '',
                # Include Meta fallback for functions that may need it
                "access_token": env_tok,
                "phone_number_id": env_phone,
                "whatsapp_business_account_id": env_waba,
            }

        # Meta connection type (default)
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

        return {
            "connection_type": "meta",
            "access_token": token,
            "phone_number_id": phone_id,
            "whatsapp_business_account_id": waba_id,
            "display_phone_number": acc.get('display_phone_number') or '',
        }

    except Exception as e:
        logger.warning(f"Could not resolve tenant connection config for {tenant_id}: {e}; falling back to env")
        return {
            "connection_type": "meta",
            "access_token": env_tok,
            "phone_number_id": env_phone,
            "whatsapp_business_account_id": env_waba,
            "display_phone_number": None,
        }


def get_tenant_credentials(tenant_id: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (access_token, phone_number_id, whatsapp_business_account_id) for tenant.
    Convenience wrapper around get_tenant_connection_config for callers that only need Meta-style tuple.
    """
    config = get_tenant_connection_config(tenant_id)
    return (
        config.get("access_token"),
        config.get("phone_number_id"),
        config.get("whatsapp_business_account_id"),
    )


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
