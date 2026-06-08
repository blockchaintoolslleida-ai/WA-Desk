import { useState } from 'react';
import { useTranslation } from '../contexts/LanguageContext';
import { MagnifyingGlass, X, Plus, UserPlus } from '@phosphor-icons/react';
import { contactsApi, conversationsApi } from '../lib/api';

function formatTime(dateStr, locale) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const now = new Date();
  const diffMins = Math.floor((now - d) / 60000);
  if (diffMins < 1) return '~';
  if (diffMins < 60) return `${diffMins}m`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d`;
  return d.toLocaleDateString(locale, { day: 'numeric', month: 'short' });
}

export default function ConversationList({ conversations, selectedId, filter, search, loading, onSelect, onFilterChange, onSearchChange, onDelete }) {
  const { t, locale } = useTranslation();
  const [showNewContact, setShowNewContact] = useState(false);
  const [newContact, setNewContact] = useState({ name: '', phone: '' });
  const [creating, setCreating] = useState(false);

  const handleCreateContact = async () => {
    if (!newContact.name.trim() || !newContact.phone.trim()) return;
    setCreating(true);
    try {
      const res = await contactsApi.create(newContact);
      // Create a conversation for this contact
      const convRes = await conversationsApi.create({ contact_id: res.data.id });
      setShowNewContact(false);
      setNewContact({ name: '', phone: '' });
      // Reload conversations
      window.location.reload();
    } catch (e) { console.error('Create contact failed:', e); }
    setCreating(false);
  };

  const FILTERS = [
    { key: 'all', label: t('filter.all') },
    { key: 'with_pending', label: t('filter.with_pending') },
    { key: 'in_progress', label: t('filter.in_progress') },
    { key: 'unassigned', label: t('filter.unassigned') },
    { key: 'mine', label: t('filter.mine') },
    { key: 'unread', label: t('filter.unread') },
    { key: 'closed', label: t('filter.closed') },
  ];

  return (
    <>
      <div className="p-3 border-b border-[#E2E8F0]">
        <div className="relative">
          <MagnifyingGlass size={16} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#64748B]" />
          <input data-testid="conversation-search" type="text" value={search} onChange={(e) => onSearchChange(e.target.value)} placeholder={t('conv.search_placeholder')} className="w-full pl-8 pr-3 py-1.5 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A] focus:border-transparent" />
        </div>
        <button onClick={() => setShowNewContact(!showNewContact)}
          className="mt-2 w-full flex items-center justify-center gap-1 px-3 py-1.5 text-xs font-medium text-[#0F172A] border border-dashed border-[#CBD5E1] rounded-md hover:bg-[#F1F5F9] transition-colors">
          <UserPlus size={14} weight="bold" />
          {t('conv.new_contact') || 'New Contact'}
        </button>
        {showNewContact && (
          <div className="mt-2 p-2 bg-[#F8FAFC] border border-[#E2E8F0] rounded-md space-y-2">
            <input type="text" placeholder={t('conv.contact_name') || 'Name'} value={newContact.name}
              onChange={e => setNewContact(p => ({...p, name: e.target.value}))}
              className="w-full px-2 py-1.5 text-xs border border-[#E2E8F0] rounded focus:outline-none focus:ring-1 focus:ring-[#0F172A]" />
            <input type="text" placeholder={t('conv.contact_phone') || 'Phone (with country code)'} value={newContact.phone}
              onChange={e => setNewContact(p => ({...p, phone: e.target.value}))}
              className="w-full px-2 py-1.5 text-xs border border-[#E2E8F0] rounded focus:outline-none focus:ring-1 focus:ring-[#0F172A]" />
            <div className="flex gap-1">
              <button onClick={handleCreateContact} disabled={creating}
                className="flex-1 px-2 py-1.5 text-xs font-medium bg-[#0F172A] text-white rounded hover:bg-[#1E293B] disabled:opacity-50">
                {creating ? '...' : t('conv.create') || 'Create'}
              </button>
              <button onClick={() => setShowNewContact(false)}
                className="px-2 py-1.5 text-xs text-[#64748B] border border-[#E2E8F0] rounded hover:bg-white">
                {t('conv.cancel') || 'Cancel'}
              </button>
            </div>
          </div>
        )}
      </div>
      <div className="px-3 py-2 border-b border-[#E2E8F0] flex flex-wrap gap-1">
        {FILTERS.map((f) => (
          <button key={f.key} data-testid={`filter-${f.key}`} onClick={() => onFilterChange(f.key)} className={`px-2 py-0.5 text-xs rounded-md transition-colors ${filter === f.key ? 'bg-[#0F172A] text-white' : 'text-[#475569] hover:bg-[#F1F5F9]'}`}>
            {f.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-sm text-[#64748B]">{t('conv.loading')}</div>
        ) : conversations.length === 0 ? (
          <div className="p-4 text-center text-sm text-[#64748B]">{t('conv.no_results')}</div>
        ) : (
          conversations.map((conv) => {
            const contact = conv.contact || {};
            const isSelected = conv.id === selectedId;
            const hasUnread = conv.unread_count > 0;
            const hasPending = conv.pending_cases > 0 || conv.unclassified_count > 0;

            return (
              <div key={conv.id} data-testid={`conversation-item-${conv.id}`} className={`flex items-stretch border-b border-[#E2E8F0] transition-colors ${isSelected ? 'bg-[#F1F5F9]' : 'hover:bg-[#FAFBFC]'} ${hasUnread ? 'bg-blue-50/30' : ''}`}>
              <button onClick={() => onSelect(conv.id)} className="w-full text-left px-3 py-3 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      {hasUnread && <span className="w-2 h-2 rounded-full bg-[#2563EB] flex-shrink-0 animate-pulse-dot" />}
                      <span className={`text-sm truncate ${hasUnread ? 'font-semibold text-[#0F172A]' : 'font-medium text-[#334155]'}`}>
                        {contact.name || contact.phone || '?'}
                      </span>
                    </div>
                    <p className="text-xs text-[#64748B] mt-0.5 truncate">
                      {conv.last_message_direction === 'outgoing' && <span className="text-[#64748B]">{t('chat.you')} </span>}
                      {conv.last_message_body || ''}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <span className="text-[10px] text-[#64748B]">{formatTime(conv.last_message_at, locale)}</span>
                    {conv.window && conv.window.window_expires_at && (
                      <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full flex items-center gap-0.5 ${
                        conv.window.window_active
                          ? conv.window.seconds_remaining <= 7200
                            ? 'text-amber-700 bg-amber-50'
                            : 'text-green-700 bg-green-50'
                          : 'text-red-700 bg-red-50'
                      }`}>
                        <span className={`w-1 h-1 rounded-full ${
                          conv.window.window_active
                            ? conv.window.seconds_remaining <= 7200 ? 'bg-amber-500' : 'bg-green-500'
                            : 'bg-red-500'
                        }`} />
                        {conv.window.window_active
                          ? `${conv.window.hours_remaining}h`
                          : '24h'
                        }
                      </span>
                    )}
                    {conv.cases_count > 0 && (
                      <span className="text-[10px] font-medium text-[#475569] bg-[#F1F5F9] px-1.5 py-0.5 rounded">
                        {conv.cases_count} {conv.cases_count === 1 ? t('conv.case_open') : t('conv.cases_open')}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  {hasPending && (
                    <span className="text-[10px] font-medium text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                      {conv.pending_cases > 0 && `${conv.pending_cases} ${t('conv.pending')}`}
                      {conv.pending_cases > 0 && conv.unclassified_count > 0 && ' + '}
                      {conv.unclassified_count > 0 && `${conv.unclassified_count} ${t('conv.unclassified')}`}
                    </span>
                  )}
                  {conv.agent_names?.length > 0 && (
                    <span className="text-[11px] text-[#475569] font-medium truncate">{t('conv.attending')} {conv.agent_names.join(', ')}</span>
                  )}
                </div>
              </button>
              {onDelete && (
                <button onClick={(e) => { e.stopPropagation(); onDelete(conv.id); }}
                  className="px-2 flex items-center justify-center hover:bg-red-50 text-[#94A3B8] hover:text-red-500 transition-colors flex-shrink-0"
                  title={t('conv.delete') || 'Delete'}>
                  <X size={14} weight="bold" />
                </button>
              )}
            </div>
            );
          })
        )}
      </div>
    </>
  );
}
