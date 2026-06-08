"""
Secrets Manager - Fernet encryption for WhatsApp credentials
"""
import os
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')

def _get_fernet():
    if not ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not configured in .env")
    return Fernet(ENCRYPTION_KEY.encode())

def encrypt_value(plain_text: str) -> str:
    if not plain_text:
        return ''
    f = _get_fernet()
    return f.encrypt(plain_text.encode()).decode()

def decrypt_value(encrypted_text: str) -> str:
    if not encrypted_text:
        return ''
    f = _get_fernet()
    try:
        return f.decrypt(encrypted_text.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt value - invalid key or corrupted data")
        return ''

def mask_value(value: str, visible_chars: int = 6) -> str:
    if not value or len(value) <= visible_chars:
        return '*' * 8
    return value[:visible_chars] + '*' * (len(value) - visible_chars)
