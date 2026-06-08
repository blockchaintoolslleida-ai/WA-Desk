"""
WhatsApp Webhook Router - Multi-case aware message handling
"""
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import PlainTextResponse
import logging
import os
import httpx
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
import uuid
from database import get_supabase_admin
from config import WHATSAPP_VERIFY_TOKEN
from services.whatsapp import parse_webhook_payload, mark_message_as_read, normalize_phone
from services.media import process_incoming_media
from services.secrets_manager import decrypt_value

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

processed_messages = set()


@router.get("/webhook")
@router.get("/webhook/")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified OK")
        return PlainTextResponse(content=hub_challenge, status_code=200)
    # If no hub params, show diagnostic info
    if not hub_mode:
        return {
            "status": "webhook_active",
            "callback_url": os.environ.get('BASE_URL', '') + "/api/whatsapp/webhook",
            "verify_token": WHATSAPP_VERIFY_TOKEN,
            "phone_number_id": os.environ.get('WHATSAPP_PHONE_NUMBER_ID', 'NOT SET'),
            "has_access_token": bool(os.environ.get('WHATSAPP_ACCESS_TOKEN')),
            "hint": "Configure this callback_url and verify_token in Meta Developer Portal > WhatsApp > Configuration"
        }
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
@router.post("/webhook/")
async def receive_webhook(request: Request):
    try:
        payload = await request.json()
        logger.warning(f">>> WEBHOOK RECEIVED: {str(payload)[:500]}")

        message = parse_webhook_payload(payload)
        if not message:
            logger.warning(">>> WEBHOOK: No message parsed (status update or other)")
            return {"status": "ignored"}

        if message.message_id in processed_messages:
            return {"status": "duplicate"}
        processed_messages.add(message.message_id)
        if len(processed_messages) > 10000:
            processed_messages.clear()

        # Extract phone_number_id from metadata to identify tenant
        recv_phone_id = None
        try:
            recv_phone_id = payload['entry'][0]['changes'][0]['value']['metadata']['phone_number_id']
        except (KeyError, IndexError):
            pass

        await process_inbound_message(message, recv_phone_id)
        await mark_message_as_read(message.message_id)
        return {"status": "processed"}

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}


