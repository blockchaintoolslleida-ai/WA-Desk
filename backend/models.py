"""
WhatsApp Business Desk - Pydantic Models (Phase 2: Multi-Case Architecture)
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any
from enum import Enum


# ============== Enums ==============

class CaseStatus(str, Enum):
    NOU = "nou"
    PER_ATENDRE = "per_atendre"
    EN_ATENCIO = "en_atencio"
    ESPERANT_CLIENT = "esperant_client"
    RESOLT = "resolt"
    TANCAT = "tancat"


class CasePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageDirection(str, Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    OUTBOUND_FROM_MOBILE = "outbound_from_mobile"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    DOCUMENT = "document"
    VIDEO = "video"
    SYSTEM = "system"


# ============== Auth Models ==============

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


# ============== Profile Models ==============

class ProfileCreate(BaseModel):
    full_name: str
    email: str
    role: str = "agent"
    phone: Optional[str] = None
    password: str


# ============== Message Models ==============

class MessageCreate(BaseModel):
    body: str


class NoteCreate(BaseModel):
    note: str


# ============== WhatsApp Models ==============

class WhatsAppInboundMessage(BaseModel):
    phone: str
    message_id: str
    body: str
    timestamp: str
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    contact_name: Optional[str] = None


class WhatsAppOutboundMessage(BaseModel):
    phone: str
    body: str
    preview_url: bool = False
