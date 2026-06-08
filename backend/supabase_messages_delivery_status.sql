-- ============================================
-- Migration: Add delivery tracking to messages
-- Apply via Supabase SQL editor
-- ============================================

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS delivery_status TEXT,
  ADD COLUMN IF NOT EXISTS delivery_error TEXT;

COMMENT ON COLUMN messages.delivery_status IS 'sent | failed | delivered | read | NULL (for inbound)';
COMMENT ON COLUMN messages.delivery_error IS 'Meta error message when delivery_status = failed';

CREATE INDEX IF NOT EXISTS idx_messages_delivery_status ON messages(delivery_status) WHERE delivery_status IS NOT NULL;