async def process_inbound_message(message, recv_phone_id=None, tenant_id=None):
    """Process inbound WhatsApp message with multi-case and multi-tenant logic.
    tenant_id can be passed explicitly (OpenWA) or resolved from recv_phone_id (Meta).
    """
    supabase = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    # Resolve tenant from the receiving phone_number_id or explicit tenant_id
    resolved_tenant_id = tenant_id
    if not resolved_tenant_id and recv_phone_id:
        try:
            acc_res = supabase.table('whatsapp_accounts').select('tenant_id').eq(
                'phone_number_id', recv_phone_id).limit(1).execute()
            if acc_res.data:
                resolved_tenant_id = acc_res.data[0].get('tenant_id')
                logger.info(f"Webhook from tenant: {resolved_tenant_id}")
        except Exception:
            pass

    try:
        phone = normalize_phone(message.phone)

        # Find or create contact — try multiple phone formats (normalized, +prefixed, original)
        try:
            # Try with + prefix first (common format from WhatsApp)
            contact_res = supabase.table('contacts').select('*').eq('phone', '+' + phone).execute()
            if not contact_res.data:
                # Try normalized (digits only)
                contact_res = supabase.table('contacts').select('*').eq('phone', phone).execute()
            if not contact_res.data:
                # Try original phone as-is from webhook
                contact_res = supabase.table('contacts').select('*').eq('phone', message.phone).execute()
        except Exception as col_err:
            logger.error(f"Error querying contacts: {col_err}")
            contact_res = type('R', (), {'data': []})()

        if contact_res.data:
            contact = contact_res.data[0]
            # Normalize phone in DB if it has + prefix (migrate to clean format)
            stored_phone = contact.get('phone', '')
            if stored_phone.startswith('+') or stored_phone != phone:
                try:
                    supabase.table('contacts').update({'phone': phone, 'updated_at': now}).eq('id', contact['id']).execute()
                    contact['phone'] = phone
                except Exception:
                    pass
            # Update name if we got a profile name from WhatsApp and current is generic
            if message.contact_name and contact.get('name', '').startswith('Contacte '):
                try:
                    supabase.table('contacts').update({'name': message.contact_name, 'updated_at': now}).eq('id', contact['id']).execute()
                    contact['name'] = message.contact_name
                except Exception:
                    pass
        else:
            contact = {
                'id': str(uuid.uuid4()),
                'name': message.contact_name or f"Contacte {phone[-4:]}",
                'phone': phone,
                'tenant_id': resolved_tenant_id,
                'created_at': now,
                'updated_at': now
            }
            supabase.table('contacts').insert(contact).execute()

        contact_id = contact['id']

        # Find active conversation or create new
        conv_res = supabase.table('conversations').select('*').eq(
            'contact_id', contact_id
        ).eq('is_active', True).order('created_at', desc=True).limit(1).execute()

        if conv_res.data:
            conversation = conv_res.data[0]
            conversation_id = conversation['id']

            # Update conversation
            supabase.table('conversations').update({
                'last_message_at': now,
                'updated_at': now,
                'unread_count': conversation.get('unread_count', 0) + 1
            }).eq('id', conversation_id).execute()
        else:
            # Create new conversation (no status, no case)
            conversation_id = str(uuid.uuid4())
            conv_data = {
                'id': conversation_id,
                'contact_id': contact_id,
                'status': None,
                'last_message_at': now,
                'unread_count': 1,
                'is_active': True,
                'tenant_id': resolved_tenant_id,
                'created_at': now,
                'updated_at': now
            }
            supabase.table('conversations').insert(conv_data).execute()

        # Determine if message should auto-link to a case
        active_cases = supabase.table('cases').select('id').eq(
            'conversation_id', conversation_id
        ).eq('is_active', True).execute()
        active_case_list = active_cases.data or []

        case_id = None
        needs_classification = False

        if len(active_case_list) == 1:
            # Auto-assign to the single active case
            case_id = active_case_list[0]['id']
            supabase.table('cases').update({
                'last_activity_at': now, 'updated_at': now
            }).eq('id', case_id).execute()
        elif len(active_case_list) > 1:
            # Multiple cases: needs classification
            needs_classification = True
        else:
            # No cases: message pending classification
            needs_classification = True

        # Insert message
        # If media, download from WhatsApp and store locally
        stored_media_url = message.media_url
        if message.media_type and message.media_url:
            # For OpenWA: media is already a local URL (downloaded by _download_openwa_media)
            # For Meta: media_url is a WhatsApp media ID, needs download
            if message.media_url.startswith('http'):
                stored_media_url = message.media_url  # Already a local URL
            else:
                public_url = await process_incoming_media(message.media_url)
                if public_url:
                    stored_media_url = public_url

        msg_data = {
            'id': str(uuid.uuid4()),
            'conversation_id': conversation_id,
            'case_id': case_id,
            'direction': 'incoming',
            'message_type': message.media_type or 'text',
            'body': message.body,
            'media_url': stored_media_url,
            'whatsapp_message_id': message.message_id,
            'needs_classification': needs_classification,
            'sent_at': now,
            'created_at': now
        }
        supabase.table('messages').insert(msg_data).execute()

        logger.info(f"Inbound processed: conv={conversation_id}, case={case_id}, needs_class={needs_classification}")

    except Exception as e:
        logger.error(f"Error processing inbound: {e}")


@router.get("/status")
async def whatsapp_status():
    from config import WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID
    configured = bool(
        WHATSAPP_ACCESS_TOKEN and not WHATSAPP_ACCESS_TOKEN.startswith('PLACEHOLDER')
        and WHATSAPP_PHONE_NUMBER_ID and not WHATSAPP_PHONE_NUMBER_ID.startswith('PLACEHOLDER')
    )
    return {
        "configured": configured,
        "phone_number_id": WHATSAPP_PHONE_NUMBER_ID[:6] + "..." if WHATSAPP_PHONE_NUMBER_ID else None,
        "webhook_url": "/api/whatsapp/webhook"
    }


def _get_openwa_creds_for_session(session_id: str) -> dict:
    """Get OpenWA credentials (server_url, api_key, session_id) for a session."""
    try:
        sb = get_supabase_admin()
        acc = sb.table('whatsapp_accounts').select(
            'id, openwa_server_url, openwa_session_id'
        ).eq('openwa_session_id', session_id).eq('connection_type', 'openwa').limit(1).execute()
        if not acc.data:
            return None

        server_url = acc.data[0].get('openwa_server_url', '')
        acc_id = acc.data[0].get('id', '')

        secrets = sb.table('whatsapp_secrets').select('encrypted_openwa_api_key').eq(
            'whatsapp_account_id', acc_id).limit(1).execute()
        if not secrets.data or not secrets.data[0].get('encrypted_openwa_api_key'):
            return None

        api_key = decrypt_value(secrets.data[0]['encrypted_openwa_api_key'])
        if not api_key:
            return None

        return {
            'server_url': server_url,
            'api_key': api_key,
            'session_id': session_id,
        }
    except Exception as e:
        logger.warning(f"Failed to get OpenWA creds for session {session_id}: {e}")
        return None


# ── OpenWA Media Download ─────────────────────────────────────

