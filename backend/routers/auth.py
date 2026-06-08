"""
Authentication Router - Supabase Auth
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
import logging
from database import get_supabase, get_supabase_admin
from models import LoginRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
async def login(request: LoginRequest):
    """Login with email/username + password via Supabase Auth"""
    supabase = get_supabase()
    admin_client = get_supabase_admin()

    try:
        email = request.email

        # Username lookup
        if '@' not in email:
            res = admin_client.table('profiles').select('email').eq('username', email.strip().lower()).execute()
            if not res.data:
                raise HTTPException(status_code=401, detail="Usuari no trobat")
            email = res.data[0]['email']

        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": request.password
        })

        if not auth_response.user:
            raise HTTPException(status_code=401, detail="Credencials incorrectes")

        profile = admin_client.table('profiles').select('id, full_name, email, role, phone, is_active, created_at, username, tenant_id').eq(
            'id', auth_response.user.id
        ).execute()

        if not profile.data:
            raise HTTPException(status_code=404, detail="Perfil no trobat")

        user_data = profile.data[0]

        if not user_data.get('is_active', True):
            raise HTTPException(status_code=403, detail="Compte desactivat")

        return {
            "access_token": auth_response.session.access_token,
            "token_type": "bearer",
            "user": user_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=401, detail="Error d'autenticacio")


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    if not authorization:
        return {"message": "OK"}
    try:
        supabase = get_supabase()
        supabase.auth.sign_out()
    except Exception:
        pass
    return {"message": "Sessio tancada"}


@router.get("/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Get current authenticated user profile"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticat")

    token = authorization.replace("Bearer ", "")
    admin_client = get_supabase_admin()

    try:
        user_response = admin_client.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Token invalid")

        profile = admin_client.table('profiles').select(
            'id, full_name, email, role, phone, is_active, created_at, username, tenant_id'
        ).eq('id', user_response.user.id).single().execute()

        if not profile.data:
            raise HTTPException(status_code=404, detail="Perfil no trobat")

        return profile.data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user failed: {e}")
        raise HTTPException(status_code=401, detail="Error d'autenticacio")
