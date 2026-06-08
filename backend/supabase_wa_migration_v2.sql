-- WhatsApp Business Desk - Migration V2: Multi-Case Model
-- Run this in the Supabase SQL Editor

-- ============================================
-- 1. Cases table (core new entity)
-- ============================================
CREATE TABLE IF NOT EXISTS cases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'per_atendre' CHECK (status IN ('nou','per_atendre','en_atencio','esperant_client','resolt','tancat')),
  assigned_agent_id UUID REFERENCES profiles(id),
  priority TEXT DEFAULT 'normal',
  case_type TEXT,
  created_by UUID REFERENCES profiles(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  last_activity_at TIMESTAMPTZ DEFAULT now(),
  is_active BOOLEAN DEFAULT true
);

-- ============================================
-- 2. Add case_id and needs_classification to messages
-- ============================================
ALTER TABLE messages ADD COLUMN IF NOT EXISTS case_id UUID REFERENCES cases(id) ON DELETE SET NULL;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS needs_classification BOOLEAN DEFAULT false;

-- ============================================
-- 3. Case events (audit trail per case)
-- ============================================
CREATE TABLE IF NOT EXISTS case_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  actor_id UUID REFERENCES profiles(id),
  event_type TEXT NOT NULL,
  old_value JSONB,
  new_value JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- 4. Case views (collision detection per case)
-- ============================================
CREATE TABLE IF NOT EXISTS case_views (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  agent_id UUID NOT NULL REFERENCES profiles(id),
  viewed_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- 5. Case notes (internal notes per case)
-- ============================================
CREATE TABLE IF NOT EXISTS case_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  author_id UUID NOT NULL REFERENCES profiles(id),
  note TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- 6. Drop status constraint on conversations (now derived)
-- ============================================
ALTER TABLE conversations DROP CONSTRAINT IF EXISTS conversations_status_check;
ALTER TABLE conversations ALTER COLUMN status DROP NOT NULL;
ALTER TABLE conversations ALTER COLUMN status SET DEFAULT NULL;

-- ============================================
-- 7. Indexes
-- ============================================
CREATE INDEX IF NOT EXISTS idx_cases_conversation ON cases(conversation_id);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_assigned ON cases(assigned_agent_id);
CREATE INDEX IF NOT EXISTS idx_cases_active ON cases(is_active);
CREATE INDEX IF NOT EXISTS idx_messages_case ON messages(case_id);
CREATE INDEX IF NOT EXISTS idx_messages_needs_class ON messages(needs_classification) WHERE needs_classification = true;
CREATE INDEX IF NOT EXISTS idx_case_events_case ON case_events(case_id);
CREATE INDEX IF NOT EXISTS idx_case_views_case ON case_views(case_id);
CREATE INDEX IF NOT EXISTS idx_case_notes_case ON case_notes(case_id);

-- ============================================
-- 8. RLS + Policies
-- ============================================
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_views ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_notes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_cases" ON cases FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_case_events" ON case_events FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_case_views" ON case_views FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_case_notes" ON case_notes FOR ALL USING (true) WITH CHECK (true);