async def _download_openwa_media(server_url: str, api_key: str, session_id: str,
                                  msg_id: str, media_type: str) -> Optional[str]:
    """Download media from OpenWA and store locally. Returns local URL or None."""
    import uuid as _uuid
    try:
        # Try OpenWA media endpoint
        url = f"{server_url.rstrip('/')}/api/sessions/{session_id}/messages/{msg_id}/media"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers={"X-API-Key": api_key})

        if resp.status_code != 200:
            # Fallback: try to get media via base64 from message data endpoint
            # Not all OpenWA versions support this — just return None
            return None

        content_type = resp.headers.get('content-type', 'application/octet-stream')
        ext_map = {
            'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
            'audio/ogg': '.ogg', 'audio/mp4': '.m4a', 'audio/mpeg': '.mp3',
            'video/mp4': '.mp4', 'application/pdf': '.pdf',
        }
        ext = ext_map.get(content_type, '.bin')

        # Store in local media directory
        media_dir = Path(__file__).parent.parent / "media_files" / "media" / "incoming"
        media_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{_uuid.uuid4().hex}{ext}"
        filepath = media_dir / filename
        filepath.write_bytes(resp.content)

        base_url = os.environ.get('BASE_URL', 'http://localhost:8000')
        return f"{base_url}/api/media/files/incoming/{filename}"

    except Exception as e:
        logger.warning(f"OpenWA media download failed (non-fatal): {e}")
        return None


# ── OpenWA LID Resolver ────────────────────────────────────────

async def _resolve_openwa_lid(session_id: str, lid: str) -> dict:
    """Try to resolve an anonymized LID to a real phone number via OpenWA contacts API.

    Calls: GET /api/sessions/{sessionId}/contacts/{lid}@lid
    Returns: {"phone": "34694293833", "name": "Juan Jose Ruiz Fernandez"} or None
    """
    try:
        # Get OpenWA credentials
        sb = get_supabase_admin()
        acc = sb.table('whatsapp_accounts').select(
            'openwa_server_url, openwa_session_id'
        ).eq('openwa_session_id', session_id).eq('connection_type', 'openwa').limit(1).execute()
        if not acc.data:
            return None

        server_url = acc.data[0].get('openwa_server_url', '')
        acc_id = acc.data[0].get('openwa_session_id', '')

        # Get API key
        secrets = sb.table('whatsapp_secrets').select('encrypted_openwa_api_key').eq(
            'whatsapp_account_id', acc_id).limit(1).execute()
        if not secrets.data:
            # Try by account id
            accounts = sb.table('whatsapp_accounts').select('id').eq('openwa_session_id', session_id).limit(1).execute()
            if accounts.data:
                secrets = sb.table('whatsapp_secrets').select('encrypted_openwa_api_key').eq(
                    'whatsapp_account_id', accounts.data[0]['id']).limit(1).execute()

        if not secrets.data or not secrets.data[0].get('encrypted_openwa_api_key'):
            return None

        api_key = decrypt_value(secrets.data[0]['encrypted_openwa_api_key'])
        if not api_key:
            return None

        # Call OpenWA to resolve LID
        import httpx
        url = f"{server_url.rstrip('/')}/api/sessions/{session_id}/contacts/{lid}@lid"
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, headers={"X-API-Key": api_key})

        if resp.status_code != 200:
            logger.warning(f"OpenWA LID resolution failed: {resp.status_code} — {resp.text[:200]}")
            return None

        data = resp.json()
        contact_id = data.get('id', '')  # e.g., "34694293833@c.us"

        if '@c.us' not in contact_id:
            return None

        phone = normalize_phone(contact_id.replace('@c.us', ''))
        name = data.get('name') or data.get('pushName') or ''

        if phone:
            logger.info(f"LID {lid} resolved to phone={phone} name={name}")
            return {"phone": phone, "name": name}

        return None

    except Exception as e:
        logger.warning(f"OpenWA LID resolution error (non-fatal): {e}")
        return None


# ── OpenWA Webhook ─────────────────────────────────────────────

