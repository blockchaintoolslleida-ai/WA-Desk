"""
Media Proxy Router — Proxies media requests from frontend to OpenWA.
Solves the problem of media_url being null: instead of downloading media upfront,
we generate a proxy URL that fetches from OpenWA on-demand.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import httpx
import logging
from database import get_supabase_admin
from services.secrets_manager import decrypt_value

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/media", tags=["Media Proxy"])


@router.get("/openwa/{session_id}/{msg_id}")
async def proxy_openwa_media(session_id: str, msg_id: str):
    """Proxy media from OpenWA through WA-Desk so the frontend can display it.
    The frontend uses this URL format: /api/media/openwa/{sessionId}/{msgId}
    """
    try:
        # Get OpenWA credentials
        sb = get_supabase_admin()
        acc = sb.table('whatsapp_accounts').select(
            'id, openwa_server_url'
        ).eq('openwa_session_id', session_id).eq('connection_type', 'openwa').limit(1).execute()

        if not acc.data:
            raise HTTPException(status_code=404, detail="Session not found")

        server_url = acc.data[0].get('openwa_server_url', '')
        acc_id = acc.data[0].get('id', '')

        secrets = sb.table('whatsapp_secrets').select('encrypted_openwa_api_key').eq(
            'whatsapp_account_id', acc_id).limit(1).execute()
        if not secrets.data or not secrets.data[0].get('encrypted_openwa_api_key'):
            raise HTTPException(status_code=404, detail="API key not found")

        api_key = decrypt_value(secrets.data[0]['encrypted_openwa_api_key'])

        # Try to fetch media from OpenWA via multiple possible endpoints
        media_content = None
        content_type = 'application/octet-stream'

        paths = [
            f"/api/sessions/{session_id}/messages/{msg_id}/media",
            f"/api/sessions/{session_id}/media/{msg_id}",
        ]

        async with httpx.AsyncClient(timeout=20) as client:
            for path in paths:
                try:
                    url = f"{server_url.rstrip('/')}{path}"
                    resp = await client.get(url, headers={"X-API-Key": api_key})
                    if resp.status_code == 200 and len(resp.content) > 100:
                        media_content = resp.content
                        content_type = resp.headers.get('content-type', content_type)
                        logger.info(f"Proxied media from OpenWA: {len(media_content)} bytes via {path}")
                        break
                except Exception:
                    continue

        if not media_content:
            raise HTTPException(status_code=404, detail="Media not found on OpenWA")

        return StreamingResponse(
            iter([media_content]),
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Media proxy error: {e}")
        raise HTTPException(status_code=500, detail="Error fetching media")
