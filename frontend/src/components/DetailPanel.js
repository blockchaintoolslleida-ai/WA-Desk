import { useState, useEffect } from 'react';
import { useTranslation } from '../contexts/LanguageContext';
import { casesApi, contactsApi } from '../lib/api';
import { User, Phone, EnvelopeSimple, Clock, PlusCircle, CaretDown, UserCircle, NotePencil, ListBullets, Tag, WarningCircle, PencilSimple, Check, X, NoteBlank, Trash } from '@phosphor-icons/react';
import { toast } from 'sonner';

const STATUS_COLORS = {
  nou: 'badge-nuevo', per_atendre: 'badge-por_atender', en_atencio: 'badge-en_atencion',
  esperant_client: 'badge-esperando_cliente', resolt: 'badge-resuelto', tancat: 'badge-cerrado',
};

function formatDT(d, locale) { return d ? new Date(d).toLocaleString(locale, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '-'; }

export default function DetailPanel({ conversation, agents, currentUserId, selectedCaseId, onSelectCase, onCaseStatusChange, onCaseAssign, onCreateCase, onContactUpdated }) {
  const { t, locale } = useTranslation();
  const [tab, setTab] = useState('cases');
  const [caseNotes, setCaseNotes] = useState([]);
  const [caseEvents, setCaseEvents] = useState([]);
  const [newNote, setNewNote] = useState('');
  const [showStatusDD, setShowStatusDD] = useState(false);
  const [showAgentDD, setShowAgentDD] = useState(false);
  const [editingContact, setEditingContact] = useState(false);
  const [contactForm, setContactForm] = useState({});
  const [savingContact, setSavingContact] = useState(false);
  const [editingNoteId, setEditingNoteId] = useState(null);
  const [editingNoteText, setEditingNoteText] = useState('');
  const [savingNote, setSavingNote] = useState(false);
  const [confirmDeleteNote, setConfirmDeleteNote] = useState(null);
  const contact = conversation?.contact || {};
  const cases = conversation?.cases || [];
  const selectedCase = cases.find(c => c.id === selectedCaseId);

  useEffect(() => {
    if (selectedCaseId) {
      casesApi.notes(selectedCaseId).then(r => setCaseNotes(r.data || [])).catch(() => {});
      casesApi.events(selectedCaseId).then(r => setCaseEvents(r.data || [])).catch(() => {});
      casesApi.registerView(selectedCaseId).catch(() => {});
    }
  }, [selectedCaseId]);

  const handleAddNote = async (e) => {
    e.preventDefault();
    if (!newNote.trim() || !selectedCaseId) return;
    try {
      await casesApi.createNote(selectedCaseId, newNote.trim());
      setNewNote('');
      const r = await casesApi.notes(selectedCaseId);
      setCaseNotes(r.data || []);
    } catch {
      toast.error(t('detail.note_error'));
    }
  };

  const startEditNote = (n) => {
    setEditingNoteId(n.id);
    setEditingNoteText(n.note);
  };

  const cancelEditNote = () => {
    setEditingNoteId(null);
    setEditingNoteText('');
  };

  const saveEditNote = async () => {
    if (!editingNoteText.trim() || !editingNoteId) return;
    setSavingNote(true);
    try {
      await casesApi.updateNote(selectedCaseId, editingNoteId, editingNoteText.trim());
      const r = await casesApi.notes(selectedCaseId);
      setCaseNotes(r.data || []);
      cancelEditNote();
      toast.success(t('detail.note_updated'));
    } catch (err) {
      toast.error(err.response?.data?.detail || t('detail.note_error'));
    }
    setSavingNote(false);
  };

  const deleteNote = async (noteId) => {
    setSavingNote(true);
    try {
      await casesApi.deleteNote(selectedCaseId, noteId);
      const r = await casesApi.notes(selectedCaseId);
      setCaseNotes(r.data || []);
      setConfirmDeleteNote(null);
      toast.success(t('detail.note_deleted'));
    } catch (err) {
      toast.error(err.response?.data?.detail || t('detail.note_error'));
    }
    setSavingNote(false);
  };

  const STATUS_OPTS = [
    { v: 'nou', l: t('status.nou') }, { v: 'per_atendre', l: t('status.per_atendre') },
    { v: 'en_atencio', l: t('status.en_atencio') }, { v: 'esperant_client', l: t('status.esperant_client') },
    { v: 'resolt', l: t('status.resolt') }, { v: 'tancat', l: t('status.tancat') },
  ];

  const tabs = [
    { key: 'cases', label: t('detail.tab_cases'), icon: Tag },
    { key: 'info', label: t('detail.tab_info'), icon: User },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Tabs */}
      <div className="flex border-b border-[#E2E8F0]">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button key={key} data-testid={`detail-tab-${key}`} onClick={() => setTab(key)} className={`flex-1 py-2.5 text-xs font-medium flex items-center justify-center gap-1 transition-colors border-b-2 ${tab === key ? 'border-[#0F172A] text-[#0F172A]' : 'border-transparent text-[#64748B] hover:text-[#475569]'}`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {/* CASES TAB */}
        {tab === 'cases' && (
          <div className="space-y-3">
            {/* Case list */}
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-bold uppercase tracking-wide text-[#64748B]">{t('case.title')} ({cases.length})</h3>
              <button data-testid="create-case-btn" onClick={onCreateCase} className="flex items-center gap-1 text-[10px] font-medium text-[#2563EB] hover:underline">
                <PlusCircle size={14} /> {t('case.new')}
              </button>
            </div>

            {conversation.unclassified_count > 0 && (
              <div className="flex items-center gap-1.5 p-2 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-700">
                <WarningCircle size={14} weight="bold" />
                <span>{conversation.unclassified_count} {t('conv.unclassified')}</span>
              </div>
            )}

            {cases.length === 0 ? (
              <p className="text-sm text-[#64748B] text-center py-3">{t('case.no_cases')}</p>
            ) : (
              cases.map(c => (
                <button key={c.id} data-testid={`case-item-${c.id}`} onClick={() => onSelectCase(c.id === selectedCaseId ? null : c.id)} className={`w-full text-left p-2.5 rounded-md border transition-colors ${c.id === selectedCaseId ? 'border-[#0F172A] bg-[#F8FAFC]' : 'border-[#E2E8F0] hover:bg-[#FAFBFC]'}`}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-sm font-medium text-[#0F172A] line-clamp-1">{c.title}</span>
                    <span className={`${STATUS_COLORS[c.status] || ''} text-[9px] px-1.5 py-0.5 rounded-md font-medium whitespace-nowrap`}>{t(`status.${c.status}`)}</span>
                  </div>
                  {c.assigned_agent_name && <p className="text-xs text-[#475569] mt-1 font-medium">{c.assigned_agent_name}</p>}
                  {c.priority && c.priority !== 'normal' && <span className="text-[9px] font-bold text-red-600 uppercase mt-1 inline-block">{t(`priority.${c.priority}`)}</span>}
                </button>
              ))
            )}

            {/* Selected case detail */}
            {selectedCase && (
              <div className="mt-4 pt-3 border-t border-[#E2E8F0] space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wide text-[#64748B]">{selectedCase.title}</h4>

                {/* Status */}
                <div className="relative">
                  <label className="text-[10px] font-bold uppercase tracking-wide text-[#64748B]">{t('detail.status')}</label>
                  <button data-testid="case-status-trigger" onClick={() => setShowStatusDD(!showStatusDD)} className={`${STATUS_COLORS[selectedCase.status]} w-full text-left px-3 py-1.5 rounded-md text-xs font-medium flex items-center justify-between mt-1`}>
                    {t(`status.${selectedCase.status}`)} <CaretDown size={12} />
                  </button>
                  {showStatusDD && (
                    <div className="absolute z-10 mt-1 w-full bg-white border border-[#E2E8F0] rounded-md shadow-lg">
                      {STATUS_OPTS.map(o => (
                        <button key={o.v} data-testid={`case-status-${o.v}`} onClick={() => { onCaseStatusChange(selectedCase.id, o.v); setShowStatusDD(false); }} className="w-full text-left px-3 py-1.5 text-xs hover:bg-[#F1F5F9]">
                          <span className={`${STATUS_COLORS[o.v]} px-1.5 py-0.5 rounded text-[9px]`}>{o.l}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Agent */}
                <div className="relative">
                  <label className="text-[10px] font-bold uppercase tracking-wide text-[#64748B]">{t('detail.agent')}</label>
                  <button data-testid="case-agent-trigger" onClick={() => setShowAgentDD(!showAgentDD)} className="w-full text-left px-3 py-1.5 rounded-md text-xs border border-[#E2E8F0] flex items-center justify-between mt-1 hover:bg-[#F8FAFC]">
                    <span className="flex items-center gap-1"><UserCircle size={14} className="text-[#64748B]" /> {selectedCase.assigned_agent_name || t('detail.unassigned')}</span>
                    <CaretDown size={12} className="text-[#64748B]" />
                  </button>
                  {showAgentDD && (
                    <div className="absolute z-10 mt-1 w-full bg-white border border-[#E2E8F0] rounded-md shadow-lg max-h-40 overflow-y-auto">
                      <button data-testid="case-assign-me" onClick={() => { onCaseAssign(selectedCase.id, null); setShowAgentDD(false); }} className="w-full text-left px-3 py-1.5 text-xs text-[#2563EB] font-medium hover:bg-[#F1F5F9]">{t('detail.assign_me')}</button>
                      {agents.map(a => (
                        <button key={a.id} onClick={() => { onCaseAssign(selectedCase.id, a.id); setShowAgentDD(false); }} className="w-full text-left px-3 py-1.5 text-xs hover:bg-[#F1F5F9]">{a.full_name}</button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex flex-wrap gap-1.5">
                  {!['resolt', 'tancat'].includes(selectedCase.status) && (
                    <>
                      <button data-testid="case-resolve" onClick={() => onCaseStatusChange(selectedCase.id, 'resolt')} className="px-2 py-1 text-[10px] font-medium rounded-md border border-[#E2E8F0] hover:bg-[#F1F5F9]">{t('detail.resolve')}</button>
                      <button data-testid="case-close" onClick={() => onCaseStatusChange(selectedCase.id, 'tancat')} className="px-2 py-1 text-[10px] font-medium rounded-md border border-[#E2E8F0] hover:bg-[#F1F5F9]">{t('detail.close')}</button>
                    </>
                  )}
                  {['resolt', 'tancat'].includes(selectedCase.status) && (
                    <button data-testid="case-reopen" onClick={() => onCaseStatusChange(selectedCase.id, 'per_atendre')} className="px-2 py-1 text-[10px] font-medium rounded-md border border-amber-200 bg-amber-50 text-amber-700">{t('detail.reopen')}</button>
                  )}
                </div>

                {/* Dates */}
                <div className="text-[10px] text-[#64748B] space-y-1">
                  <p><Clock size={10} className="inline mr-1" />{t('detail.created')} {formatDT(selectedCase.created_at, locale)}</p>
                  <p><Clock size={10} className="inline mr-1" />{t('detail.last_activity')} {formatDT(selectedCase.last_activity_at, locale)}</p>
                </div>

                {/* Notes */}
                <div>
                  <h5 className="text-[10px] font-bold uppercase tracking-wide text-[#64748B] mb-1 flex items-center gap-1"><NotePencil size={12} /> {t('detail.tab_notes')}</h5>
                  <form onSubmit={handleAddNote} className="mb-2">
                    <textarea data-testid="case-note-input" rows={2} value={newNote}
                      onChange={e => setNewNote(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleAddNote(e); }}
                      placeholder={t('detail.note_placeholder')}
                      className="w-full px-2 py-1.5 text-[11px] border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-1 focus:ring-[#0F172A] resize-none" />
                    <div className="flex justify-end mt-1">
                      <button data-testid="case-note-submit" type="submit" disabled={!newNote.trim()}
                        className="px-2.5 py-1 text-[10px] font-medium bg-[#0F172A] text-white rounded-md disabled:opacity-30">
                        {t('detail.add_note')}
                      </button>
                    </div>
                  </form>
                  {caseNotes.length === 0 ? (
                    <p className="text-[11px] text-[#64748B]">{t('detail.no_notes')}</p>
                  ) : caseNotes.map(n => {
                    const isAuthor = n.author_id === currentUserId;
                    const isEditing = editingNoteId === n.id;
                    return (
                      <div key={n.id} data-testid={`case-note-${n.id}`} className="p-2 bg-[#FFFBEB] border border-[#FDE68A] rounded-md mb-1.5 group">
                        {isEditing ? (
                          <div>
                            <textarea data-testid={`case-note-edit-${n.id}`} rows={2} value={editingNoteText}
                              onChange={e => setEditingNoteText(e.target.value)}
                              className="w-full px-2 py-1.5 text-[11px] border border-amber-300 rounded-md focus:outline-none focus:ring-1 focus:ring-amber-500 bg-white resize-none" />
                            <div className="flex items-center justify-end gap-1 mt-1">
                              <button data-testid={`case-note-cancel-${n.id}`} onClick={cancelEditNote}
                                className="px-2 py-0.5 text-[10px] text-[#64748B] hover:bg-[#F1F5F9] rounded">{t('detail.cancel')}</button>
                              <button data-testid={`case-note-save-${n.id}`} onClick={saveEditNote}
                                disabled={savingNote || !editingNoteText.trim()}
                                className="px-2 py-0.5 text-[10px] font-medium bg-amber-600 text-white rounded disabled:opacity-40">
                                {savingNote ? '...' : t('detail.save')}
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div>
                            <p className="text-[11px] text-[#92400E] whitespace-pre-wrap break-words">{n.note}</p>
                            <div className="flex items-center justify-between mt-0.5">
                              <p className="text-[9px] text-[#B45309]">
                                {n.author_name} · {formatDT(n.created_at, locale)}
                                {n.updated_at && <span className="italic ml-1">({t('detail.note_edited')})</span>}
                              </p>
                              {isAuthor && (
                                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                  <button data-testid={`case-note-edit-btn-${n.id}`} onClick={() => startEditNote(n)}
                                    title={t('detail.edit')}
                                    className="p-0.5 text-[#B45309] hover:bg-amber-200 rounded">
                                    <PencilSimple size={11} />
                                  </button>
                                  <button data-testid={`case-note-delete-btn-${n.id}`} onClick={() => setConfirmDeleteNote(n)}
                                    title={t('detail.delete')}
                                    className="p-0.5 text-red-600 hover:bg-red-100 rounded">
                                    <Trash size={11} />
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Events */}
                <div>
                  <h5 className="text-[10px] font-bold uppercase tracking-wide text-[#64748B] mb-1 flex items-center gap-1"><ListBullets size={12} /> {t('detail.tab_history')}</h5>
                  {caseEvents.length === 0 ? <p className="text-[11px] text-[#64748B]">{t('detail.no_history')}</p> : caseEvents.map(ev => (
                    <div key={ev.id} className="flex gap-2 text-[10px] mb-1.5">
                      <div className="w-1.5 h-1.5 rounded-full bg-[#94A3B8] mt-1 flex-shrink-0" />
                      <div>
                        <span className="font-medium text-[#334155]">{t(`event.${ev.event_type}`) || ev.event_type}</span>
                        {ev.actor_name && ev.actor_name !== 'Sistema' && <span className="text-[#64748B]"> {t('event.by')} {ev.actor_name}</span>}
                        {ev.old_value?.status && ev.new_value?.status && <p className="text-[#64748B]">{t(`status.${ev.old_value.status}`)} → {t(`status.${ev.new_value.status}`)}</p>}
                        {ev.event_type === 'reassignment' && (
                          <p className="text-[#64748B]">{ev.old_value?.agent_name || '?'} → <span className="font-medium text-[#334155]">{ev.new_value?.agent_name || '?'}</span></p>
                        )}
                        {ev.event_type === 'assignment' && ev.new_value?.agent_name && (
                          <p className="text-[#64748B]">→ <span className="font-medium text-[#334155]">{ev.new_value.agent_name}</span></p>
                        )}
                        <p className="text-[#94A3B8]">{formatDT(ev.created_at, locale)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* INFO TAB */}
        {tab === 'info' && (
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-bold uppercase tracking-wide text-[#64748B]">{t('detail.contact')}</h3>
                {!editingContact ? (
                  <button data-testid="edit-contact-btn" onClick={() => { setEditingContact(true); setContactForm({ name: contact.name || '', email: contact.email || '', phone: contact.phone || '', notes: contact.notes || '' }); }}
                    className="flex items-center gap-1 text-[10px] font-medium text-[#2563EB] hover:underline">
                    <PencilSimple size={12} /> {t('detail.edit')}
                  </button>
                ) : (
                  <div className="flex items-center gap-1">
                    <button data-testid="save-contact-btn" disabled={savingContact} onClick={async () => {
                      setSavingContact(true);
                      try {
                        await contactsApi.update(contact.id, contactForm);
                        setEditingContact(false);
                        if (onContactUpdated) onContactUpdated();
                        toast.success(t('detail.contact_saved'));
                      } catch { toast.error(t('detail.contact_error')); }
                      finally { setSavingContact(false); }
                    }} className="p-1 rounded hover:bg-green-50 text-green-600"><Check size={16} weight="bold" /></button>
                    <button data-testid="cancel-edit-btn" onClick={() => setEditingContact(false)} className="p-1 rounded hover:bg-red-50 text-red-500"><X size={16} /></button>
                  </div>
                )}
              </div>

              {!editingContact ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm"><User size={14} className="text-[#64748B]" />{contact.name || t('detail.no_name')}</div>
                  <div className="flex items-center gap-2 text-sm"><Phone size={14} className="text-[#64748B]" /><span className="font-mono text-xs">{contact.phone || '-'}</span></div>
                  <div className="flex items-center gap-2 text-sm"><EnvelopeSimple size={14} className="text-[#64748B]" />{contact.email || <span className="text-[#94A3B8] italic">{t('detail.no_email')}</span>}</div>
                  {contact.notes && (
                    <div className="mt-2 p-2 bg-[#F8FAFC] rounded-md border border-[#E2E8F0]">
                      <div className="flex items-center gap-1 text-[10px] font-medium text-[#64748B] mb-1"><NoteBlank size={12} />{t('detail.notes')}</div>
                      <p className="text-xs text-[#475569] whitespace-pre-wrap">{contact.notes}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  <div>
                    <label className="text-[10px] font-medium text-[#64748B] uppercase">{t('detail.field_name')}</label>
                    <input data-testid="contact-name-input" value={contactForm.name} onChange={e => setContactForm(f => ({ ...f, name: e.target.value }))}
                      className="w-full mt-0.5 px-2 py-1.5 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
                  </div>
                  <div>
                    <label className="text-[10px] font-medium text-[#64748B] uppercase">{t('detail.field_phone')}</label>
                    <input data-testid="contact-phone-input" value={contactForm.phone} onChange={e => setContactForm(f => ({ ...f, phone: e.target.value }))}
                      className="w-full mt-0.5 px-2 py-1.5 text-sm font-mono border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
                  </div>
                  <div>
                    <label className="text-[10px] font-medium text-[#64748B] uppercase">{t('detail.field_email')}</label>
                    <input data-testid="contact-email-input" type="email" value={contactForm.email} onChange={e => setContactForm(f => ({ ...f, email: e.target.value }))}
                      placeholder="email@example.com" className="w-full mt-0.5 px-2 py-1.5 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
                  </div>
                  <div>
                    <label className="text-[10px] font-medium text-[#64748B] uppercase">{t('detail.notes')}</label>
                    <textarea data-testid="contact-notes-input" value={contactForm.notes} onChange={e => setContactForm(f => ({ ...f, notes: e.target.value }))}
                      rows={3} placeholder={t('detail.notes_placeholder')} className="w-full mt-0.5 px-2 py-1.5 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A] resize-none" />
                  </div>
                </div>
              )}
            </div>
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wide text-[#64748B] mb-2">{t('detail.dates')}</h3>
              <div className="text-xs text-[#475569] space-y-1">
                <p><Clock size={12} className="inline mr-1 text-[#64748B]" />{t('detail.created')} {formatDT(conversation.created_at, locale)}</p>
                <p><Clock size={12} className="inline mr-1 text-[#64748B]" />{t('detail.last_message')} {formatDT(conversation.last_message_at, locale)}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Delete note confirmation modal */}
      {confirmDeleteNote && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => !savingNote && setConfirmDeleteNote(null)}>
          <div className="bg-white rounded-xl p-5 w-full max-w-sm shadow-2xl mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>{t('detail.note_delete_title')}</h3>
            <p className="text-xs text-[#475569] mb-2">{t('detail.note_delete_confirm')}</p>
            <div className="p-2 bg-[#FFFBEB] border border-[#FDE68A] rounded-md mb-3">
              <p className="text-[11px] text-[#92400E] whitespace-pre-wrap break-words line-clamp-3">{confirmDeleteNote.note}</p>
            </div>
            <div className="flex gap-2">
              <button data-testid="case-note-delete-cancel" onClick={() => setConfirmDeleteNote(null)} disabled={savingNote}
                className="flex-1 px-3 py-2 text-xs font-medium border border-[#E2E8F0] rounded-md hover:bg-[#F8FAFC]">
                {t('detail.cancel')}
              </button>
              <button data-testid="case-note-delete-confirm" onClick={() => deleteNote(confirmDeleteNote.id)} disabled={savingNote}
                className="flex-1 px-3 py-2 text-xs font-semibold bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-40 flex items-center justify-center gap-1.5">
                <Trash size={12} weight="bold" />
                {savingNote ? '...' : t('detail.delete')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