@router.post("/webhook/openwa")
async def receive_openwa_webhook(request: Request):
    """Receive incoming messages from an OpenWA Gateway webhook.

    OpenWA webhook format:
    {
      "event": "message.received",
      "sessionId": "sess_abc123",
      "data": {
        "id": {"_serialized": "msg_xyz"},
        "body": "Hello",
        "from": "34612345678@c.us",
        "type": "chat",
        "hasMedia": false,
        "timestamp": 1704067200,
      },
      "signature": "sha256=..."
    }
    """
    try:
        payload = await request.json()
        session_id = payload.get('sessionId', '')
        logger.info(f"OpenWA webhook received: event={payload.get('event')}, session={session_id}")
        data = payload.get('data', {})

        # Only handle message.received events
        if payload.get('event') != 'message.received':
            return {"status": "ignored", "reason": f"event={payload.get('event')}"}

        if not data:
            return {"status": "ignored", "reason": "no data"}

        # Extract message fields from OpenWA format
        raw_id = data.get('id', '')
        if isinstance(raw_id, dict):
            msg_id = raw_id.get('_serialized', '') or str(raw_id)
        else:
            msg_id = str(raw_id) if raw_id else ''
        body = data.get('body', '')
        timestamp = str(data.get('timestamp', ''))

        # Resolve sender identity: WhatsApp privacy mode hides real phone behind @lid
        # @c.us = phone-based ID, @lid = anonymized ID (privacy mode)
        # Priority: chatId if @c.us → from if @c.us → chatId if @lid (anonymized ID as contact key)
        chat_id = data.get('chatId', '')
        from_id = data.get('from', '')
        to_id = data.get('to', '')

        phone = ''
        if '@c.us' in chat_id:
            candidate = normalize_phone(chat_id.replace('@c.us', ''))
            to_phone = normalize_phone(to_id.replace('@c.us', '')) if '@c.us' in to_id else ''
            if candidate != to_phone:
                phone = candidate  # chatId is real phone (not the business)

        if not phone and '@c.us' in from_id:
            phone = normalize_phone(from_id.replace('@c.us', ''))

        if not phone and '@lid' in chat_id:
            # Try to resolve LID to real phone via OpenWA contacts API
            lid_raw = normalize_phone(chat_id.replace('@lid', ''))
            resolved = await _resolve_openwa_lid(session_id, lid_raw)
            if resolved:
                phone = resolved['phone']
                contact_name = resolved['name']
                logger.info(f"OpenWA LID resolved: {lid_raw} → phone={phone} name={contact_name}")
            else:
                # Fallback: use LID as unique contact key
                phone = 'lid_' + lid_raw
                logger.info(f"OpenWA LID NOT resolved, using key: {phone}")

        if not phone:
            logger.error(f"OpenWA: could not resolve identity — chatId={chat_id} from={from_id}")
            return {"status": "ignored", "reason": "cannot resolve identity"}

        logger.info(f"OpenWA resolved identity: phone={phone} (from chatId={chat_id} from={from_id})")
        msg_type = data.get('type', 'chat')
        has_media = data.get('hasMedia', False)
        media_url = None
        media_type = None
        contact_name = None

        # Media types from whatsapp-web.js: image, video, audio, ptt (voice note), document, sticker
        MEDIA_TYPES = {'image', 'video', 'audio', 'ptt', 'document', 'sticker'}
        is_media = has_media or msg_type in MEDIA_TYPES

        if is_media:
            media_type = msg_type if msg_type in MEDIA_TYPES else 'document'
            # Normalize ptt → audio for display
            if media_type == 'ptt':
                media_type = 'audio'

            # Get OpenWA credentials for media download
            ow_creds = _get_openwa_creds_for_session(session_id)
            if ow_creds:
                media_url = await _download_openwa_media(
                    ow_creds['server_url'], ow_creds['api_key'],
                    ow_creds['session_id'], msg_id, media_type
                )

            # Get caption or set placeholder
            caption = data.get('caption', '') or data.get('body', '')
            if caption and caption != body:
                body = caption
            if not body:
                type_labels = {'image': '[Imatge]', 'video': '[Vídeo]', 'audio': '[Àudio]', 'document': '[Document]', 'sticker': '[Sticker]'}
                body = type_labels.get(media_type, f'[{media_type.upper()}]')

        # Deduplicate
        dedup_key = f"openwa_{msg_id}"
        if dedup_key in processed_messages:
            return {"status": "duplicate", "message_id": msg_id}
        processed_messages.add(dedup_key)
        if len(processed_messages) > 10000:
            processed_messages.clear()

        # Resolve tenant by OpenWA session ID
        sb = get_supabase_admin()
        tenant_id = None
        if session_id:
            acc_res = sb.table('whatsapp_accounts').select('tenant_id, id').eq(
                'openwa_session_id', session_id
            ).eq('connection_type', 'openwa').limit(1).execute()
            if acc_res.data:
                tenant_id = acc_res.data[0].get('tenant_id')

        # Build inbound message and process
        from models import WhatsAppInboundMessage
        message = WhatsAppInboundMessage(
            phone=phone,
            message_id=msg_id,
            body=body,
            timestamp=timestamp,
            media_url=media_url,
            media_type=media_type,
            contact_name=contact_name,
        )

        # Use existing process_inbound_message with the resolved tenant context
        await process_inbound_message(message, recv_phone_id=None, tenant_id=tenant_id)

        return {"status": "processed", "message_id": msg_id}

    except Exception as e:
        logger.error(f"OpenWA webhook error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing OpenWA webhook: {str(e)[:200]}")
