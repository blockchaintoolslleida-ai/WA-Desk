# WADesk - WhatsApp Business Helpdesk

Plataforma multi-tenant de helpdesk per WhatsApp Business. Permet a empreses gestionar la comunicació amb els seus clients de forma centralitzada.

## Funcionalitats

- **Safata d'entrada**: Gestió de converses WhatsApp amb vista de 3 columnes
- **Multi-cas**: Arquitectura de múltiples casos per conversa amb classificació de missatges
- **Finestra 24h**: Control de la finestra de missatgeria de WhatsApp amb countdown, bloqueig i selector de plantilles
- **Panell d'administració**: Configuració de compte WhatsApp, webhook, certificat i registre d'auditoria
- **Multi-tenant**: Aïllament de dades per empresa amb encriptació de credencials (AES-256/Fernet)
- **Wizard de configuració**: Assistent guiat de 3 passos per nous tenants
- **Agents**: CRUD d'agents amb rols (admin, agent)
- **Multi-idioma**: Català, Castellà, Anglès

## Tech Stack

- **Frontend**: React + TailwindCSS + Phosphor Icons
- **Backend**: FastAPI (Python)
- **Base de dades**: Supabase (PostgreSQL)
- **Autenticació**: Supabase Auth
- **Encriptació**: Fernet (cryptography)
- **Missatgeria**: WhatsApp Business API (Meta Graph API v25.0)

## Configuració

### 1. Variables d'entorn

Backend (`/app/backend/.env`):
```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
WHATSAPP_VERIFY_TOKEN=el_teu_token_de_verificacio
WHATSAPP_PHONE_NUMBER_ID=el_teu_phone_number_id
WHATSAPP_ACCESS_TOKEN=EAAxxxxx
ENCRYPTION_KEY=la_teva_clau_fernet
BASE_URL=https://el-teu-domini.com
```

Frontend (`/app/frontend/.env`):
```
REACT_APP_BACKEND_URL=https://el-teu-domini.com
REACT_APP_SUPABASE_URL=https://xxxxx.supabase.co
REACT_APP_SUPABASE_ANON_KEY=eyJ...
```

### 2. Base de dades

Executa els scripts SQL a Supabase SQL Editor en aquest ordre:
1. Schema principal (taules: profiles, contacts, conversations, messages, cases)
2. `supabase_wa_migration_v2.sql` (extensions WhatsApp)
3. `supabase_admin_platform_migration.sql` (admin multi-tenant)
4. `supabase_tenant_isolation_migration.sql` (tenant_id a conversations/contacts)

### 3. Configuració WhatsApp

1. Crea una app a [developers.facebook.com](https://developers.facebook.com)
2. Configura el webhook:
   - **URL**: `https://el-teu-domini.com/api/whatsapp/webhook`
   - **Token de verificació**: el valor de `WHATSAPP_VERIFY_TOKEN`
3. Subscriu-te al camp **messages**
4. Copia el **Phone Number ID** i l'**Access Token** (EAA...)

## Rols d'usuari

| Rol | Accés |
|-----|-------|
| `super_admin` | Accés total al sistema |
| `admin` | Administració del seu tenant |
| `agent` | Gestió de converses i casos |

## API Endpoints

### Autenticació
- `POST /api/auth/login` - Login (email o username)
- `GET /api/auth/me` - Perfil de l'usuari actual

### Converses
- `GET /api/conversations` - Llistat (filtrat per tenant)
- `GET /api/conversations/{id}` - Detall amb contacte i casos

### Missatges
- `GET /api/messages/{conversation_id}` - Missatges d'una conversa
- `POST /api/messages/send` - Enviar missatge WhatsApp

### Agents
- `GET /api/agents` - Llistat (filtrat per tenant)
- `POST /api/agents` - Crear agent
- `DELETE /api/agents/{id}` - Eliminar agent

### Webhook WhatsApp
- `GET /api/whatsapp/webhook` - Verificació Meta + diagnòstic
- `POST /api/whatsapp/webhook` - Recepció de missatges

### Administració
- `GET /api/admin/whatsapp-account` - Configuració del compte
- `PUT /api/admin/whatsapp-account` - Actualitzar compte
- `POST /api/admin/whatsapp-account/validate` - Validar connexió
- `GET /api/admin/webhook-config` - Configuració webhook
- `GET /api/admin/audit-logs` - Registre d'auditoria

### Finestra 24h
- `GET /api/window/{conversation_id}` - Estat de la finestra
- `POST /api/window/template` - Enviar plantilla

### Pàgines estàtiques
- `GET /api/privacy-policy` - Política de privacitat (HTML)

## Idiomes

- Català (ca) - Per defecte
- Castellà (es)
- Anglès (en)

## Llicència

Propietari - Tots els drets reservats
