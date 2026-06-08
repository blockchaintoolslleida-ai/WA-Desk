"""
Agents Router - Full CRUD with role hierarchy
super_admin > admin > agent
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from pydantic import BaseModel
import logging
from datetime import datetime, timezone
from database import get_supabase_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["Agents"])

ROLE_HIERARCHY = {'super_admin': 3, 'admin': 2, 'agent': 1}


class AgentCreate(BaseModel):
    full_name: str
    email: str
    password: str
    role: str = "agent"
    phone: Optional[str] = None


class AgentUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


async def get_authenticated_user(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticat")
    token = authorization.replace("Bearer ", "")
    admin_client = get_supabase_admin()
    try:
        user_response = admin_client.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Token invalid")
        profile = admin_client.table('profiles').select('id, full_name, role, tenant_id').eq('id', user_response.user.id).single().execute()
        if not profile.data:
            raise HTTPException(status_code=401, detail="Perfil no trobat")
        return profile.data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Error d'autenticacio")


def require_admin(user):
    if user['role'] not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Nomes administradors poden gestionar agents")


def can_manage_role(actor_role: str, target_role: str) -> bool:
    return ROLE_HIERARCHY.get(actor_role, 0) > ROLE_HIERARCHY.get(target_role, 0)


@router.get("")
async def list_agents(authorization: Optional[str] = Header(None)):
    """List agents/admins for current tenant"""
    user = await get_authenticated_user(authorization)
    supabase = get_supabase_admin()
    try:
        query = supabase.table('profiles').select(
            'id, full_name, email, role, phone, is_active, created_at'
        ).in_('role', ['super_admin', 'admin', 'agent'])

        tenant_id = user.get('tenant_id')
        if tenant_id and user.get('role') != 'super_admin':
            query = query.eq('tenant_id', tenant_id)

        result = query.order('created_at').execute()
        return result.data or []
    except Exception as e:
        logger.error(f"List agents error: {e}")
        raise HTTPException(status_code=500, detail="Error carregant agents")


@router.post("")
async def create_agent(req: AgentCreate, authorization: Optional[str] = Header(None)):
    """Create a new agent (admin+ only). Admins can only create agents, super_admins can create admins too."""
    user = await get_authenticated_user(authorization)
    require_admin(user)

    target_role = req.role if req.role in ['agent', 'admin'] else 'agent'
    if target_role == 'admin' and user['role'] != 'super_admin':
        raise HTTPException(status_code=403, detail="Nomes el superadministrador pot crear administradors")

    supabase = get_supabase_admin()
    try:
        auth_response = supabase.auth.admin.create_user({
            "email": req.email,
            "password": req.password,
            "email_confirm": True
        })

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Error creant usuari d'autenticacio")

        profile_data = {
            'id': auth_response.user.id,
            'full_name': req.full_name.strip(),
            'email': req.email.strip(),
            'role': target_role,
            'phone': req.phone.strip() if req.phone else None,
            'is_active': True,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'tenant_id': user.get('tenant_id'),
        }
        supabase.table('profiles').insert(profile_data).execute()
        return profile_data

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if 'already been registered' in error_msg or 'duplicate' in error_msg.lower():
            raise HTTPException(status_code=400, detail="Ja existeix un usuari amb aquest email")
        logger.error(f"Create agent error: {e}")
        raise HTTPException(status_code=500, detail=f"Error creant agent: {error_msg[:100]}")


@router.put("/{agent_id}")
async def update_agent(agent_id: str, req: AgentUpdate, authorization: Optional[str] = Header(None)):
    """Update agent info. Admins can update agents, super_admins can update admins."""
    user = await get_authenticated_user(authorization)
    require_admin(user)
    supabase = get_supabase_admin()

    try:
        target = supabase.table('profiles').select('id, role').eq('id', agent_id).single().execute()
        if not target.data:
            raise HTTPException(status_code=404, detail="Agent no trobat")

        target_role = target.data['role']
        if not can_manage_role(user['role'], target_role) and user['id'] != agent_id:
            raise HTTPException(status_code=403, detail="No tens permis per modificar aquest usuari")

        updates = {}
        if req.full_name is not None:
            updates['full_name'] = req.full_name.strip()
        if req.phone is not None:
            updates['phone'] = req.phone.strip() if req.phone.strip() else None
        if req.is_active is not None:
            updates['is_active'] = req.is_active
        if req.role is not None and req.role in ['agent', 'admin']:
            if req.role == 'admin' and user['role'] != 'super_admin':
                raise HTTPException(status_code=403, detail="Nomes el superadministrador pot assignar rol d'administrador")
            updates['role'] = req.role

        result = supabase.table('profiles').update(updates).eq('id', agent_id).execute()
        return result.data[0] if result.data else {"ok": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update agent error: {e}")
        raise HTTPException(status_code=500, detail="Error actualitzant agent")


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, authorization: Optional[str] = Header(None)):
    """Deactivate agent. Admins can deactivate agents, super_admins can deactivate admins."""
    user = await get_authenticated_user(authorization)
    require_admin(user)
    supabase = get_supabase_admin()

    try:
        target = supabase.table('profiles').select('id, role').eq('id', agent_id).single().execute()
        if not target.data:
            raise HTTPException(status_code=404, detail="Agent no trobat")

        if not can_manage_role(user['role'], target.data['role']):
            raise HTTPException(status_code=403, detail="No tens permis per eliminar aquest usuari")

        if agent_id == user['id']:
            raise HTTPException(status_code=400, detail="No et pots eliminar a tu mateix")

        if user['role'] == 'super_admin':
            # Hard delete by super_admin
            supabase.table('profiles').delete().eq('id', agent_id).execute()
            return {"ok": True, "deleted": True, "hard": True}
        else:
            # Soft delete by admin
            supabase.table('profiles').update({
                'is_active': False
            }).eq('id', agent_id).execute()
            return {"ok": True, "deactivated": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete agent error: {e}")
        raise HTTPException(status_code=500, detail="Error eliminant agent")
