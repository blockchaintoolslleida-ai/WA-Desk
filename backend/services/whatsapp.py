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
            contact_name=contact_name,
            reply_to_wamid=(message.get('context') or {}).get('id'),
        )
        
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        return None


async def send_whatsapp_message(message: WhatsAppOutboundMessage, reply_to_wamid: str = None, phone_number_id: str = None, tenant_id: str = None) -> dict:
    """Send a WhatsApp message via the Cloud API (Meta) or OpenWA Gateway.

    Credentials resolution:
      - If tenant_id is provided → use tenant's stored config (Meta or OpenWA)
      - phone_number_id parameter overrides Meta phone_id when provided
      - Auto-detects connection_type and routes accordingly

    Returns: {"ok": bool, "error": str or None, "wamid": str or None}
    """
    from services.tenant_credentials import get_tenant_connection_config
    config = get_tenant_connection_config(tenant_id)

    connection_type = config.get("connection_type", "meta")

    if connection_type == "openwa":
        server_url = config.get("openwa_server_url", "")
        api_key = config.get("openwa_api_key", "")
        session_id = config.get("openwa_session_id", "")

        if not server_url or not api_key or not session_id:
            return {"ok": False, "error": "OpenWA no configurat", "wamid": None}

        # Build correct chatId format: phone@c.us or lid_xxx → xxx@lid
        phone = message.phone
        if phone.startswith('lid_'):
            chat_id = phone[4:] + '@lid'
        else:
            chat_id = normalize_phone(phone) + '@c.us'
        return await _send_openwa_text(server_url, api_key, session_id, chat_id, message.body,
                                        quoted_message_id=reply_to_wamid)

    # Meta path (default)
    token = config.get("access_token")
    tenant_phone_id = config.get("phone_number_id")

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
    """Mark a WhatsApp message as read. No-op for OpenWA."""
    from services.tenant_credentials import get_tenant_connection_config
    config = get_tenant_connection_config(tenant_id)

    if config.get("connection_type") == "openwa":
        return True  # OpenWA doesn't have a read-receipt endpoint

    token = config.get("access_token")
    phone_id = config.get("phone_number_id")
    if not token or token.startswith('PLACEHOLDER') or not phone_id:
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
    """Upload media to WhatsApp and return the media ID.
    For OpenWA, media is sent directly (no separate upload) — returns '__openwa_direct__' sentinel.
    """
    from services.tenant_credentials import get_tenant_connection_config
    config = get_tenant_connection_config(tenant_id)

    if config.get("connection_type") == "openwa":
        return "__openwa_direct__"

    token = config.get("access_token")
    phone_id = config.get("phone_number_id")
    if not token or token.startswith('PLACEHOLDER'):
        logger.warning("WhatsApp credentials not configured")
        return None

    url = f"{WHATSAPP_API_URL}/{phone_id}/media"
    headers = {"Authorization": f"Bearer {token}"}

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
    """Send a WhatsApp template message (for messages outside 24h window).
    For OpenWA, falls back to sending as a regular text message (no 24h restriction).
    """
    from services.tenant_credentials import get_tenant_connection_config
    config = get_tenant_connection_config(tenant_id)

    if config.get("connection_type") == "openwa":
        server_url = config.get("openwa_server_url", "")
        api_key = config.get("openwa_api_key", "")
        session_id = config.get("openwa_session_id", "")
        if not server_url or not api_key or not session_id:
            return False
        if phone.startswith('lid_'):
            chat_id = phone[4:] + '@lid'
        else:
            chat_id = normalize_phone(phone) + '@c.us'
        # For OpenWA, just send the template name as a regular message
        result = await _send_openwa_text(server_url, api_key, session_id, chat_id,
                                         f"[Template: {template_name}]")
        return result.get("ok", False)

    token = config.get("access_token")
    phone_id = config.get("phone_number_id")
    if not token or token.startswith('PLACEHOLDER'):
        logger.warning("WhatsApp credentials not configured - template not sent")
        return False

    url = f"{WHATSAPP_API_URL}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    wa_lang_map = {"ca": "ca", "es": "es", "en": "en_US"}
    wa_lang = wa_lang_map.get(language_code, "ca")
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {"name": template_name, "language": {"code": wa_lang}},
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
    """Send a document via WhatsApp. For OpenWA, media is sent directly."""
    from services.tenant_credentials import get_tenant_connection_config
    config = get_tenant_connection_config(tenant_id)

    if config.get("connection_type") == "openwa":
        # Media sent directly via send_openwa_media — document sending requires file_bytes
        # which we don't have here. Fall back to text notification.
        server_url = config.get("openwa_server_url", "")
        api_key = config.get("openwa_api_key", "")
        session_id = config.get("openwa_session_id", "")
        if not server_url or not api_key or not session_id:
            return False
        if phone.startswith('lid_'):
            chat_id = phone[4:] + '@lid'
        else:
            chat_id = normalize_phone(phone) + '@c.us'
        text = f"[Document: {filename}] {caption}".strip()
        result = await _send_openwa_text(server_url, api_key, session_id, chat_id, text)
        return result.get("ok", False)

    token = config.get("access_token")
    phone_id = config.get("phone_number_id")
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
        "document": {"id": media_id, "filename": filename, "caption": caption}
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


