-- ============================================
-- Migration: Add updated_at to case_notes
-- Apply via Supabase SQL editor
-- ============================================

ALTER TABLE case_notes
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

COMMENT ON COLUMN case_notes.updated_at IS 'Set when the author edits the note. NULL means never edited.';
