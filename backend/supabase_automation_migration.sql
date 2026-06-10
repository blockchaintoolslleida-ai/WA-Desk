-- ============================================================
-- Section 5: Messaging Automation — Database Tables
-- ============================================================

-- 1. Automation Rules
CREATE TABLE IF NOT EXISTS automation_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  category TEXT NOT NULL CHECK (category IN ('greeting', 'schedule', 'keywords', 'fallback')),
  name TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  priority INTEGER NOT NULL DEFAULT 1,
  trigger_config JSONB NOT NULL DEFAULT '{}',
  response_text TEXT,
  delay_seconds INTEGER DEFAULT 0,
  daily_limit INTEGER,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_automation_rules_tenant
  ON automation_rules(tenant_id, category, priority);

-- 2. Business Hours
CREATE TABLE IF NOT EXISTS business_hours (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  timezone TEXT NOT NULL DEFAULT 'Europe/Madrid',
  schedule JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(tenant_id)
);

-- 3. Assignment Config
CREATE TABLE IF NOT EXISTS assignment_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  is_enabled BOOLEAN DEFAULT false,
  timeout_minutes INTEGER DEFAULT 5,
  strategy TEXT NOT NULL DEFAULT 'round_robin',
  agent_pool UUID[] DEFAULT '{}',
  last_assigned_index INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(tenant_id)
);

-- 4. Automation Logs
CREATE TABLE IF NOT EXISTS automation_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  rule_id UUID REFERENCES automation_rules(id) ON DELETE SET NULL,
  conversation_id UUID,
  message_id UUID,
  category TEXT,
  triggered_at TIMESTAMPTZ DEFAULT now(),
  response_preview TEXT
);

CREATE INDEX IF NOT EXISTS idx_automation_logs_tenant_date
  ON automation_logs(tenant_id, triggered_at);
CREATE INDEX IF NOT EXISTS idx_automation_logs_rule
  ON automation_logs(rule_id, triggered_at);
