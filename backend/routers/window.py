"""
Window 24h Router - WhatsApp conversation window management
Tracks 24h messaging window, provides template sending
"""
from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional, List
from pydantic import BaseModel
import logging
from datetime import datetime, timezone, timedelta
import uuid
from database import get_supabase_admin
from models import WhatsAppOutboundMessage
from services.whatsapp import send_whatsapp_message, send_whatsapp_template, normalize_phone

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Window & Templates"])

# In-memory template config (could be moved to DB later)
TEMPLATES = [
    {
        "id": "followup_generic",
        "name": "followup_generic",
        "category": "UTILITY",
        "languages": {
            "ca": "Hola {{1}}, quedem pendents de la teva resposta. Respon a aquest missatge si necessites ajuda.",
            "es": "Hola {{1}}, quedamos pendientes de tu respuesta. Responde a este mensaje si necesitas ayuda.",
            "en": "Hi {{1}}, we're waiting for your reply. Respond to this message if you need help.",
        },
        "variables": ["customer_name"],
    },
    {
        "id": "reopen_case",
        "name": "reopen_case",
        "category": "UTILITY",
        "languages": {
            "ca": "Hola {{1}}, et contactem des del nostre servei d'atenció. Com podem ajudar-te?",
            "es": "Hola {{1}}, te contactamos desde nuestro servicio de atención. ¿Cómo podemos ayudarte?",
            "en": "Hi {{1}}, we're reaching out from our support team. How can we help you?",
        },
        "variables": ["customer_name"],
    },
]

REMINDER_MESSAGES = {
    "ca": "Quedem pendents de la teva resposta.",
    "es": "Quedamos pendientes de tu respuesta.",
    "en": "We're waiting for your reply.",
}

REMINDER_BODY_PATTERNS = list(REMINDER_MESSAGES.values())


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
    except Exception:
        raise HTTPException(status_code=401, detail="Error d'autenticacio")


def get_last_incoming_timestamp(supabase, conversation_id: str) -> Optional[datetime]:
    """Get the timestamp of the last incoming (customer) message for a conversation"""
    result = supabase.table('messages').select('sent_at').eq(
        'conversation_id', conversation_id
    ).eq('direction', 'incoming').order('sent_at', desc=True).limit(1).execute()

    if result.data and result.data[0].get('sent_at'):
        return datetime.fromisoformat(result.data[0]['sent_at'].replace('Z', '+00:00'))
    return None


