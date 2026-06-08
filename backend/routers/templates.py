"""
Templates Router - WhatsApp Message Templates Management
Uses whatsapp_business_management permission to list and manage templates
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from pydantic import BaseModel
import logging
import httpx
from database import get_supabase_admin
from config import WHATSAPP_API_URL
from services.tenant_credentials import get_tenant_credentials

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/templates", tags=["Templates"])


async def get_admin_user(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticat")
    token = authorization.replace("Bearer ", "")
    admin_client = get_supabase_admin()
    try:
        user_response = admin_client.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Token invalid")
        profile = admin_client.table('profiles').select('id, role, tenant_id').eq(
            'id', user_response.user.id).single().execute()
        if not profile.data or profile.data['role'] not in ('admin', 'super_admin'):
            raise HTTPException(status_code=403, detail="Accés denegat")
        return profile.data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Error d'autenticacio")


def _get_tenant_meta_creds(tenant_id: str):
    """Returns (token, phone_number_id, waba_id) for tenant; raises 400 if not Meta."""
    from services.tenant_credentials import get_tenant_connection_config
    config = get_tenant_connection_config(tenant_id)
    if config.get('connection_type') == 'openwa':
        raise HTTPException(
            status_code=400,
            detail="Les plantilles només estan disponibles amb WhatsApp Business API (Meta). "
                   "OpenWA no requereix plantilles per enviar missatges fora de la finestra 24h."
        )
    token = config.get('access_token')
    phone_id = config.get('phone_number_id')
    waba_id = config.get('whatsapp_business_account_id')
    if not waba_id:
        raise HTTPException(status_code=400, detail="No s'ha pogut obtenir el WABA ID. Configura'l al Setup Wizard.")
    if not token:
        raise HTTPException(status_code=400, detail="No s'ha configurat el Token de WhatsApp.")
    return token, phone_id, waba_id


@router.get("")
async def list_templates(authorization: Optional[str] = Header(None)):
    """List all message templates from Meta WhatsApp Business API"""
    user = await get_admin_user(authorization)
    token, _, waba_id = _get_tenant_meta_creds(user['tenant_id'])

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{WHATSAPP_API_URL}/{waba_id}/message_templates",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": 100}
            )

            if resp.status_code != 200:
                error = resp.json().get('error', {})
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=error.get('message', 'Error fetching templates')
                )

            data = resp.json()
            templates = data.get('data', [])

            result = []
            for t in templates:
                result.append({
                    'id': t.get('id'),
                    'name': t.get('name'),
                    'status': t.get('status'),
                    'category': t.get('category'),
                    'language': t.get('language'),
                    'components': t.get('components', []),
                })

            return {"templates": result, "total": len(result)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail="Error obtenint plantilles")


class SendTemplateRequest(BaseModel):
    template_name: str
    language_code: str
    to_phone: str
    variables: list = []


@router.post("/send")
async def send_template_to_number(req: SendTemplateRequest, authorization: Optional[str] = Header(None)):
    """Send a template message to a specific phone number (for testing)"""
    user = await get_admin_user(authorization)
    token, phone_id, _ = _get_tenant_meta_creds(user['tenant_id'])
    if not phone_id:
        raise HTTPException(status_code=400, detail="Phone Number ID no configurat")

    components = []
    if req.variables:
        params = [{"type": "text", "text": v} for v in req.variables]
        components.append({"type": "body", "parameters": params})

    payload = {
        "messaging_product": "whatsapp",
        "to": req.to_phone.replace("+", "").replace(" ", ""),
        "type": "template",
        "template": {
            "name": req.template_name,
            "language": {"code": req.language_code},
        }
    }
    if components:
        payload["template"]["components"] = components

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{WHATSAPP_API_URL}/{phone_id}/messages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )

            if resp.status_code in (200, 201):
                return {"ok": True, "response": resp.json()}
            else:
                error = resp.json().get('error', {})
                return {"ok": False, "error": error.get('message', 'Unknown error'), "code": resp.status_code}

    except Exception as e:
        logger.error(f"Error sending template: {e}")
        raise HTTPException(status_code=500, detail="Error enviant plantilla")


class CreateTemplateRequest(BaseModel):
    name: str
    category: str
    language: str
    body_text: str
    header_text: Optional[str] = None
    footer_text: Optional[str] = None


@router.post("")
async def create_template(req: CreateTemplateRequest, authorization: Optional[str] = Header(None)):
    """Create a new WhatsApp message template via Meta API."""
    user = await get_admin_user(authorization)
    token, _, waba_id = _get_tenant_meta_creds(user['tenant_id'])

    name = req.name.strip().lower().replace(' ', '_')
    if not name or not all(c.isalnum() or c == '_' for c in name):
        raise HTTPException(status_code=400, detail="Nom invalid. Usa nomes minuscules, numeros i guio baix.")

    components = []
    if req.header_text and req.header_text.strip():
        components.append({"type": "HEADER", "format": "TEXT", "text": req.header_text.strip()[:60]})
    components.append({"type": "BODY", "text": req.body_text.strip()[:1024]})
    if req.footer_text and req.footer_text.strip():
        components.append({"type": "FOOTER", "text": req.footer_text.strip()[:60]})

    payload = {
        "name": name,
        "category": req.category.upper(),
        "language": req.language,
        "components": components,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{WHATSAPP_API_URL}/{waba_id}/message_templates",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                return {
                    "ok": True,
                    "id": data.get('id'),
                    "status": data.get('status', 'PENDING'),
                    "category": data.get('category'),
                    "name": name,
                }

            error = resp.json().get('error', {})
            raise HTTPException(
                status_code=resp.status_code,
                detail=error.get('error_user_msg') or error.get('message') or 'Error creant plantilla'
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail="Error creant plantilla")


@router.delete("/{template_name}")
async def delete_template(template_name: str, authorization: Optional[str] = Header(None)):
    """Delete a WhatsApp message template by name via Meta API."""
    user = await get_admin_user(authorization)
    token, _, waba_id = _get_tenant_meta_creds(user['tenant_id'])

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(
                f"{WHATSAPP_API_URL}/{waba_id}/message_templates",
                headers={"Authorization": f"Bearer {token}"},
                params={"name": template_name},
            )

            if resp.status_code == 200:
                return {"ok": True, "deleted": template_name}

            error = resp.json().get('error', {})
            raise HTTPException(
                status_code=resp.status_code,
                detail=error.get('message') or 'Error eliminant plantilla'
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        raise HTTPException(status_code=500, detail="Error eliminant plantilla")
