"""
WhatsApp Webhook Router - Multi-case aware message handling
"""
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import PlainTextResponse
import logging
import os
from datetime import datetime, timezone
import uuid
from database import get_supabase_admin
from config import WHATSAPP_VERIFY_TOKEN
from services.whatsapp import parse_webhook_payload, mark_message_as_read, normalize_phone
from services.media import process_incoming_media

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


async def process_inbound_message(message, recv_phone_id=None):
    """Process inbound WhatsApp message with multi-case and multi-tenant logic"""
    supabase = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    # Resolve tenant from the receiving phone_number_id (for future use when migration is run)
    if recv_phone_id:
        try:
            acc_res = supabase.table('whatsapp_accounts').select('tenant_id').eq(
                'phone_number_id', recv_phone_id).limit(1).execute()
            if acc_res.data:
                logger.info(f"Webhook from tenant: {acc_res.data[0].get('tenant_id')}")
        except Exception:
            pass

    try:
        phone = normalize_phone(message.phone)

        # Find or create contact (graceful: works with or without tenant_id column)
        try:
            contact_res = supabase.table('contacts').select('*').eq('phone', phone).execute()
        except Exception as col_err:
            logger.error(f"Error querying contacts: {col_err}")
            contact_res = type('R', (), {'data': []})()

        if contact_res.data:
            contact = contact_res.data[0]
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
        # If media, download from WhatsApp and store in Supabase Storage
        stored_media_url = message.media_url
        if message.media_type and message.media_url:
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
