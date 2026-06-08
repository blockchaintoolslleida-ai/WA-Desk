"""
Media Router - File upload and send via WhatsApp
"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from typing import Optional
import logging
from datetime import datetime, timezone
import uuid
from database import get_supabase_admin
from services.media import upload_agent_file
from services.whatsapp import (
    send_whatsapp_message, send_whatsapp_document,
    upload_media_to_whatsapp, normalize_phone
)
from models import WhatsAppOutboundMessage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/media", tags=["Media"])


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


IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
AUDIO_TYPES = {'audio/ogg', 'audio/mpeg', 'audio/aac', 'audio/opus', 'audio/mp4'}
DOC_TYPES = {
    'application/pdf', 'text/plain',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/msword', 'application/vnd.ms-excel',
}
VIDEO_TYPES = {'video/mp4', 'video/3gpp'}


def classify_mime(mime: str) -> str:
    if mime in IMAGE_TYPES:
        return 'image'
    if mime in AUDIO_TYPES:
        return 'audio'
    if mime in VIDEO_TYPES:
        return 'video'
    return 'document'


@router.post("/send/{conversation_id}")
async def send_media(
    conversation_id: str,
    file: UploadFile = File(...),
    caption: str = Form(""),
    case_id: Optional[str] = Form(None),
    reply_to_id: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """Upload a file and send it via WhatsApp"""
    user = await get_user_from_token(authorization)
    supabase = get_supabase_admin()

    try:
        # Get conversation + contact
        conv_res = supabase.table('conversations').select(
            '*, contacts(phone, name)'
        ).eq('id', conversation_id).single().execute()
        if not conv_res.data:
            raise HTTPException(status_code=404, detail="Conversa no trobada")

        contact = conv_res.data.get('contacts', {})
        phone = contact.get('phone')
        if not phone:
            raise HTTPException(status_code=400, detail="Contacte sense telefon")

        # Read file
        file_bytes = await file.read()
        mime_type = file.content_type or 'application/octet-stream'
        filename = file.filename or 'file'
        msg_type = classify_mime(mime_type)

        # Upload to Supabase Storage for permanent URL
        public_url = upload_agent_file(file_bytes, mime_type, filename)
        if not public_url:
            raise HTTPException(status_code=500, detail="Error pujant fitxer")

        # Send via WhatsApp (tenant-scoped credentials)
        tenant_id = user.get('tenant_id')
        wa_sent = False
        if msg_type == 'image':
            wa_media_id = await upload_media_to_whatsapp(file_bytes, mime_type, filename, tenant_id=tenant_id)
            if wa_media_id:
                wa_sent = await send_whatsapp_image(phone, wa_media_id, caption, tenant_id=tenant_id)
        elif msg_type in ['document', 'audio', 'video']:
            wa_media_id = await upload_media_to_whatsapp(file_bytes, mime_type, filename, tenant_id=tenant_id)
            if wa_media_id:
                wa_sent = await send_whatsapp_document(
                    normalize_phone(phone), wa_media_id, filename, caption, tenant_id=tenant_id
                )
        else:
            wa_media_id = await upload_media_to_whatsapp(file_bytes, mime_type, filename, tenant_id=tenant_id)
            if wa_media_id:
                wa_sent = await send_whatsapp_document(
                    normalize_phone(phone), wa_media_id, filename, caption, tenant_id=tenant_id
                )

        # Auto-inherit case from reply
        actual_case_id = case_id
        if reply_to_id and not actual_case_id:
            replied = supabase.table('messages').select('case_id').eq('id', reply_to_id).single().execute()
            if replied.data and replied.data.get('case_id'):
                actual_case_id = replied.data['case_id']

        # If no case, auto-link if only 1 active case
        if not actual_case_id:
            cases_res = supabase.table('cases').select('id').eq(
                'conversation_id', conversation_id
            ).eq('is_active', True).execute()
            if cases_res.data and len(cases_res.data) == 1:
                actual_case_id = cases_res.data[0]['id']

        now = datetime.now(timezone.utc).isoformat()

        msg_data = {
            'id': str(uuid.uuid4()),
            'conversation_id': conversation_id,
            'case_id': actual_case_id,
            'direction': 'outgoing',
            'message_type': msg_type,
            'body': caption or filename,
            'media_url': public_url,
            'sender_agent_id': user['id'],
            'reply_to_id': reply_to_id,
            'needs_classification': False,
            'sent_at': now,
            'created_at': now,
        }
        supabase.table('messages').insert(msg_data).execute()

        supabase.table('conversations').update({
            'last_message_at': now, 'updated_at': now
        }).eq('id', conversation_id).execute()

        if actual_case_id:
            supabase.table('cases').update({
                'last_activity_at': now, 'updated_at': now
            }).eq('id', actual_case_id).execute()

        return {
            "id": msg_data['id'],
            "whatsapp_sent": wa_sent,
            "media_url": public_url,
            "message_type": msg_type,
            "case_id": actual_case_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send media error: {e}")
        raise HTTPException(status_code=500, detail="Error enviant fitxer")


async def send_whatsapp_image(phone: str, media_id: str, caption: str = "", tenant_id: str = None) -> bool:
    """Send an image via WhatsApp"""
    from config import WHATSAPP_API_URL
    from services.tenant_credentials import get_tenant_credentials
    import httpx

    token, phone_id, _ = get_tenant_credentials(tenant_id)
    if not token or token.startswith('PLACEHOLDER'):
        return False

    url = f"{WHATSAPP_API_URL}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": normalize_phone(phone),
        "type": "image",
        "image": {"id": media_id}
    }
    if caption:
        payload["image"]["caption"] = caption

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info(f"Image sent to {phone}")
                return True
            logger.error(f"Image send failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send image: {e}")
        return False