def compute_window_status(last_incoming_at: Optional[datetime]) -> dict:
    """Compute window status from last incoming message timestamp"""
    if not last_incoming_at:
        return {
            "window_active": False,
            "window_expires_at": None,
            "seconds_remaining": 0,
            "hours_remaining": 0,
            "minutes_remaining": 0,
            "reminder_zone": False,
        }

    now = datetime.now(timezone.utc)
    expires_at = last_incoming_at + timedelta(hours=24)
    remaining = (expires_at - now).total_seconds()

    return {
        "window_active": remaining > 0,
        "window_expires_at": expires_at.isoformat(),
        "seconds_remaining": max(0, int(remaining)),
        "hours_remaining": max(0, int(remaining // 3600)),
        "minutes_remaining": max(0, int((remaining % 3600) // 60)),
        "reminder_zone": 0 < remaining <= 7200,  # Last 2 hours
    }


@router.get("/window/status/{conversation_id}")
async def get_window_status(conversation_id: str, authorization: Optional[str] = Header(None)):
    """Get the 24h window status for a conversation"""
    await get_user_from_token(authorization)
    supabase = get_supabase_admin()

    last_incoming = get_last_incoming_timestamp(supabase, conversation_id)
    status = compute_window_status(last_incoming)
    status["last_customer_message_at"] = last_incoming.isoformat() if last_incoming else None
    return status


@router.get("/templates")
async def list_templates(authorization: Optional[str] = Header(None)):
    """List available message templates"""
    await get_user_from_token(authorization)
    return TEMPLATES


class TemplateSendRequest(BaseModel):
    template_id: str
    language: str = "ca"
    variables: dict = {}


@router.post("/templates/send/{conversation_id}")
async def send_template(
    conversation_id: str,
    req: TemplateSendRequest,
    authorization: Optional[str] = Header(None),
):
    """Send a template message to reopen the 24h window"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()

    # Find the template
    template = next((t for t in TEMPLATES if t["id"] == req.template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Plantilla no trobada")

    # Get conversation contact
    try:
        conv_res = supabase.table('conversations').select(
            '*, contacts(phone, name)'
        ).eq('id', conversation_id).maybe_single().execute()
    except Exception:
        raise HTTPException(status_code=404, detail="Conversa no trobada")

    if not conv_res.data:
        raise HTTPException(status_code=404, detail="Conversa no trobada")

    contact = conv_res.data.get('contacts', {})
    phone = contact.get('phone')
    if not phone:
        raise HTTPException(status_code=400, detail="Contacte sense telefon")

    customer_name = contact.get('name') or phone

    # Build template body with variables
    lang = req.language if req.language in template["languages"] else "ca"
    body = template["languages"][lang]
    body = body.replace("{{1}}", req.variables.get("customer_name", customer_name))

    # Try sending as template first, fallback to regular message
    wa_sent = await send_whatsapp_template(
        phone=normalize_phone(phone),
        template_name=template["name"],
        language_code=lang,
        components=[{"type": "body", "parameters": [{"type": "text", "text": customer_name}]}],
        tenant_id=user.get('tenant_id'),
    )

    # If template fails (not approved yet), send as regular text with warning
    if not wa_sent:
        logger.warning("Template send failed, falling back to text message")
        fallback = await send_whatsapp_message(
            WhatsAppOutboundMessage(phone=normalize_phone(phone), body=body),
            tenant_id=user.get('tenant_id'),
        )
        wa_sent = fallback.get('ok', False) if isinstance(fallback, dict) else bool(fallback)
        wa_error = fallback.get('error') if isinstance(fallback, dict) else None
    else:
        wa_error = None

    now = datetime.now(timezone.utc).isoformat()

    # Save the sent message
    msg_data = {
        'id': str(uuid.uuid4()),
        'conversation_id': conversation_id,
        'direction': 'outgoing',
        'message_type': 'text',
        'body': f"[Plantilla] {body}",
        'sender_agent_id': user['id'],
        'needs_classification': False,
        'sent_at': now,
        'created_at': now,
    }
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

    return {
        "id": msg_data['id'],
        "whatsapp_sent": wa_sent,
        "whatsapp_error": wa_error,
        "body": body,
        "template_used": template["name"],
    }


async def run_auto_reminder():
    """Background task: send automatic reminder to conversations nearing 24h expiry"""
    supabase = get_supabase_admin()

    try:
        # Get all active conversations
        convs = supabase.table('conversations').select(
            'id, contact_id, contacts(phone, name)'
        ).eq('is_active', True).execute()

        if not convs.data:
            return

        now = datetime.now(timezone.utc)
        reminder_window_start = now - timedelta(hours=22, minutes=5)
        reminder_window_end = now - timedelta(hours=21, minutes=55)

        for conv in convs.data:
            try:
                last_incoming = get_last_incoming_timestamp(supabase, conv['id'])
                if not last_incoming:
                    continue

                # Check if last incoming message is in the reminder window (21h55m - 22h5m ago)
                if not (reminder_window_end <= last_incoming <= reminder_window_start):
                    continue

                # Check if reminder was already sent (look for reminder pattern in recent outgoing messages)
                recent_msgs = supabase.table('messages').select('body, direction, sent_at').eq(
                    'conversation_id', conv['id']
                ).eq('direction', 'outgoing').order('sent_at', desc=True).limit(5).execute()

                already_sent = False
                for msg in (recent_msgs.data or []):
                    if any(pattern in (msg.get('body') or '') for pattern in REMINDER_BODY_PATTERNS):
                        msg_time = datetime.fromisoformat(msg['sent_at'].replace('Z', '+00:00'))
                        if (now - msg_time).total_seconds() < 86400:  # Within last 24h
                            already_sent = True
                            break

                if already_sent:
                    continue

                # Send the reminder
                contact = conv.get('contacts', {})
                phone = contact.get('phone')
                if not phone:
                    continue

                # Send in Catalan by default (main language of the system)
                reminder_body = REMINDER_MESSAGES["ca"]
                wa_result = await send_whatsapp_message(
                    WhatsAppOutboundMessage(phone=normalize_phone(phone), body=reminder_body),
                    tenant_id=conv.get('tenant_id'),
                )
                wa_sent = wa_result.get('ok', False) if isinstance(wa_result, dict) else bool(wa_result)

                # Save as system message
                msg_now = datetime.now(timezone.utc).isoformat()
                supabase.table('messages').insert({
                    'id': str(uuid.uuid4()),
                    'conversation_id': conv['id'],
                    'direction': 'outgoing',
                    'message_type': 'system',
                    'body': reminder_body,
                    'needs_classification': False,
                    'sent_at': msg_now,
                    'created_at': msg_now,
                }).execute()

                supabase.table('conversations').update({
                    'last_message_at': msg_now, 'updated_at': msg_now
                }).eq('id', conv['id']).execute()

                logger.info(f"Auto-reminder sent to conversation {conv['id']} (phone: {phone}, wa_sent: {wa_sent})")

            except Exception as e:
                logger.error(f"Error processing conversation {conv['id']} for reminder: {e}")

    except Exception as e:
        logger.error(f"Auto-reminder task error: {e}")
