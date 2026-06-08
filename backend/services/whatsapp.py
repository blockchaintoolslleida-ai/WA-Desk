"""
WhatsApp Business Cloud API Integration Service
Handles webhook verification, inbound messages, and outbound responses
"""
import httpx
import logging
import hashlib
import hmac
from typing import Optional, Dict, Any
from config import (
    WHATSAPP_VERIFY_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_API_URL
)
from models import WhatsAppInboundMessage, WhatsAppOutboundMessage

logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    """Normalize phone number to E.164 format"""
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    # Ensure it starts with country code
    if digits.startswith('34'):  # Spain
        return digits
    elif len(digits) == 9:  # Spanish local number
        return '34' + digits
    
    return digits


def verify_webhook_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    """Verify the webhook signature from Meta"""
    if not signature or not app_secret:
        return False
    
    try:
        expected_signature = hmac.new(
            app_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Signature format: sha256=xxxxx
        if signature.startswith('sha256='):
            signature = signature[7:]
        
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False


def parse_webhook_payload(payload: Dict[str, Any]) -> Optional[WhatsAppInboundMessage]:
    """Parse incoming WhatsApp webhook payload"""
    try:
        entry = payload.get('entry', [])
        if not entry:
            return None
        
        changes = entry[0].get('changes', [])
        if not changes:
            return None
        
        value = changes[0].get('value', {})
        messages = value.get('messages', [])
        
        if not messages:
            return None
        
        message = messages[0]
        contacts = value.get('contacts', [{}])
        contact_name = None
        if contacts and contacts[0].get('profile'):
            contact_name = contacts[0]['profile'].get('name')
        
        # Extract message content based on type
        msg_type = message.get('type', 'text')
        body = ""
        media_url = None
        media_type = None
        
        if msg_type == 'text':
            body = message.get('text', {}).get('body', '')
        elif msg_type in ['image', 'document', 'audio', 'video']:
            media_data = message.get(msg_type, {})
            media_url = media_data.get('id')  # WhatsApp media ID
            media_type = msg_type
            body = media_data.get('caption', '') or ''
            if not body:
                mime = media_data.get('mime_type', '')
                filename = media_data.get('filename', '')
                body = filename if filename else f'[{msg_type.upper()}] {mime}'
        
        return WhatsAppInboundMessage(
            phone=normalize_phone(message.get('from', '')),
            message_id=message.get('id', ''),
            body=body,
            timestamp=message.get('timestamp', ''),
            media_url=media_url,
            media_type=media_type,
            contact_name=contact_name
        )
        
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        return None


async def send_whatsapp_message(message: WhatsAppOutboundMessage, reply_to_wamid: str = None, phone_number_id: str = None, tenant_id: str = None) -> dict:
    """Send a WhatsApp message via the Cloud API, optionally as a reply (quoted).

    Credentials resolution:
      - If tenant_id is provided → use tenant's stored token + phone_number_id (fallback to .env)
      - phone_number_id parameter overrides everything when provided

    Returns: {"ok": bool, "error": str or None, "wamid": str or None}
    """
    # Resolve credentials per-tenant
    from services.tenant_credentials import get_tenant_credentials
    token, tenant_phone_id, _ = get_tenant_credentials(tenant_id)

    if not token or token.startswith('PLACEHOLDER'):
        logger.warning("WhatsApp credentials not configured - message not sent")
        return {"ok": False, "error": "WhatsApp no configurat", "wamid": None}

    sender_phone_id = phone_number_id or tenant_phone_id
    if not sender_phone_id:
        return {"ok": False, "error": "Phone Number ID no configurat", "wamid": None}

    url = f"{WHATSAPP_API_URL}/{sender_phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": message.phone,
        "type": "text",
        "text": {
            "preview_url": message.preview_url,
            "body": message.body
        }
    }

    # Add context for quoted reply (WhatsApp will show the original message)
    if reply_to_wamid:
        payload["context"] = {"message_id": reply_to_wamid}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                logger.info(f"WhatsApp message sent to {message.phone}" + (f" (reply to {reply_to_wamid})" if reply_to_wamid else ""))
                data = response.json()
                wamid = (data.get('messages') or [{}])[0].get('id')
                return {"ok": True, "error": None, "wamid": wamid}

            try:
                err_data = response.json().get('error', {})
                err_msg = err_data.get('error_user_msg') or err_data.get('message') or response.text
            except Exception:
                err_msg = response.text or f"HTTP {response.status_code}"
            logger.error(f"WhatsApp API error: {response.status_code} - {err_msg}")
            return {"ok": False, "error": err_msg, "wamid": None}

    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        return {"ok": False, "error": str(e), "wamid": None}


