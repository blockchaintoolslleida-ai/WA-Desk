-- Admin Platform Migration: Multi-tenant WhatsApp Management
-- Run this in Supabase SQL Editor

-- 1. Tenants table
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'inactive')),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. WhatsApp Accounts (per tenant)
CREATE TABLE IF NOT EXISTS whatsapp_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    account_name TEXT NOT NULL DEFAULT '',
    business_name TEXT NOT NULL DEFAULT '',
    display_phone_number TEXT DEFAULT '',
    phone_number_id TEXT DEFAULT '',
    whatsapp_business_account_id TEXT DEFAULT '',
    business_manager_id TEXT DEFAULT '',
    meta_app_id TEXT DEFAULT '',
    sender_display_name TEXT DEFAULT '',
    connection_status TEXT NOT NULL DEFAULT 'disconnected' CHECK (connection_status IN ('connected', 'disconnected', 'error')),
    webhook_status TEXT NOT NULL DEFAULT 'not_configured' CHECK (webhook_status IN ('verified', 'not_configured', 'error')),
    token_status TEXT NOT NULL DEFAULT 'not_set' CHECK (token_status IN ('valid', 'expired', 'not_set', 'error')),
    last_validation_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 3. WhatsApp Secrets (encrypted credentials)
CREATE TABLE IF NOT EXISTS whatsapp_secrets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    whatsapp_account_id UUID NOT NULL UNIQUE REFERENCES whatsapp_accounts(id) ON DELETE CASCADE,
    encrypted_access_token TEXT,
    encrypted_app_secret TEXT,
    encrypted_verify_token TEXT,
    token_expires_at TIMESTAMPTZ,
    last_rotated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 4. Webhook Logs
CREATE TABLE IF NOT EXISTS whatsapp_webhook_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    whatsapp_account_id UUID REFERENCES whatsapp_accounts(id),
    event_type TEXT NOT NULL DEFAULT 'unknown',
    payload_json JSONB,
    delivery_status TEXT DEFAULT 'received',
    error_message TEXT,
    received_at TIMESTAMPTZ DEFAULT now()
);

-- 5. API Logs
CREATE TABLE IF NOT EXISTS whatsapp_api_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    whatsapp_account_id UUID REFERENCES whatsapp_accounts(id),
    direction TEXT NOT NULL DEFAULT 'outbound' CHECK (direction IN ('inbound', 'outbound')),
    endpoint TEXT,
    request_summary TEXT,
    response_summary TEXT,
    status_code INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 6. Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID,
    action_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    description TEXT,
    ip_address TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 7. Add tenant_id to profiles if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='profiles' AND column_name='tenant_id') THEN
        ALTER TABLE profiles ADD COLUMN tenant_id UUID REFERENCES tenants(id);
    END IF;
END $$;

-- 8. Create default tenant
INSERT INTO tenants (id, name, slug, status) VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'Default Workshop',
    'default',
    'active'
) ON CONFLICT (slug) DO NOTHING;

-- 9. Link existing profiles to default tenant
UPDATE profiles SET tenant_id = 'a0000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;

-- 10. Create indexes
CREATE INDEX IF NOT EXISTS idx_wa_accounts_tenant ON whatsapp_accounts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_wa_secrets_account ON whatsapp_secrets(whatsapp_account_id);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_tenant ON whatsapp_webhook_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_logs_tenant ON whatsapp_api_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC);

-- Enable RLS
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_secrets ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_webhook_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_api_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Service role bypass (backend uses service role key)
CREATE POLICY "service_role_all_tenants" ON tenants FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_wa_accounts" ON whatsapp_accounts FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_wa_secrets" ON whatsapp_secrets FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_webhook_logs" ON whatsapp_webhook_logs FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_api_logs" ON whatsapp_api_logs FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_audit_logs" ON audit_logs FOR ALL USING (auth.role() = 'service_role');
