# WhatsApp Business Desk - Roadmap

## P0 - Completed
- [x] Core helpdesk (inbox, chat, cases, messages, dashboard)
- [x] Multi-case architecture + message classification
- [x] i18n (CA/ES/EN) with locale-aware dates
- [x] WhatsApp media support + reply/quote
- [x] Agent CRUD with role hierarchy
- [x] 24h window management (countdown, blocking, templates, auto-reminder)
- [x] Admin Platform Phase 1 (Account config, Credentials encryption, Webhook management, Audit logs)
- [x] Multi-tenant agent isolation (profiles filtered by tenant_id)
- [x] Admin page simplified (account_name + phone_number_id + certificate inline)
- [x] Admin navigation fixed (back to inbox + header nav)
- [x] Admin sidebar renamed to "Configuració"

## P1 - Next
- [ ] **MIGRATION**: Run `supabase_tenant_isolation_migration.sql` to add tenant_id to conversations & contacts
- [ ] Secció 5: Configuració de missatgeria (automatitzacions, respostes automàtiques)
- [ ] Secció 6: Regles de la finestra 24h (configurables per tenant)
- [ ] Secció 7: Gestió d'agents + equips + assignació (manual, round-robin, per departament)
- [ ] Secció 8: Sincronització de plantilles amb Meta (CRUD + preview + approval status)
- [ ] Secció 9: Dashboard resum (KPIs: connexió, webhook, token, converses)

## P2 - Future
- [ ] Notes internes millorades (editar, eliminar)
- [ ] Selecció múltiple de missatges no classificats
- [ ] Mètriques avançades amb gràfics (recharts)
- [ ] Exportació converses/casos (PDF/CSV)
- [ ] Notificacions en temps real (Supabase Realtime)
- [ ] Respostes ràpides / plantilles predefinides
- [ ] Etiquetes personalitzades per casos
- [ ] RLS per rol i tenant
- [ ] Gestió de plantilles WhatsApp des de la UI
