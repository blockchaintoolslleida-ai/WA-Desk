# WhatsApp Business Desk - Product Requirements Document

## Original Problem Statement
Build a professional WhatsApp Business Helpdesk web application with multi-tenant admin platform. Key features:
- 3-column helpdesk UI (conversation list | chat view | detail panel)
- Multi-case architecture per conversation
- Multi-language support (Catalan, Spanish, English)
- 24h WhatsApp messaging window management
- Multi-tenant admin panel for WhatsApp Business account management
- Strict tenant data isolation
- Guided first-use setup wizard for new tenants

## Tech Stack
- **Backend:** FastAPI + Python
- **Frontend:** React + TailwindCSS + Shadcn UI + Phosphor Icons
- **Database:** Supabase (PostgreSQL) via REST API
- **Auth:** Supabase Auth
- **Messaging:** WhatsApp Business API (Meta Graph API)
- **Storage:** Supabase Storage (media bucket)
- **Encryption:** Fernet (cryptography library) for secret storage
- **i18n:** Custom React Context (CA/ES/EN) with locale-aware dates

## Multi-Tenant Architecture
- Each company (tenant) has independent WhatsApp config, credentials, webhook
- Strict data separation: no cross-tenant data access
- New admins must create their tenant before configuring WhatsApp
- Secrets encrypted with Fernet, never returned in plain text
- All admin actions logged in audit trail
- Agent list filtered by tenant_id (profiles table)
- Conversations filtered by tenant_id (requires migration)
- Webhook assigns tenant_id from phone_number_id lookup

## Implemented Features

### Phase 1 - Core Helpdesk (Complete)
- [x] Login/logout, 3-column inbox, conversations, chat, dashboard

### Phase 2 - Multi-Case (Complete)
- [x] Multi-case architecture, case CRUD, message classification
- [x] i18n (CA/ES/EN), media, reply/quote, agents CRUD

### Phase 2.5 - Window 24h (Complete)
- [x] Countdown badge, input blocking, template selector, auto-reminder

### Phase 3 - Admin Platform (In Progress)
- [x] **Tenant onboarding** - New admins create their company first
- [x] **Section 1: WhatsApp Account** - Simplified: account_name + phone_number_id + certificate
- [x] **Section 2: Credentials** - Merged into Account section (Fernet encryption)
- [x] **Section 3: Webhook** - URL/token display, copy, verify, events
- [x] **Section 4: Audit Trail** - All actions logged
- [x] **Multi-tenant isolation** - Agents, conversations, contacts filtered by tenant_id (DONE)
- [x] **Setup Wizard** - Guided 3-step first-use experience (Phone ID → Certificate → Verify)
- [x] **Section 8: Templates Management (Meta App Review)** - 2026-04-28 — List/Create/Delete WhatsApp message templates via Meta Graph API v25.0. Full CRUD UI in Admin → Plantilles. CA/ES/EN i18n. Verified end-to-end against real Meta API. Backend tests at `/app/backend/tests/test_templates.py`.
- [x] **Compliance pages** - /api/privacy-policy, /api/terms-of-service, /api/data-deletion (HTML, GET+HEAD)
- [x] **Webhook v25.0** - Updated payload parsing, no strict tenant_id dependency
- [x] **AdminPage refactor** - 2026-04-28 — Split 1319-line AdminPage.js into modular files under `/app/frontend/src/pages/admin/`: StatusBadge, SetupWizard, AccountSection, WebhookSection, AuditSection, TemplatesSection, TenantSetupForm. Main file now 139 lines.
- [ ] Section 5: Messaging config (automation rules)
- [ ] Section 6: 24h window rules
- [ ] Section 7: Agent management + teams
- [ ] Section 9: Dashboard KPIs

### Phase 5 - Multi-tenant SaaS Routing (DONE 2026-04-28)
- [x] **Tenant credentials resolver** - `services/tenant_credentials.py` resolves (token, phone_id, waba_id) per tenant with .env fallback for DEV
- [x] **Outbound routing per tenant** - `send_whatsapp_message`, `send_whatsapp_template`, `send_whatsapp_document`, `upload_media_to_whatsapp`, `send_whatsapp_image`, `mark_message_as_read` all accept tenant_id
- [x] **Templates router per tenant** - all CRUD endpoints use `_get_tenant_meta_creds` to resolve credentials
- [x] **Setup Wizard ampliat** - Step 1 ara demana Phone ID + WABA ID, links a Meta Business, tip de System User permanent token a Step 2
- [x] **Admin Account UI** - camp WABA ID editable
- [x] **Resilient delivery feedback** - red toast + "No lliurat" badge on failed sends

### Phase 4 - Cases Enhancements
- [x] **Internal Notes CRUD per case** - 2026-04-28
- [ ] (P1) Multi-select unclassified messages → bulk-create case
- [ ] (P3) Supabase Realtime for live message/case updates
- [ ] (P3) Dashboard KPI graphs

### Pending Migration
- [x] Tenant isolation migration applied — conversations/contacts have tenant_id
- [x] WHATSAPP_BUSINESS_ACCOUNT_ID added to backend/.env (1479512030191419)
- [x] WHATSAPP_PHONE_NUMBER_ID updated to 1106052232582803 (matches new Meta token scope)

## Credentials
- **Admin 1:** admin@workshoppartsdesk.com / Admin123! (Auto Recanvis Catalunya)
- **Admin 2:** info@blockchaintools.es / Riullobregat$4 (BlockchainTools SL)
- **Super Admin:** superadmin@workshoppartsdesk.com / SuperAdmin2026!
- **Meta Reviewer Agent:** review@meta-test.com / MetaReview2026!

## Meta WhatsApp Configuration (Active)
- **App ID:** 1676550513335784 (CRM)
- **WABA ID:** 1479512030191419
- **Phone Number ID:** 1106052232582803 (Botiga, +34 621 12 22 40)
- **Webhook URL:** https://saas-automotive-hub.emergent.host/api/whatsapp/webhook
- **Token type:** SYSTEM_USER permanent (no expiry, `expires_at=0`)
- **Token scopes:** whatsapp_business_management, whatsapp_business_messaging, manage_app_solution, whatsapp_business_manage_events

## Outbound Delivery Tracking (2026-04-28)
- `services/whatsapp.py::send_whatsapp_message` returns `{ok, error, wamid}` instead of bool
- `routers/messages.py` and `routers/window.py` propagate `whatsapp_error` to frontend
- `pages/InboxPage.js` shows red toast (8s) with Meta error when send fails
- `components/ChatView.js` renders a red "No lliurat" badge on each failed outgoing bubble (uses `msg.delivery_status === 'failed'`)
- Optional migration `/app/backend/supabase_messages_delivery_status.sql` adds `delivery_status` and `delivery_error` columns. Without it, the badge only shows on freshly-failed sends in the current session (state not persisted across reloads).