# ═══════════════════════════════════════════════════════════════════
# OpenWA Gateway Helpers
# ═══════════════════════════════════════════════════════════════════

async def _send_openwa_text(server_url: str, api_key: str, session_id: str,
                            chat_id: str, text: str,
                            quoted_message_id: str = None) -> dict:
    """Send a text message via OpenWA REST API.

    When quoted_message_id is provided, the /reply endpoint is used so WhatsApp
    shows the message as a quoted reply. Falls back to /send-text if /reply fails.

    Returns: {"ok": bool, "error": str or None, "wamid": str or None}
    """
    base = server_url.rstrip('/')
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    # If replying to a specific message, try the /reply endpoint first
    if quoted_message_id:
        reply_url = f"{base}/api/sessions/{session_id}/messages/reply"
        reply_payload = {"chatId": chat_id, "text": text, "quotedMessageId": quoted_message_id}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(reply_url, json=reply_payload, headers=headers)
            if resp.status_code in (200, 201):
                data = resp.json()
                msg_id = data.get("messageId") or data.get("id") or "openwa_reply_" + chat_id
                logger.info(f"OpenWA reply sent to {chat_id} (quoted {quoted_message_id})")
                return {"ok": True, "error": None, "wamid": msg_id}
            logger.warning(f"OpenWA /reply failed ({resp.status_code}), falling back to send-text")
        except Exception as e:
            logger.warning(f"OpenWA /reply error: {e}, falling back to send-text")

    # Fallback: plain send-text (no quoting)
    url = f"{base}/api/sessions/{session_id}/messages/send-text"
    payload = {"chatId": chat_id, "text": text}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code in (200, 201):
                data = response.json()
                msg_id = data.get("messageId") or data.get("id") or "openwa_" + chat_id
                logger.info(f"OpenWA message sent to {chat_id}")
                return {"ok": True, "error": None, "wamid": msg_id}

            err_msg = response.text or f"HTTP {response.status_code}"
            logger.error(f"OpenWA send error: {response.status_code} - {err_msg}")
            return {"ok": False, "error": err_msg, "wamid": None}

    except httpx.ConnectError:
        logger.error(f"OpenWA server unreachable: {server_url}")
        return {"ok": False, "error": "OpenWA server unreachable", "wamid": None}
    except Exception as e:
        logger.error(f"OpenWA send failed: {e}")
        return {"ok": False, "error": str(e), "wamid": None}


async def send_openwa_media(server_url: str, api_key: str, session_id: str,
                            chat_id: str, media_type: str, file_bytes: bytes,
                            filename: str, mime_type: str, caption: str = "") -> dict:
    """Send media (image/document/video) via OpenWA REST API.
    OpenWA sends media directly in one multipart request (no separate upload step).

    Returns: {"ok": bool, "error": str or None, "wamid": str or None}
    """
    # Map media_type to OpenWA endpoint
    endpoint_map = {
        "image": "send-image",
        "document": "send-document",
        "video": "send-video",
        "audio": "send-audio",
    }
    action = endpoint_map.get(media_type, "send-document")
    url = f"{server_url.rstrip('/')}/api/sessions/{session_id}/messages/{action}"

    headers = {"X-API-Key": api_key}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            files = {"file": (filename, file_bytes, mime_type)}
            data = {"chatId": chat_id}
            if caption:
                data["caption"] = caption

            response = await client.post(url, data=data, files=files, headers=headers)

            if response.status_code in (200, 201):
                resp_data = response.json()
                msg_id = resp_data.get("messageId") or resp_data.get("id") or "openwa_media"
                logger.info(f"OpenWA media sent to {chat_id}: {filename}")
                return {"ok": True, "error": None, "wamid": msg_id}

            err_msg = response.text or f"HTTP {response.status_code}"
            logger.error(f"OpenWA media send error: {response.status_code} - {err_msg}")
            return {"ok": False, "error": err_msg, "wamid": None}

    except httpx.ConnectError:
        return {"ok": False, "error": "OpenWA server unreachable", "wamid": None}
    except Exception as e:
        logger.error(f"OpenWA media send failed: {e}")
        return {"ok": False, "error": str(e), "wamid": None}


async def validate_openwa_connection(server_url: str, api_key: str, session_id: str) -> dict:
    """Test OpenWA connection by fetching session info.

    Returns: {"ok": bool, "status": str, "error": str or None}
    """
    url = f"{server_url.rstrip('/')}/api/sessions/{session_id}"
    headers = {"X-API-Key": api_key}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                state = data.get("state") or data.get("status") or "CONNECTED"
                return {"ok": True, "status": state, "error": None}
            elif response.status_code == 404:
                return {"ok": False, "status": "not_found", "error": f"Session '{session_id}' no trobada"}
            else:
                return {"ok": False, "status": "error", "error": f"HTTP {response.status_code}: {response.text[:200]}"}

    except httpx.ConnectError:
        return {"ok": False, "status": "error", "error": "No s'ha pogut connectar al servidor OpenWA"}
    except Exception as e:
        return {"ok": False, "status": "error", "error": str(e)}
