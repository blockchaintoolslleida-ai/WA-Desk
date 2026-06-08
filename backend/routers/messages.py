"""
Messages Router - Send messages via WhatsApp (with reply/quote support)
"""
from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional
from pydantic import BaseModel
import logging
from datetime import datetime, timezone
import uuid
from database import get_supabase_admin
from models import WhatsAppOutboundMessage
from services.whatsapp import send_whatsapp_message, normalize_phone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/messages", tags=["Messages"])


class SendMessageRequest(BaseModel):
    body: str
    reply_to_id: Optional[str] = None


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


@router.post("/send/{conversation_id}")
async def send_message(
    conversation_id: str,
    req: SendMessageRequest,
    authorization: Optional[str] = Header(None),
    case_id: Optional[str] = Query(None),
):
    """Send an outgoing message via WhatsApp, optionally as a reply to another message"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()

    try:
        conv_res = supabase.table('conversations').select(
            '*, contacts(phone, name)'
        ).eq('id', conversation_id).single().execute()

        if not conv_res.data:
            raise HTTPException(status_code=404, detail="Conversa no trobada")

        contact = conv_res.data.get('contacts', {})
        phone = contact.get('phone')
        if not phone:
            raise HTTPException(status_code=400, detail="Contacte sense telefon")

        # If replying, auto-inherit case_id from the replied message
        actual_case_id = case_id
        reply_to_id = req.reply_to_id
        reply_to_wamid = None

        if reply_to_id:
            replied_msg = supabase.table('messages').select('case_id, whatsapp_message_id').eq('id', reply_to_id).single().execute()
            if replied_msg.data:
                if not actual_case_id and replied_msg.data.get('case_id'):
                    actual_case_id = replied_msg.data['case_id']
                # Get the WhatsApp message ID for the context/quote
                reply_to_wamid = replied_msg.data.get('whatsapp_message_id')

        # If still no case_id and only 1 active case, auto-link
        if not actual_case_id:
            active_cases = supabase.table('cases').select('id').eq(
                'conversation_id', conversation_id
            ).eq('is_active', True).execute()
            if active_cases.data and len(active_cases.data) == 1:
                actual_case_id = active_cases.data[0]['id']

        # Send via WhatsApp (with context for quoted reply) — uses tenant credentials
        wa_result = await send_whatsapp_message(
            WhatsAppOutboundMessage(phone=normalize_phone(phone), body=req.body),
            reply_to_wamid=reply_to_wamid,
            tenant_id=user.get('tenant_id'),
        )
        wa_sent = wa_result.get('ok', False)
        wa_error = wa_result.get('error')
        wa_message_id = wa_result.get('wamid')

        now = datetime.now(timezone.utc).isoformat()

        msg_data = {
            'id': str(uuid.uuid4()),
            'conversation_id': conversation_id,
            'case_id': actual_case_id,
            'direction': 'outgoing',
            'message_type': 'text',
            'body': req.body,
            'sender_agent_id': user['id'],
            'needs_classification': False,
            'reply_to_id': reply_to_id,
            'sent_at': now,
            'created_at': now,
        }
        if wa_message_id:
            msg_data['whatsapp_message_id'] = wa_message_id
        # delivery_status column may not exist yet; try with then without
        try:
            supabase.table('messages').insert({
                **msg_data,
                'delivery_status': 'sent' if wa_sent else 'failed',
                'delivery_error': wa_error,
            }).execute()
        except Exception:
            supabase.table('messages').insert(msg_data).execute()

        supabase.table('conversations').update({
            'last_message_at': now, 'updated_at': now
        }).eq('id', conversation_id).execute()

        if actual_case_id:
            supabase.table('cases').update({
                'last_activity_at': now, 'updated_at': now
            }).eq('id', actual_case_id).execute()

            supabase.table('case_events').insert({
                'id': str(uuid.uuid4()),
                'case_id': actual_case_id,
                'actor_id': user['id'],
                'event_type': 'message_sent',
                'new_value': {'body_preview': req.body[:80], 'whatsapp_sent': wa_sent, 'is_reply': bool(reply_to_id), 'error': wa_error},
                'created_at': now,
            }).execute()

        return {
            "id": msg_data['id'],
            "whatsapp_sent": wa_sent,
            "whatsapp_error": wa_error,
            "body": req.body,
            "sender_agent_name": user['full_name'],
            "case_id": actual_case_id,
            "reply_to_id": reply_to_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(status_code=500, detail="Error enviant missatge")
