import { useState } from 'react';
import { useTranslation } from '../contexts/LanguageContext';
import { X } from '@phosphor-icons/react';

export default function CreateCaseModal({ agents, onClose, onCreate, selectedCount, currentUserId }) {
  const { t } = useTranslation();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [assignedAgentId, setAssignedAgentId] = useState(currentUserId || '');
  const [priority, setPriority] = useState('normal');
  const [initialNote, setInitialNote] = useState('');
  const [creating, setCreating] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    setCreating(true);
    await onCreate({
      title: title.trim(),
      description: description.trim() || null,
      assigned_agent_id: assignedAgentId || null,
      priority,
      initial_note: initialNote.trim() || null,
    });
    setCreating(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-lg border border-[#E2E8F0] shadow-xl w-full max-w-md mx-4 animate-fade-in" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-[#E2E8F0]">
          <h2 className="text-sm font-bold" style={{ fontFamily: 'Manrope' }}>
            {selectedCount > 0 ? t('case.create_from_messages') : t('case.create')}
          </h2>
          <button onClick={onClose} className="text-[#64748B] hover:text-[#475569]"><X size={18} /></button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-3">
          {selectedCount > 0 && (
            <p className="text-xs text-[#2563EB] bg-blue-50 px-3 py-1.5 rounded-md border border-blue-200">
              {selectedCount} {t('chat.selected')}
            </p>
          )}

          <div>
            <label className="block text-xs font-semibold text-[#475569] uppercase tracking-wide mb-1">{t('case.title_label')}</label>
            <input data-testid="case-title-input" type="text" value={title} onChange={e => setTitle(e.target.value)} placeholder={t('case.title_placeholder')} className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" required />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#475569] uppercase tracking-wide mb-1">{t('case.description_label')}</label>
            <input type="text" value={description} onChange={e => setDescription(e.target.value)} placeholder={t('case.description_placeholder')} className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[#475569] uppercase tracking-wide mb-1">{t('case.assign_label')}</label>
              <select value={assignedAgentId} onChange={e => setAssignedAgentId(e.target.value)} className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]">
                <option value="">—</option>
                {agents.map(a => <option key={a.id} value={a.id}>{a.full_name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#475569] uppercase tracking-wide mb-1">{t('case.priority_label')}</label>
              <select value={priority} onChange={e => setPriority(e.target.value)} className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]">
                <option value="low">{t('priority.low')}</option>
                <option value="normal">{t('priority.normal')}</option>
                <option value="high">{t('priority.high')}</option>
                <option value="urgent">{t('priority.urgent')}</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#475569] uppercase tracking-wide mb-1">{t('case.note_label')}</label>
            <input type="text" value={initialNote} onChange={e => setInitialNote(e.target.value)} placeholder={t('case.note_placeholder')} className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
          </div>

          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="flex-1 py-2 text-sm font-medium border border-[#E2E8F0] rounded-md hover:bg-[#F1F5F9]">{t('case.cancel')}</button>
            <button data-testid="submit-create-case" type="submit" disabled={!title.trim() || creating} className="flex-1 py-2 text-sm font-medium bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] disabled:opacity-50">
              {creating ? t('case.creating') : t('case.create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
