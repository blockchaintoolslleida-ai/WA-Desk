-- ============================================
-- Migració: Aïllament multi-tenant complet
-- Afegeix tenant_id a conversations i contacts
-- ============================================

-- 1. Afegir tenant_id a contacts (si no existeix)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='contacts' AND column_name='tenant_id') THEN
        ALTER TABLE contacts ADD COLUMN tenant_id UUID REFERENCES tenants(id);
    END IF;
END $$;

-- 2. Afegir tenant_id a conversations (si no existeix)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='conversations' AND column_name='tenant_id') THEN
        ALTER TABLE conversations ADD COLUMN tenant_id UUID REFERENCES tenants(id);
    END IF;
END $$;

-- 3. Assignar tenant per defecte a registres existents sense tenant
-- (Utilitza el primer tenant actiu com a default)
UPDATE contacts SET tenant_id = (SELECT id FROM tenants WHERE status = 'active' ORDER BY created_at LIMIT 1)
WHERE tenant_id IS NULL;

UPDATE conversations SET tenant_id = (SELECT id FROM tenants WHERE status = 'active' ORDER BY created_at LIMIT 1)
WHERE tenant_id IS NULL;

-- 4. Índexs per rendiment
CREATE INDEX IF NOT EXISTS idx_contacts_tenant ON contacts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_conversations_tenant ON conversations(tenant_id);