async def send_portal_link(phone: str, ticket_id: str, portal_url: str, language: str = "ca") -> bool:
    """Send the secure portal link to the customer"""
    messages = {
        "ca": f"Hem rebut la teva sol·licitud. Accedeix al teu ticket aquí: {portal_url}/ticket/{ticket_id}",
        "es": f"Hemos recibido tu solicitud. Accede a tu ticket aquí: {portal_url}/ticket/{ticket_id}",
        "en": f"We've received your request. Access your ticket here: {portal_url}/ticket/{ticket_id}"
    }
    
    body = messages.get(language, messages["ca"])
    
    return await send_whatsapp_message(WhatsAppOutboundMessage(
        phone=phone,
        body=body,
        preview_url=True
    ))


async def mark_message_as_read(message_id: str, tenant_id: str = None) -> bool:
    """Mark a WhatsApp message as read"""
    from services.tenant_credentials import get_tenant_credentials
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
        "status": "read",
        "message_id": message_id
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to mark message as read: {e}")
        return False


async def upload_media_to_whatsapp(file_bytes: bytes, mime_type: str, filename: str, tenant_id: str = None) -> Optional[str]:
    """Upload media to WhatsApp and return the media ID"""
    from services.tenant_credentials import get_tenant_credentials
    token, phone_id, _ = get_tenant_credentials(tenant_id)
    if not token or token.startswith('PLACEHOLDER'):
        logger.warning("WhatsApp credentials not configured")
        return None

    url = f"{WHATSAPP_API_URL}/{phone_id}/media"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            files = {
                'file': (filename, file_bytes, mime_type),
                'messaging_product': (None, 'whatsapp'),
                'type': (None, mime_type),
            }
            response = await client.post(url, headers=headers, files=files)

            if response.status_code == 200:
                media_id = response.json().get('id')
                logger.info(f"Media uploaded: {media_id}")
                return media_id
            else:
                logger.error(f"Media upload failed: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Failed to upload media: {e}")
        return None


async def send_whatsapp_template(phone: str, template_name: str, language_code: str = "ca", components: list = None, tenant_id: str = None) -> bool:
    """Send a WhatsApp template message (for messages outside 24h window)"""
    from services.tenant_credentials import get_tenant_credentials
    token, phone_id, _ = get_tenant_credentials(tenant_id)
    if not token or token.startswith('PLACEHOLDER'):
        logger.warning("WhatsApp credentials not configured - template not sent")
        return False

    url = f"{WHATSAPP_API_URL}/{phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Map our language codes to WhatsApp template language codes
    wa_lang_map = {"ca": "ca", "es": "es", "en": "en_US"}
    wa_lang = wa_lang_map.get(language_code, "ca")

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": wa_lang},
        }
    }

    if components:
        payload["template"]["components"] = components

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                logger.info(f"WhatsApp template '{template_name}' sent to {phone}")
                return True
            else:
                logger.warning(f"WhatsApp template API error: {response.status_code} - {response.text}")
                return False

    except Exception as e:
        logger.error(f"Failed to send WhatsApp template: {e}")
        return False


async def send_whatsapp_document(phone: str, media_id: str, filename: str, caption: str = "", tenant_id: str = None) -> bool:
    """Send a document via WhatsApp using a previously uploaded media ID"""
    from services.tenant_credentials import get_tenant_credentials
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
        "to": phone,
        "type": "document",
        "document": {
            "id": media_id,
            "filename": filename,
            "caption": caption
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info(f"Document sent to {phone}: {filename}")
                return True
            else:
                logger.error(f"Document send failed: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Failed to send document: {e}")
        return False
