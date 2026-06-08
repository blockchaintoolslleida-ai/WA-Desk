"""
Media Service - Download from WhatsApp, store in Supabase Storage
"""
import httpx
import logging
import uuid
import mimetypes
from typing import Optional, Tuple
from config import WHATSAPP_ACCESS_TOKEN, WHATSAPP_API_URL
from database import get_supabase_admin

logger = logging.getLogger(__name__)

MIME_EXTENSIONS = {
    'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
    'audio/ogg': '.ogg', 'audio/mpeg': '.mp3', 'audio/aac': '.aac', 'audio/opus': '.opus',
    'video/mp4': '.mp4', 'video/3gpp': '.3gp',
    'application/pdf': '.pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
    'text/plain': '.txt',
}


async def download_whatsapp_media(media_id: str) -> Optional[Tuple[bytes, str]]:
    """Download media from WhatsApp API. Returns (file_bytes, mime_type) or None."""
    if not WHATSAPP_ACCESS_TOKEN or WHATSAPP_ACCESS_TOKEN.startswith('PLACEHOLDER'):
        return None

    headers = {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Get the download URL from the media ID
            meta_url = f"{WHATSAPP_API_URL}/{media_id}"
            meta_res = await client.get(meta_url, headers=headers)
            if meta_res.status_code != 200:
                logger.error(f"Media meta fetch failed: {meta_res.status_code} - {meta_res.text}")
                return None

            data = meta_res.json()
            download_url = data.get('url')
            mime_type = data.get('mime_type', 'application/octet-stream')

            if not download_url:
                logger.error("No download URL in media response")
                return None

            # Step 2: Download the actual file
            file_res = await client.get(download_url, headers=headers)
            if file_res.status_code != 200:
                logger.error(f"Media download failed: {file_res.status_code}")
                return None

            logger.info(f"Downloaded media {media_id}: {len(file_res.content)} bytes, {mime_type}")
            return (file_res.content, mime_type)

    except Exception as e:
        logger.error(f"Media download error: {e}")
        return None


def upload_to_storage(file_bytes: bytes, mime_type: str, folder: str = "incoming") -> Optional[str]:
    """Upload file to Supabase Storage and return public URL."""
    try:
        supabase = get_supabase_admin()
        ext = MIME_EXTENSIONS.get(mime_type, mimetypes.guess_extension(mime_type) or '.bin')
        filename = f"{folder}/{uuid.uuid4().hex}{ext}"

        supabase.storage.from_('media').upload(
            filename,
            file_bytes,
            file_options={"content-type": mime_type}
        )

        public_url = supabase.storage.from_('media').get_public_url(filename)
        logger.info(f"Uploaded to storage: {filename}")
        return public_url

    except Exception as e:
        logger.error(f"Storage upload error: {e}")
        return None


async def process_incoming_media(whatsapp_media_id: str) -> Optional[str]:
    """Download from WhatsApp and upload to Supabase Storage. Returns public URL."""
    result = await download_whatsapp_media(whatsapp_media_id)
    if not result:
        return None

    file_bytes, mime_type = result
    return upload_to_storage(file_bytes, mime_type, folder="incoming")


def upload_agent_file(file_bytes: bytes, mime_type: str, filename: str) -> Optional[str]:
    """Upload an agent's file to storage. Returns public URL."""
    try:
        supabase = get_supabase_admin()
        ext = MIME_EXTENSIONS.get(mime_type, mimetypes.guess_extension(mime_type) or '.bin')
        safe_name = f"outgoing/{uuid.uuid4().hex}{ext}"

        supabase.storage.from_('media').upload(
            safe_name,
            file_bytes,
            file_options={"content-type": mime_type}
        )

        public_url = supabase.storage.from_('media').get_public_url(safe_name)
        return public_url

    except Exception as e:
        logger.error(f"Agent file upload error: {e}")
        return None
